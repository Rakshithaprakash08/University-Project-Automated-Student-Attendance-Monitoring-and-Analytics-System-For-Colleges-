from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

from .db import get_db
from .face import extract_face_encoding
from .security import login_required, role_required
from .utils import to_json

students_bp = Blueprint("students", __name__, url_prefix="/students")


@students_bp.route("/")
@login_required
@role_required("admin", "teacher")
def list_students():
    db = get_db()
    section_filter = request.args.get("section", "").strip()
    if section_filter:
        rows = db.execute(
            "SELECT * FROM students WHERE active = 1 AND section_name = ? ORDER BY section_name, name",
            (section_filter,),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM students WHERE active = 1 ORDER BY section_name, name").fetchall()
    return render_template("students.html", students=rows, section_filter=section_filter)


@students_bp.route("/add", methods=["GET", "POST"])
@login_required
@role_required("admin")
def add_student():
    if request.method == "POST":
        return _save_student()
    return render_template("student_form.html", student=None)


@students_bp.route("/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_student(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        flash("Student not found", "error")
        return redirect(url_for("students.list_students"))

    if request.method == "POST":
        return _save_student(student_id)

    student_user = db.execute(
        "SELECT id, username FROM users WHERE role = 'student' AND student_id = ?",
        (student_id,),
    ).fetchone()
    return render_template("student_form.html", student=student, student_user=student_user)


@students_bp.route("/<int:student_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_student(student_id):
    db = get_db()
    db.execute("UPDATE students SET active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (student_id,))
    db.commit()
    flash("Student archived", "success")
    return redirect(url_for("students.list_students"))


def _save_student(student_id=None):
    db = get_db()

    student_code = request.form.get("student_code", "").strip()
    name = request.form.get("name", "").strip()
    section_name = request.form.get("section_name", "").strip()
    section = request.form.get("section", "").strip()
    unique_id = request.form.get("unique_id", "").strip().upper()
    guardian_phone = request.form.get("guardian_phone", "").strip()
    login_username = request.form.get("login_username", "").strip()
    login_password = request.form.get("login_password", "")

    if not all([student_code, name, section_name]):
        flash("Student code, name and section are required", "error")
        return redirect(request.url)

    photo = request.files.get("photo")
    photo_path = None
    photo_encoding = None

    if photo and photo.filename:
        safe_name = secure_filename(f"{student_code}_{photo.filename}")
        upload_path = Path(current_app.config["UPLOAD_DIR"]) / safe_name
        photo.save(upload_path)
        photo_path = str(upload_path)
        photo_encoding = extract_face_encoding(upload_path.read_bytes())

    try:
        if student_id:
            existing = db.execute("SELECT photo_path, photo_encoding FROM students WHERE id = ?", (student_id,)).fetchone()
            db.execute(
                """
                UPDATE students
                SET student_code = ?, name = ?, section_name = ?, section = ?,
                    photo_path = ?, photo_encoding = ?, unique_id = ?, guardian_phone = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    student_code,
                    name,
                    section_name,
                    section,
                    photo_path or existing["photo_path"],
                    to_json(photo_encoding) if photo_encoding else existing["photo_encoding"],
                    unique_id or None,
                    guardian_phone or None,
                    student_id,
                ),
            )
        else:
            cursor = db.execute(
                """
                INSERT INTO students
                (student_code, name, section_name, section, photo_path, photo_encoding, unique_id, guardian_phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    student_code,
                    name,
                    section_name,
                    section,
                    photo_path,
                    to_json(photo_encoding) if photo_encoding else None,
                    unique_id or None,
                    guardian_phone or None,
                ),
            )
            student_id = cursor.lastrowid

        if login_username:
            _upsert_student_user(db, student_id, name, login_username, login_password)
        db.commit()
        flash("Student saved", "success")
    except Exception as exc:
        if isinstance(exc, ValueError):
            flash(str(exc), "error")
        else:
            flash("Unable to save student. Check duplicate student code, Unique ID, or username.", "error")

    return redirect(url_for("students.list_students"))


def _upsert_student_user(db, student_id, name, username, password):
    existing = db.execute(
        "SELECT id, password_hash FROM users WHERE role = 'student' AND student_id = ?",
        (student_id,),
    ).fetchone()

    if existing:
        password_hash = existing["password_hash"]
        if password:
            password_hash = generate_password_hash(password)
        db.execute(
            "UPDATE users SET name = ?, username = ?, password_hash = ? WHERE id = ?",
            (name, username, password_hash, existing["id"]),
        )
    else:
        if not password:
            raise ValueError("Password required when creating student login")
        db.execute(
            "INSERT INTO users (name, role, username, password_hash, student_id) VALUES (?, 'student', ?, ?, ?)",
            (name, username, generate_password_hash(password), student_id),
        )

