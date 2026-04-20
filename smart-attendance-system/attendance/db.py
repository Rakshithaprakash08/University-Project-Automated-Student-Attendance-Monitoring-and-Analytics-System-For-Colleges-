import sqlite3
from pathlib import Path

from flask import current_app, g


def get_db():
    if "db" not in g:
        db_path = current_app.config["DB_PATH"]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    schema_path = Path(current_app.root_path).parent / "schema.sql"
    db.executescript(schema_path.read_text(encoding="utf-8"))
    db.commit()


def ensure_db_initialized():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('teacher', 'admin', 'student')),
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            student_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            section_name TEXT NOT NULL,
            section TEXT,
            photo_path TEXT,
            photo_encoding TEXT,
            unique_id TEXT UNIQUE,
            guardian_phone TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT 'General',
            status TEXT NOT NULL CHECK (status IN ('present', 'absent', 'late')),
            mode TEXT NOT NULL CHECK (mode IN ('manual', 'face', 'unique_id', 'qr')),
            unique_id_done INTEGER NOT NULL DEFAULT 0,
            face_done INTEGER NOT NULL DEFAULT 0,
            qr_done INTEGER NOT NULL DEFAULT 0,
            timestamp TEXT NOT NULL,
            synced INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(student_id, date, subject)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            operation TEXT NOT NULL CHECK (operation IN ('insert', 'update', 'delete')),
            payload TEXT,
            queued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            processed INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_name TEXT NOT NULL,
            weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
            subject TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(section_name, weekday, subject)
        )
        """
    )
    _migrate_users_for_students(db)
    _migrate_attendance_for_subjects(db)
    _migrate_attendance_for_verification_flags(db)
    _migrate_students_class_to_section(db)
    _migrate_unique_id_naming(db)
    db.commit()


def _migrate_users_for_students(db):
    columns = db.execute("PRAGMA table_info(users)").fetchall()
    col_names = {col[1] for col in columns}
    table_sql_row = db.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'").fetchone()
    table_sql = (table_sql_row[0] or "") if table_sql_row else ""

    needs_rebuild = ("student_id" not in col_names) or ("'student'" not in table_sql)
    if not needs_rebuild:
        return

    db.execute("ALTER TABLE users RENAME TO users_old")
    db.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('teacher', 'admin', 'student')),
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            student_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    old_columns = db.execute("PRAGMA table_info(users_old)").fetchall()
    old_col_names = {col[1] for col in old_columns}
    if "student_id" in old_col_names:
        db.execute(
            """
            INSERT INTO users (id, name, role, username, password_hash, student_id, created_at)
            SELECT id, name, role, username, password_hash, student_id, created_at
            FROM users_old
            """
        )
    else:
        db.execute(
            """
            INSERT INTO users (id, name, role, username, password_hash, created_at)
            SELECT id, name, role, username, password_hash, created_at
            FROM users_old
            """
        )
    db.execute("DROP TABLE users_old")


def _migrate_attendance_for_subjects(db):
    columns = db.execute("PRAGMA table_info(attendance)").fetchall()
    col_names = {col[1] for col in columns}

    if "subject" in col_names:
        return

    db.execute("ALTER TABLE attendance RENAME TO attendance_old")
    db.execute(
        """
        CREATE TABLE attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT 'General',
            status TEXT NOT NULL CHECK (status IN ('present', 'absent', 'late')),
            mode TEXT NOT NULL CHECK (mode IN ('manual', 'face', 'unique_id', 'qr')),
            unique_id_done INTEGER NOT NULL DEFAULT 0,
            face_done INTEGER NOT NULL DEFAULT 0,
            qr_done INTEGER NOT NULL DEFAULT 0,
            timestamp TEXT NOT NULL,
            synced INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(student_id, date, subject)
        )
        """
    )
    db.execute(
        """
        INSERT INTO attendance (id, student_id, date, subject, status, mode, unique_id_done, face_done, qr_done, timestamp, synced, note)
        SELECT
            id,
            student_id,
            date,
            'General',
            status,
            CASE WHEN mode = 'rfid' THEN 'unique_id' ELSE mode END,
            CASE WHEN mode IN ('unique_id', 'rfid') THEN 1 ELSE 0 END,
            CASE WHEN mode = 'face' THEN 1 ELSE 0 END,
            CASE WHEN mode = 'qr' THEN 1 ELSE 0 END,
            timestamp,
            synced,
            note
        FROM attendance_old
        """
    )
    db.execute("DROP TABLE attendance_old")


def _migrate_attendance_for_verification_flags(db):
    columns = db.execute("PRAGMA table_info(attendance)").fetchall()
    col_names = {col[1] for col in columns}

    if "unique_id_done" not in col_names:
        if "rfid_done" in col_names:
            db.execute("ALTER TABLE attendance RENAME COLUMN rfid_done TO unique_id_done")
        else:
            db.execute("ALTER TABLE attendance ADD COLUMN unique_id_done INTEGER NOT NULL DEFAULT 0")
    if "face_done" not in col_names:
        db.execute("ALTER TABLE attendance ADD COLUMN face_done INTEGER NOT NULL DEFAULT 0")
    if "qr_done" not in col_names:
        db.execute("ALTER TABLE attendance ADD COLUMN qr_done INTEGER NOT NULL DEFAULT 0")

    db.execute("UPDATE attendance SET unique_id_done = CASE WHEN mode IN ('unique_id', 'rfid') THEN 1 ELSE unique_id_done END")
    db.execute("UPDATE attendance SET face_done = CASE WHEN mode = 'face' THEN 1 ELSE face_done END")
    db.execute("UPDATE attendance SET qr_done = CASE WHEN mode = 'qr' THEN 1 ELSE qr_done END")
    db.execute(
        """
        UPDATE attendance
        SET status = CASE
            WHEN unique_id_done = 1 AND face_done = 1 AND qr_done = 1 THEN 'present'
            ELSE 'absent'
        END
        WHERE mode IN ('unique_id', 'rfid', 'face', 'qr')
        """
    )


def _migrate_students_class_to_section(db):
    columns = db.execute("PRAGMA table_info(students)").fetchall()
    col_names = {col[1] for col in columns}

    if "section_name" in col_names:
        return

    if "class_name" in col_names:
        db.execute("ALTER TABLE students RENAME COLUMN class_name TO section_name")


def _migrate_unique_id_naming(db):
    student_columns = db.execute("PRAGMA table_info(students)").fetchall()
    student_col_names = {col[1] for col in student_columns}
    if "unique_id" not in student_col_names and "rfid_tag" in student_col_names:
        db.execute("ALTER TABLE students RENAME COLUMN rfid_tag TO unique_id")

    attendance_columns = db.execute("PRAGMA table_info(attendance)").fetchall()
    attendance_col_names = {col[1] for col in attendance_columns}
    if "unique_id_done" not in attendance_col_names and "rfid_done" in attendance_col_names:
        db.execute("ALTER TABLE attendance RENAME COLUMN rfid_done TO unique_id_done")

    table_sql_row = db.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'attendance'").fetchone()
    table_sql = (table_sql_row[0] or "") if table_sql_row else ""
    needs_mode_rebuild = "'unique_id'" not in table_sql

    if needs_mode_rebuild:
        db.execute("ALTER TABLE attendance RENAME TO attendance_old_unique_id")
        old_columns = db.execute("PRAGMA table_info(attendance_old_unique_id)").fetchall()
        old_col_names = {col[1] for col in old_columns}

        unique_done_expr = "unique_id_done"
        if "unique_id_done" not in old_col_names:
            unique_done_expr = "rfid_done" if "rfid_done" in old_col_names else "CASE WHEN mode IN ('unique_id', 'rfid') THEN 1 ELSE 0 END"

        db.execute(
            """
            CREATE TABLE attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                subject TEXT NOT NULL DEFAULT 'General',
                status TEXT NOT NULL CHECK (status IN ('present', 'absent', 'late')),
                mode TEXT NOT NULL CHECK (mode IN ('manual', 'face', 'unique_id', 'qr')),
                unique_id_done INTEGER NOT NULL DEFAULT 0,
                face_done INTEGER NOT NULL DEFAULT 0,
                qr_done INTEGER NOT NULL DEFAULT 0,
                timestamp TEXT NOT NULL,
                synced INTEGER NOT NULL DEFAULT 0,
                note TEXT,
                FOREIGN KEY (student_id) REFERENCES students(id),
                UNIQUE(student_id, date, subject)
            )
            """
        )
        db.execute(
            f"""
            INSERT INTO attendance (id, student_id, date, subject, status, mode, unique_id_done, face_done, qr_done, timestamp, synced, note)
            SELECT
                id,
                student_id,
                date,
                subject,
                status,
                CASE WHEN mode = 'rfid' THEN 'unique_id' ELSE mode END,
                {unique_done_expr},
                face_done,
                qr_done,
                timestamp,
                synced,
                note
            FROM attendance_old_unique_id
            """
        )
        db.execute("DROP TABLE attendance_old_unique_id")
    else:
        db.execute("UPDATE attendance SET mode = 'unique_id' WHERE mode = 'rfid'")

