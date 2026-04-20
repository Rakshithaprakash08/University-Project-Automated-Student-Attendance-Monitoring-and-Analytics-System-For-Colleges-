from pathlib import Path
import os

from flask import Flask
from werkzeug.security import generate_password_hash

from .attendance_routes import attendance_bp
from .auth import auth_bp
from .db import close_db, ensure_db_initialized, get_db
from .reports import reports_bp
from .students import students_bp
from .sync_routes import sync_bp



def create_app():
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )

    app.config.from_mapping(
        SECRET_KEY="change-me-in-production",
        DB_PATH=str(Path(app.instance_path) / "attendance.db"),
        UPLOAD_DIR=str(Path(app.root_path).parent / "uploads" / "students"),
        REMOTE_SYNC_URL=os.getenv("REMOTE_SYNC_URL", ""),
        SCHOOL_CODE=os.getenv("SCHOOL_CODE", "RURAL-SCHOOL-001"),
        ENABLE_AI_MODULE=os.getenv("ENABLE_AI_MODULE", "false").lower() == "true",
        PUBLIC_BASE_URL=os.getenv("PUBLIC_BASE_URL", ""),
    )

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)

    app.teardown_appcontext(close_db)

    with app.app_context():
        ensure_db_initialized()
        _ensure_default_admin()

    app.register_blueprint(auth_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(sync_bp)

    @app.route("/")
    def index():
        from flask import redirect, session, url_for

        if session.get("user_id"):
            return redirect(url_for("attendance.dashboard"))
        return redirect(url_for("auth.login"))

    return app


def _ensure_default_admin():
    db = get_db()
    user = db.execute("SELECT id FROM users WHERE username = ?", ("admin",)).fetchone()
    if not user:
        db.execute(
            "INSERT INTO users (name, role, username, password_hash) VALUES (?, ?, ?, ?)",
            ("System Admin", "admin", "admin", generate_password_hash("admin123")),
        )
        db.execute(
            "INSERT INTO users (name, role, username, password_hash) VALUES (?, ?, ?, ?)",
            ("Teacher", "teacher", "teacher", generate_password_hash("teacher123")),
        )
        db.commit()

    # Keep the built-in teacher account label consistent in User Management.
    db.execute(
        "UPDATE users SET name = ? WHERE username = ? AND role = ?",
        ("Teacher", "teacher", "teacher"),
    )
    db.commit()
