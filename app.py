from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from functools import wraps
from datetime import datetime
from pathlib import Path
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-antes-de-publicar")
DB_PATH = Path(__file__).with_name("eventmanager.db")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','student'))
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_time TEXT NOT NULL,
            location TEXT NOT NULL,
            capacity INTEGER NOT NULL CHECK(capacity > 0),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            attended INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, event_id)
        );
        """)
        if not con.execute("SELECT id FROM users WHERE email = ?", ("admin@eventmanager.local",)).fetchone():
            con.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                        ("Administrador", "admin@eventmanager.local",
                         generate_password_hash("Admin123!"), "admin"))
        if not con.execute("SELECT id FROM users WHERE email = ?", ("aluno@eventmanager.local",)).fetchone():
            con.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                        ("Aluno Demonstração", "aluno@eventmanager.local",
                         generate_password_hash("Aluno123!"), "student"))

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_user():
    return {"current_user": session.get("name"), "current_role": session.get("role")}

@app.route("/")
def index():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            return redirect(url_for("dashboard"))
        flash("E-mail ou senha incorretos.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 6:
            flash("Preencha os campos. A senha deve ter pelo menos 6 caracteres.", "error")
        else:
            try:
                with db() as con:
                    con.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                                (name, email, generate_password_hash(password), "student"))
                flash("Conta criada! Faça login para continuar.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Este e-mail já está cadastrado.", "error")
    return render_template("register.html")

@app.route("/dashboard")
@login_required
def dashboard():
    with db() as con:
        total_events = con.execute("SELECT COUNT(*) n FROM events").fetchone()["n"]
        total_regs = con.execute("SELECT COUNT(*) n FROM registrations").fetchone()["n"]
        upcoming = con.execute("""
            SELECT e.*, COUNT(r.id) enrolled FROM events e
            LEFT JOIN registrations r ON r.event_id=e.id
            WHERE e.event_date >= date('now','localtime')
            GROUP BY e.id ORDER BY e.event_date,e.event_time LIMIT 5
        """).fetchall()
        my_regs = con.execute("""
            SELECT e.*,r.attended FROM registrations r JOIN events e ON e.id=r.event_id
            WHERE r.user_id=? ORDER BY e.event_date,e.event_time
        """, (session["user_id"],)).fetchall()
    return render_template("dashboard.html", total_events=total_events,
                           total_regs=total_regs, upcoming=upcoming, my_regs=my_regs)

@app.route("/events")
@login_required
def events():
    q = request.args.get("q", "").strip()
    with db() as con:
        rows = con.execute("""
            SELECT e.*, COUNT(r.id) enrolled FROM events e
            LEFT JOIN registrations r ON r.event_id=e.id
            WHERE e.title LIKE ? OR e.description LIKE ? OR e.location LIKE ?
            GROUP BY e.id ORDER BY e.event_date,e.event_time
        """, (f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    return render_template("events.html", events=rows, q=q)

@app.route("/events/new", methods=["GET", "POST"])
@login_required
@admin_required
def event_new():
    if request.method == "POST":
        data = [request.form.get(k, "").strip() for k in
                ("title", "description", "event_date", "event_time", "location")]
        try:
            capacity = int(request.form.get("capacity", "0"))
            if not all(data) or capacity < 1:
                raise ValueError
            with db() as con:
                con.execute("""INSERT INTO events(title,description,event_date,event_time,location,capacity)
                               VALUES(?,?,?,?,?,?)""", (*data, capacity))
            flash("Evento cadastrado com sucesso.", "success")
            return redirect(url_for("events"))
        except ValueError:
            flash("Confira os campos e informe um limite de vagas maior que zero.", "error")
    return render_template("event_form.html", event=None)

@app.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def event_edit(event_id):
    with db() as con:
        event = con.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    if not event:
        abort(404)
    if request.method == "POST":
        data = [request.form.get(k, "").strip() for k in
                ("title", "description", "event_date", "event_time", "location")]
        try:
            capacity = int(request.form.get("capacity", "0"))
            with db() as con:
                enrolled = con.execute("SELECT COUNT(*) n FROM registrations WHERE event_id=?",
                                       (event_id,)).fetchone()["n"]
                if not all(data) or capacity < 1 or capacity < enrolled:
                    raise ValueError
                con.execute("""UPDATE events SET title=?,description=?,event_date=?,event_time=?,
                               location=?,capacity=? WHERE id=?""", (*data, capacity, event_id))
            flash("Evento atualizado.", "success")
            return redirect(url_for("events"))
        except ValueError:
            flash("Dados inválidos. O limite não pode ser menor que o número de inscritos.", "error")
    return render_template("event_form.html", event=event)

@app.route("/events/<int:event_id>/delete", methods=["POST"])
@login_required
@admin_required
def event_delete(event_id):
    with db() as con:
        con.execute("DELETE FROM events WHERE id=?", (event_id,))
    flash("Evento removido.", "success")
    return redirect(url_for("events"))

@app.route("/events/<int:event_id>/join", methods=["POST"])
@login_required
def join_event(event_id):
    with db() as con:
        event = con.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        if not event:
            abort(404)
        enrolled = con.execute("SELECT COUNT(*) n FROM registrations WHERE event_id=?",
                               (event_id,)).fetchone()["n"]
        exists = con.execute("SELECT id FROM registrations WHERE user_id=? AND event_id=?",
                             (session["user_id"], event_id)).fetchone()
        if exists:
            flash("Você já está inscrito neste evento.", "error")
        elif enrolled >= event["capacity"]:
            flash("As vagas deste evento já foram preenchidas.", "error")
        else:
            con.execute("INSERT INTO registrations(user_id,event_id) VALUES(?,?)",
                        (session["user_id"], event_id))
            flash("Inscrição realizada com sucesso.", "success")
    return redirect(request.referrer or url_for("events"))

@app.route("/events/<int:event_id>/participants")
@login_required
@admin_required
def participants(event_id):
    with db() as con:
        event = con.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        people = con.execute("""
            SELECT r.id registration_id,r.attended,u.name,u.email
            FROM registrations r JOIN users u ON u.id=r.user_id
            WHERE r.event_id=? ORDER BY u.name
        """, (event_id,)).fetchall()
    if not event:
        abort(404)
    return render_template("participants.html", event=event, people=people)

@app.route("/registrations/<int:registration_id>/attendance", methods=["POST"])
@login_required
@admin_required
def attendance(registration_id):
    with db() as con:
        con.execute("UPDATE registrations SET attended=CASE attended WHEN 1 THEN 0 ELSE 1 END WHERE id=?",
                    (registration_id,))
    return redirect(request.referrer or url_for("dashboard"))

@app.route("/certificates")
@login_required
def certificates():
    with db() as con:
        rows = con.execute("""
            SELECT e.title,e.event_date,e.location,r.attended,u.name
            FROM registrations r JOIN events e ON e.id=r.event_id
            JOIN users u ON u.id=r.user_id
            WHERE r.user_id=? AND r.attended=1 ORDER BY e.event_date DESC
        """, (session["user_id"],)).fetchall()
    return render_template("certificates.html", certificates=rows)

@app.errorhandler(403)
def forbidden(_):
    return render_template("message.html", title="Acesso não permitido",
                           message="Esta área é exclusiva para administradores."), 403

@app.errorhandler(404)
def not_found(_):
    return render_template("message.html", title="Página não encontrada",
                           message="O conteúdo solicitado não foi encontrado."), 404

init_db()
if __name__ == "__main__":
    app.run(debug=True)