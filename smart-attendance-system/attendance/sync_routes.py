import json
import urllib.error
import urllib.request

from flask import Blueprint, current_app, jsonify, request

from .db import get_db
from .security import login_required, role_required

sync_bp = Blueprint("sync", __name__, url_prefix="/sync")


@sync_bp.route("/status")
@login_required
def status():
    db = get_db()
    unsynced = db.execute("SELECT COUNT(*) AS count FROM attendance WHERE synced = 0").fetchone()["count"]
    queue = db.execute("SELECT COUNT(*) AS count FROM sync_queue WHERE processed = 0").fetchone()["count"]
    return jsonify({"unsynced_attendance": unsynced, "pending_queue": queue})


@sync_bp.route("/push", methods=["POST"])
@login_required
@role_required("teacher", "admin")
def push():
    remote_url = current_app.config.get("REMOTE_SYNC_URL", "").strip()
    if not remote_url:
        return jsonify({"ok": False, "message": "REMOTE_SYNC_URL not configured"}), 400

    db = get_db()
    queue_items = db.execute(
        "SELECT id, entity_type, entity_id, operation, payload FROM sync_queue WHERE processed = 0 ORDER BY id LIMIT 500"
    ).fetchall()
    if not queue_items:
        return jsonify({"ok": True, "message": "Nothing to sync", "count": 0})

    payload = {
        "school_code": current_app.config.get("SCHOOL_CODE"),
        "items": [dict(item) for item in queue_items],
    }

    try:
        req = urllib.request.Request(
            f"{remote_url}/api/sync/ingest",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status >= 400:
                raise urllib.error.HTTPError(req.full_url, response.status, "HTTP error", hdrs=None, fp=None)
    except Exception as exc:
        return jsonify({"ok": False, "message": f"Sync failed: {exc}"}), 503

    synced_ids = [item["id"] for item in queue_items]
    marks = ",".join("?" for _ in synced_ids)
    db.execute(f"UPDATE sync_queue SET processed = 1 WHERE id IN ({marks})", tuple(synced_ids))
    db.execute("UPDATE attendance SET synced = 1 WHERE synced = 0")
    db.commit()
    return jsonify({"ok": True, "message": "Sync successful", "count": len(synced_ids)})


@sync_bp.route("/api/sync/ingest", methods=["POST"])
def ingest_remote_payload():
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    db = get_db()

    inserted = 0
    for item in items:
        payload = item.get("payload")
        if not payload:
            continue
        payload_dict = json.loads(payload)
        student_id = payload_dict.get("student_id")
        date = payload_dict.get("date")
        subject = (payload_dict.get("subject") or "General").strip() or "General"
        status = payload_dict.get("status", "present")
        mode = payload_dict.get("mode", "manual")
        timestamp = payload_dict.get("timestamp")
        note = payload_dict.get("note")

        if not student_id or not date:
            continue

        exists = db.execute(
            "SELECT id FROM attendance WHERE student_id = ? AND date = ? AND subject = ?",
            (student_id, date, subject),
        ).fetchone()
        if exists:
            continue

        db.execute(
            "INSERT INTO attendance (student_id, date, subject, status, mode, timestamp, synced, note) VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
            (student_id, date, subject, status, mode, timestamp, note),
        )
        inserted += 1

    db.commit()
    return jsonify({"ok": True, "inserted": inserted})
