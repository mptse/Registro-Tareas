"""Aplicación local de tareas privadas."""

import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,30}$")


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or os.environ.get("SESSION_SECRET"),
        DATABASE=os.path.join(app.instance_path, "tasks.sqlite3"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,  # La aplicación se ejecuta localmente sobre HTTP.
        MAX_CONTENT_LENGTH=1 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    secret_key = app.config.get("SECRET_KEY")
    if not isinstance(secret_key, str) or len(secret_key) < 32:
        raise RuntimeError(
            "Configura FLASK_SECRET_KEY con al menos 32 caracteres aleatorios "
            "antes de iniciar (consulta README.md)."
        )

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    init_db(app)

    @app.before_request
    def load_user_and_check_csrf():
        g.user = None
        user_id = session.get("user_id")
        if user_id is not None:
            g.user = get_db().execute(
                "SELECT id, username FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if g.user is None:
                session.clear()

        if request.method == "POST":
            submitted = request.form.get("csrf_token", "")
            expected = session.get("_csrf_token", "")
            if not expected or not submitted or not hmac.compare_digest(
                submitted, expected
            ):
                abort(400, description="La solicitud no superó la validación de seguridad.")

    @app.context_processor
    def csrf_context():
        return {"csrf_token": csrf_token}

    @app.get("/")
    def index():
        if g.user is None:
            return redirect(url_for("login"))
        status = request.args.get("estado", "todas")
        if status not in {"todas", "pendientes", "completadas"}:
            status = "todas"
        query = "SELECT * FROM tasks WHERE user_id = ?"
        if status == "pendientes":
            query += " AND completed = 0"
        elif status == "completadas":
            query += " AND completed = 1"
        tasks = get_db().execute(
            query + " ORDER BY completed ASC, updated_at DESC, id DESC",
            (g.user["id"],),
        ).fetchall()
        return render_template("index.html", tasks=tasks, status=status)

    @app.route("/registro", methods=["GET", "POST"])
    def register():
        if g.user is not None:
            return redirect(url_for("index"))
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            error = None
            if not USERNAME_RE.fullmatch(username):
                error = "El usuario debe tener entre 3 y 30 caracteres: letras, números o _."
            elif len(password) < 10:
                error = "La contraseña debe tener al menos 10 caracteres."
            elif len(password) > 256:
                error = "La contraseña es demasiado larga."
            if error is None:
                try:
                    cursor = get_db().execute(
                        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                        (username, generate_password_hash(password), utc_now()),
                    )
                    get_db().commit()
                except sqlite3.IntegrityError:
                    get_db().rollback()
                    error = "Ese nombre de usuario ya está registrado."
                else:
                    session.clear()
                    session["user_id"] = cursor.lastrowid
                    flash("Tu cuenta se creó correctamente.", "success")
                    return redirect(url_for("index"))
            flash(error, "error")
        return render_template("register.html")

    @app.route("/iniciar-sesion", methods=["GET", "POST"])
    def login():
        if g.user is not None:
            return redirect(url_for("index"))
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            user = get_db().execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            if user is None or not check_password_hash(user["password_hash"], password):
                flash("Usuario o contraseña incorrectos.", "error")
            else:
                session.clear()
                session["user_id"] = user["id"]
                flash("Has iniciado sesión.", "success")
                return redirect(url_for("index"))
        return render_template("login.html")

    @app.post("/cerrar-sesion")
    @login_required
    def logout():
        session.clear()
        flash("Has cerrado sesión.", "success")
        return redirect(url_for("login"))

    @app.route("/tareas/nueva", methods=["GET", "POST"])
    @login_required
    def create_task():
        if request.method == "POST":
            title, description, error = validate_task_form()
            if error:
                flash(error, "error")
            else:
                now = utc_now()
                get_db().execute(
                    """INSERT INTO tasks
                       (user_id, title, description, completed, created_at, updated_at)
                       VALUES (?, ?, ?, 0, ?, ?)""",
                    (g.user["id"], title, description, now, now),
                )
                get_db().commit()
                flash("Tarea creada.", "success")
                return redirect(url_for("index"))
        return render_template(
            "task_form.html",
            task=None,
            heading="Nueva tarea",
            form_title=request.form.get("title", ""),
            form_description=request.form.get("description", ""),
        )

    @app.route("/tareas/<int:task_id>/editar", methods=["GET", "POST"])
    @login_required
    def edit_task(task_id):
        task = owned_task(task_id)
        if request.method == "POST":
            title, description, error = validate_task_form()
            if error:
                flash(error, "error")
            else:
                get_db().execute(
                    """UPDATE tasks SET title = ?, description = ?, updated_at = ?
                       WHERE id = ? AND user_id = ?""",
                    (title, description, utc_now(), task_id, g.user["id"]),
                )
                get_db().commit()
                flash("Tarea actualizada.", "success")
                return redirect(url_for("index"))
        return render_template(
            "task_form.html",
            task=task,
            heading="Editar tarea",
            form_title=request.form.get("title", task["title"]),
            form_description=request.form.get("description", task["description"]),
        )

    @app.post("/tareas/<int:task_id>/estado")
    @login_required
    def toggle_task(task_id):
        task = owned_task(task_id)
        get_db().execute(
            """UPDATE tasks SET completed = ?, updated_at = ?
               WHERE id = ? AND user_id = ?""",
            (0 if task["completed"] else 1, utc_now(), task_id, g.user["id"]),
        )
        get_db().commit()
        flash("Estado de la tarea actualizado.", "success")
        return redirect(url_for("index"))

    @app.post("/tareas/<int:task_id>/eliminar")
    @login_required
    def delete_task(task_id):
        owned_task(task_id)
        get_db().execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, g.user["id"]),
        )
        get_db().commit()
        flash("Tarea eliminada.", "success")
        return redirect(url_for("index"))

    @app.teardown_appcontext
    def close_db(_exception=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    return app


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app_config_database())
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def current_app_config_database():
    from flask import current_app

    return current_app.config["DATABASE"]


def init_db(app):
    db = sqlite3.connect(app.config["DATABASE"])
    try:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_owner_updated
                ON tasks(user_id, updated_at DESC);
            """
        )
        db.commit()
    finally:
        db.close()


def csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


def owned_task(task_id):
    task = get_db().execute(
        "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, g.user["id"]),
    ).fetchone()
    if task is None:
        abort(404)
    return task


def validate_task_form():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    if not title:
        return title, description, "El título es obligatorio."
    if len(title) > 120:
        return title, description, "El título no puede superar 120 caracteres."
    if len(description) > 2000:
        return title, description, "La descripción no puede superar 2000 caracteres."
    return title, description, None


if __name__ == "__main__":
    create_app().run(debug=False)
