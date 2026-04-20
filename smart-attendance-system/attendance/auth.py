from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .security import login_required, role_required

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    return _login_impl(allowed_roles={"teacher", "admin"}, template_name="login.html")


@auth_bp.route("/student-login", methods=["GET", "POST"])
def student_login():
    return _login_impl(allowed_roles={"student"}, template_name="student_login.html")


def _login_impl(allowed_roles, template_name):
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid credentials", "error")
            return render_template(template_name)

        if user["role"] not in allowed_roles:
            flash("Access denied for this login portal", "error")
            return render_template(template_name)

        session.clear()
        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        session["student_id"] = user["student_id"]
        return redirect(url_for("attendance.dashboard"))

    return render_template(template_name)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/users", methods=["GET", "POST"])
@login_required
@role_required("admin")
def users():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "teacher").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if role not in {"teacher", "admin"}:
            flash("Invalid role selected", "error")
            return redirect(url_for("auth.users"))

        if not all([name, role, username, password]):
            flash("All fields are required", "error")
        else:
            try:
                db.execute(
                    "INSERT INTO users (name, role, username, password_hash) VALUES (?, ?, ?, ?)",
                    (name, role, username, generate_password_hash(password)),
                )
                db.commit()
                flash("User created", "success")
            except Exception:
                flash("Username already exists", "error")

    users_list = db.execute(
        """
        SELECT id, name, role, username, created_at
        FROM users
        WHERE role IN ('admin', 'teacher')
        ORDER BY id DESC
        """
    ).fetchall()
    return render_template("users.html", users=users_list)
