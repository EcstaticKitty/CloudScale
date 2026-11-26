import os
from datetime import timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask, flash, redirect, render_template,
    request, session, url_for
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)

secret_key = os.getenv("SECRET_KEY")
if not secret_key:
    raise RuntimeError("SECRET_KEY is not configured")

app.config.update(
    SECRET_KEY=secret_key,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    MAX_CONTENT_LENGTH=1 * 1024 * 1024,
)

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is not configured")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url

db = SQLAlchemy(app)
csrf = CSRFProtect(app)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)


class Task(db.Model):
    # Flask-SQLAlchemy originally named this table "task" automatically.
    # Keep that name so the existing data remains in place.
    __tablename__ = "task"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, nullable=False, default=False)
    # Nullable only to preserve legacy tasks created before user accounts existed.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in to open your workspace.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


@app.route("/", methods=["GET"])
@login_required
def index():
    tasks = (Task.query
             .filter_by(user_id=session["user_id"])
             .order_by(Task.id.desc())
             .all())
    completed_count = sum(1 for task in tasks if task.completed)
    total_count = len(tasks)
    return render_template(
        "index.html",
        tasks=tasks,
        username=session.get("username", "there"),
        total_count=total_count,
        completed_count=completed_count,
        active_count=total_count - completed_count,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(username) < 3 or len(username) > 80:
            flash("Choose a username between 3 and 80 characters.", "error")
        elif len(password) < 8:
            flash("Your password must be at least 8 characters long.", "error")
        elif password != confirm_password:
            flash("The passwords do not match.", "error")
        elif User.query.filter(func.lower(User.username) == username.lower()).first():
            flash("That username is already taken. Try another one.", "error")
        else:
            user = User(
                username=username,
                password_hash=generate_password_hash(password)
            )
            db.session.add(user)
            db.session.commit()
            flash("Account created. Sign in to open your workspace.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(func.lower(User.username) == username.lower()).first()

        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session.permanent = True
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("index"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been signed out. Take it slow.", "success")
    return redirect(url_for("login"))


@app.route("/add", methods=["POST"])
@login_required
def add_task():
    title = request.form.get("title", "").strip()
    if not title:
        flash("Write a note before adding it.", "error")
    elif len(title) > 200:
        flash("Keep each note under 200 characters.", "error")
    else:
        db.session.add(Task(title=title, user_id=session["user_id"], completed=False))
        db.session.commit()
    return redirect(url_for("index"))


@app.route("/toggle/<int:task_id>", methods=["POST"])
@login_required
def toggle_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=session["user_id"]).first_or_404()
    task.completed = not task.completed
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/delete/<int:task_id>", methods=["POST"])
@login_required
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=session["user_id"]).first_or_404()
    db.session.delete(task)
    db.session.commit()
    flash("Note deleted.", "success")
    return redirect(url_for("index"))


# Creates missing tables. Existing-table schema changes are handled by migration.sql.
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
