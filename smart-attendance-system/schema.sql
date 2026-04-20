DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS attendance;
DROP TABLE IF EXISTS sync_queue;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('teacher', 'admin', 'student')),
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    student_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    class_name TEXT NOT NULL,
    section TEXT,
    photo_path TEXT,
    photo_encoding TEXT,
    unique_id TEXT UNIQUE,
    guardian_phone TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

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
);

CREATE TABLE sync_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('insert', 'update', 'delete')),
    payload TEXT,
    queued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_attendance_date ON attendance(date);
CREATE INDEX idx_attendance_synced ON attendance(synced);
CREATE INDEX idx_students_class ON students(class_name);

