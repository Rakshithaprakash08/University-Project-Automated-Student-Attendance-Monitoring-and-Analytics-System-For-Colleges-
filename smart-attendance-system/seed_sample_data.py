from attendance import create_app
from attendance.db import get_db
from werkzeug.security import generate_password_hash

app = create_app()

SAMPLE_STUDENTS = [
    ("20221CSG0114", "Rakshitha D P", "CSG", "", "UID1001", "9876543210"),
    ("20221CSG0116", "Vishal Gowda H", "CSG", "", "UID1002", "9876543211"),
    ("20221CSG0124", "Sai Siri Naidu O", "CSG", "", "UID1003", "9876543212"),
    ("20221ECE0127", "Pavan", "ECE", "", "UID1004", "9876543213"),
    ("20221EEE0108", "Tejas", "EEE", "", "UID1005", "9876543214"),
    ("20221ECE0110", "Preethi", "ECE", "", "UID1006", "9876543215"),
]

with app.app_context():
    db = get_db()

    users = db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    if users == 0:
        db.execute(
            "INSERT INTO users (name, role, username, password_hash) VALUES (?, ?, ?, ?)",
            ("System Admin", "admin", "admin", generate_password_hash("admin123")),
        )
        db.execute(
            "INSERT INTO users (name, role, username, password_hash) VALUES (?, ?, ?, ?)",
            ("Teacher", "teacher", "teacher", generate_password_hash("teacher123")),
        )

    for student in SAMPLE_STUDENTS:
        exists = db.execute("SELECT id FROM students WHERE student_code = ?", (student[0],)).fetchone()
        if not exists:
            db.execute(
                """
                INSERT INTO students (student_code, name, section_name, section, unique_id, guardian_phone)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                student,
            )

    db.commit()
    print("Sample data inserted")

