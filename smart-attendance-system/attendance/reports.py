import io
from datetime import datetime, timedelta

from flask import Blueprint, Response, flash, redirect, render_template, request, send_file, session, url_for

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    PDF_AVAILABLE = True
except Exception:
    PDF_AVAILABLE = False

from .db import get_db
from .security import login_required, role_required
from .utils import rows_to_csv
from .attendance_routes import _apply_auto_absences

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/clear-attendance", methods=["POST"])
@login_required
@role_required("admin")
def clear_attendance_data():
    db = get_db()
    attendance_deleted = db.execute("DELETE FROM attendance").rowcount or 0
    sync_deleted = db.execute("DELETE FROM sync_queue WHERE entity_type = 'attendance'").rowcount or 0
    db.commit()
    flash(f"Cleared attendance data: {attendance_deleted} attendance rows and {sync_deleted} sync rows.", "success")
    return redirect(url_for("reports.reports_home"))


@reports_bp.route("/")
@login_required
def reports_home():
    _apply_auto_absences()
    db = get_db()
    period = request.args.get("period", "monthly")
    section_name = request.args.get("section", "")
    subject = request.args.get("subject", "")
    student_id = session.get("student_id") if session.get("role") == "student" else None

    end_date = datetime.now().date()
    if period == "weekly":
        start_date = end_date - timedelta(days=6)
    else:
        start_date = end_date.replace(day=1)

    where_section = ""
    where_subject = ""
    where_student = ""
    params = [str(start_date), str(end_date)]
    if section_name:
        where_section = "AND s.section_name = ?"
        params.append(section_name)
    if subject:
        where_subject = "AND a.subject = ?"
        params.append(subject)
    if student_id:
        where_student = "AND s.id = ?"
        params.append(student_id)

    rows = db.execute(
        f"""
        SELECT
            s.student_code,
            s.name,
            s.section_name,
            COUNT(a.id) as marked_sessions,
            SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as present_sessions,
            SUM(CASE WHEN a.status = 'late' THEN 1 ELSE 0 END) as late_sessions
        FROM students s
        LEFT JOIN attendance a ON a.student_id = s.id AND a.date BETWEEN ? AND ?
        WHERE s.active = 1 {where_section} {where_subject} {where_student}
        GROUP BY s.id
        ORDER BY s.section_name, s.name
        """,
        tuple(params),
    ).fetchall()

    report_rows = []
    for r in rows:
        no_of_classes = int(r["marked_sessions"] or 0)
        present_sessions = int(r["present_sessions"] or 0)
        absent_sessions = no_of_classes - present_sessions
        percent = round((present_sessions / no_of_classes) * 100, 2) if no_of_classes else 0.0
        report_rows.append(
            {
                "student_code": r["student_code"],
                "name": r["name"],
                "section_name": r["section_name"],
                "no_of_classes": no_of_classes,
                "present_sessions": present_sessions,
                "absent_sessions": absent_sessions,
                "attendance_percent": percent,
            }
        )

    sections = db.execute("SELECT DISTINCT section_name FROM students WHERE active = 1 ORDER BY section_name").fetchall()
    subjects = db.execute("SELECT DISTINCT subject FROM attendance ORDER BY subject").fetchall()

    return render_template(
        "reports.html",
        rows=report_rows,
        period=period,
        section_name=section_name,
        subject=subject,
        student_mode=bool(student_id),
        sections=[c["section_name"] for c in sections],
        subjects=[s["subject"] for s in subjects if s["subject"]],
        start_date=start_date,
        end_date=end_date,
    )


@reports_bp.route("/export/csv")
@login_required
def export_csv():
    _apply_auto_absences()
    rows = _current_report_rows(request.args.get("subject", ""), session.get("student_id") if session.get("role") == "student" else None)
    headers = [
        "student_code",
        "name",
        "section_name",
        "no_of_classes",
        "present_sessions",
        "absent_sessions",
        "attendance_percent",
    ]
    data = rows_to_csv(rows, headers)
    return Response(
        data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance_report.csv"},
    )


@reports_bp.route("/export/pdf")
@login_required
def export_pdf():
    _apply_auto_absences()
    if not PDF_AVAILABLE:
        return Response("PDF export dependency missing. Install reportlab.", status=503)

    rows = _current_report_rows(request.args.get("subject", ""), session.get("student_id") if session.get("role") == "student" else None)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(40, height - 40, "Smart Attendance Report")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, height - 58, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    y = height - 85
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(40, y, "Code")
    pdf.drawString(100, y, "Name")
    pdf.drawString(230, y, "Class")
    pdf.drawString(280, y, "Present")
    pdf.drawString(330, y, "Absent")
    pdf.drawString(380, y, "No. Classes")
    pdf.drawString(455, y, "Percent")
    y -= 14

    pdf.setFont("Helvetica", 9)
    for row in rows:
        if y < 40:
            pdf.showPage()
            y = height - 40
            pdf.setFont("Helvetica", 9)
        pdf.drawString(40, y, str(row["student_code"]))
        pdf.drawString(100, y, str(row["name"])[:22])
        pdf.drawString(230, y, str(row["section_name"]))
        pdf.drawString(280, y, str(row["present_sessions"]))
        pdf.drawString(330, y, str(row["absent_sessions"]))
        pdf.drawString(380, y, str(row["no_of_classes"]))
        pdf.drawString(455, y, f"{row['attendance_percent']}%")
        y -= 12

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="attendance_report.pdf", mimetype="application/pdf")


def _current_report_rows(subject="", student_id=None):
    db = get_db()
    where_subject = ""
    where_student = ""
    params = []
    if subject:
        where_subject = "AND a.subject = ?"
        params.append(subject)
    if student_id:
        where_student = "AND s.id = ?"
        params.append(student_id)

    rows = db.execute(
        f"""
        SELECT
            s.student_code,
            s.name,
            s.section_name,
            COUNT(a.id) as marked_sessions,
            SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as present_sessions,
            SUM(CASE WHEN a.status = 'late' THEN 1 ELSE 0 END) as late_sessions
        FROM students s
        LEFT JOIN attendance a ON a.student_id = s.id
        WHERE s.active = 1 {where_subject} {where_student}
        GROUP BY s.id
        ORDER BY s.section_name, s.name
        """
        ,
        tuple(params),
    ).fetchall()

    report_rows = []
    for r in rows:
        no_of_classes = int(r["marked_sessions"] or 0)
        present_sessions = int(r["present_sessions"] or 0)
        absent_sessions = no_of_classes - present_sessions
        percent = round((present_sessions / no_of_classes) * 100, 2) if no_of_classes else 0.0
        report_rows.append(
            {
                "student_code": r["student_code"],
                "name": r["name"],
                "section_name": r["section_name"],
                "no_of_classes": no_of_classes,
                "present_sessions": present_sessions,
                "absent_sessions": absent_sessions,
                "attendance_percent": percent,
            }
        )
    return report_rows
