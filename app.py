from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, g
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import re
from contextlib import contextmanager
from functools import wraps
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
import os
import secrets

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-antes-de-publicar")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
ADMIN_CODE = os.environ.get("ADMIN_CODE", "")
DEMO_ACCOUNTS = os.environ.get("DEMO_ACCOUNTS", "1") != "0"
DB_PATH = Path(__file__).with_name("eventmanager.db")

CATEGORIES = ["Palestra", "Workshop", "Curso", "Esporte", "Cultura", "Feira", "Outro"]
CATEGORY_ICONS = {"Palestra": "🎤", "Workshop": "🛠️", "Curso": "📚", "Esporte": "⚽",
                  "Cultura": "🎭", "Feira": "🛍️", "Outro": "✨"}
MONTHS = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

EVENT_SELECT = """
    SELECT e.*,
           (SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id) AS enrolled,
           (SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id AND r.attended = 1) AS present,
           EXISTS(SELECT 1 FROM registrations r WHERE r.event_id = e.id AND r.user_id = :uid) AS joined,
           (SELECT r.attended FROM registrations r WHERE r.event_id = e.id AND r.user_id = :uid) AS my_attended
    FROM events e
"""

# ---------------------------------------------------------------- banco de dados

@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def ensure_user(con, name, email, password, role):
    if not con.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
        con.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                    (name, email, generate_password_hash(password), role))

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
            category TEXT NOT NULL DEFAULT 'Outro',
            cover_url TEXT NOT NULL DEFAULT '',
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
        CREATE INDEX IF NOT EXISTS idx_registrations_event ON registrations(event_id);
        """)
        # Atualiza bancos antigos (criados antes das categorias e das capas)
        columns = [row["name"] for row in con.execute("PRAGMA table_info(events)")]
        if "category" not in columns:
            con.execute("ALTER TABLE events ADD COLUMN category TEXT NOT NULL DEFAULT 'Outro'")
        if "cover_url" not in columns:
            con.execute("ALTER TABLE events ADD COLUMN cover_url TEXT NOT NULL DEFAULT ''")
        if DEMO_ACCOUNTS:
            ensure_user(con, "Administrador", "admin@eventmanager.local", "Admin123!", "admin")
            ensure_user(con, "Aluno Demonstração", "aluno@eventmanager.local", "Aluno123!", "student")

# ---------------------------------------------------------------- utilidades

def today():
    return date.today().isoformat()

def like_pattern(text):
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"

def safe_back(default_endpoint):
    ref = request.referrer
    if ref and urlparse(ref).netloc == request.host:
        return redirect(ref)
    return redirect(url_for(default_endpoint))

def current_user_row():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with db() as con:
        return con.execute("SELECT id,name,email,role FROM users WHERE id = ?", (user_id,)).fetchone()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user_row()
        if not user:
            session.clear()
            return redirect(url_for("login"))
        g.user = user
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if g.user["role"] != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

def fetch_events(con, where="", params=None, order="e.event_date, e.event_time"):
    values = dict(params or {})
    values["uid"] = g.user["id"]
    sql = EVENT_SELECT + (" WHERE " + where if where else "") + " ORDER BY " + order
    return con.execute(sql, values).fetchall()

def parse_event_form():
    form = request.form
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()
    event_date = form.get("event_date", "").strip()
    event_time = form.get("event_time", "").strip()
    location = form.get("location", "").strip()
    cover_url = form.get("cover_url", "").strip()
    category = form.get("category", "Outro")
    if category not in CATEGORIES:
        category = "Outro"
    if not (title and description and location):
        return None, "Preencha o nome, a descrição e o local do evento."
    if len(title) > 120 or len(location) > 120 or len(description) > 2000:
        return None, "Algum texto está grande demais (nome e local: até 120 caracteres; descrição: até 2000)."
    try:
        datetime.strptime(event_date, "%Y-%m-%d")
        datetime.strptime(event_time, "%H:%M")
    except ValueError:
        return None, "Informe uma data e um horário válidos."
    try:
        capacity = int(form.get("capacity", "0"))
    except ValueError:
        capacity = 0
    if not 1 <= capacity <= 100000:
        return None, "Informe um limite de vagas entre 1 e 100000."
    if cover_url and (len(cover_url) > 500 or not re.match(r"^https?://\S+$", cover_url)):
        return None, "O link da imagem de capa deve começar com http:// ou https://."
    return {"title": title, "description": description, "event_date": event_date,
            "event_time": event_time, "location": location, "capacity": capacity,
            "category": category, "cover_url": cover_url}, None

def admin_overview(con):
    totals = con.execute("""
        SELECT (SELECT COUNT(*) FROM events) AS events,
               (SELECT COUNT(*) FROM registrations) AS regs,
               (SELECT COUNT(*) FROM users WHERE role = 'student') AS students,
               (SELECT COUNT(*) FROM registrations WHERE attended = 1) AS present
    """).fetchone()
    rate = round(totals["present"] * 100 / totals["regs"]) if totals["regs"] else 0

    rows = con.execute("SELECT category, COUNT(*) AS n FROM events GROUP BY category ORDER BY n DESC").fetchall()
    biggest = max([r["n"] for r in rows], default=1)
    by_category = [{"label": r["category"], "value": r["n"], "pct": round(r["n"] * 100 / biggest)} for r in rows]

    days = [date.today() - timedelta(days=i) for i in range(6, -1, -1)]
    counts = {r["d"]: r["n"] for r in con.execute(
        "SELECT substr(registered_at, 1, 10) AS d, COUNT(*) AS n FROM registrations "
        "WHERE registered_at >= ? GROUP BY d", (days[0].isoformat(),))}
    peak = max([counts.get(d.isoformat(), 0) for d in days] + [1])
    last7 = [{"label": d.strftime("%d/%m"), "value": counts.get(d.isoformat(), 0),
              "pct": round(counts.get(d.isoformat(), 0) * 100 / peak)} for d in days]
    return {"events": totals["events"], "regs": totals["regs"], "students": totals["students"],
            "rate": rate, "by_category": by_category, "last7": last7}

# ---------------------------------------------------------------- filtros e contexto

@app.template_filter("br_date")
def br_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return value or ""

@app.template_filter("month_short")
def month_short(value):
    try:
        return MONTHS[int(value[5:7]) - 1]
    except (TypeError, ValueError, IndexError):
        return ""

@app.context_processor
def inject_globals():
    user = getattr(g, "user", None) or current_user_row()
    return {"current_user": user["name"] if user else None,
            "current_role": user["role"] if user else None,
            "CATEGORIES": CATEGORIES, "CATEGORY_ICONS": CATEGORY_ICONS, "today": today()}

# ---------------------------------------------------------------- acesso

@app.route("/")
def index():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user_row():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        flash("E-mail ou senha incorretos.", "error")
    return render_template("login.html", demo_enabled=DEMO_ACCOUNTS)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user_row():
        return redirect(url_for("dashboard"))
    admin_enabled = bool(ADMIN_CODE)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")
        admin_code = request.form.get("admin_code", "").strip()
        role = "student"
        if admin_code:
            if ADMIN_CODE and secrets.compare_digest(admin_code.encode(), ADMIN_CODE.encode()):
                role = "admin"
            else:
                flash("Código de administrador inválido.", "error")
                return render_template("register.html", admin_enabled=admin_enabled)
        if not 2 <= len(name) <= 100:
            flash("Informe seu nome completo (de 2 a 100 caracteres).", "error")
        elif not EMAIL_RE.match(email) or len(email) > 150:
            flash("Informe um e-mail válido.", "error")
        elif not 6 <= len(password) <= 128:
            flash("A senha deve ter entre 6 e 128 caracteres.", "error")
        elif password != password2:
            flash("As senhas digitadas não são iguais.", "error")
        else:
            try:
                with db() as con:
                    con.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                                (name, email, generate_password_hash(password), role))
                flash("Conta de administrador criada! Faça login para continuar." if role == "admin"
                      else "Conta criada! Faça login para continuar.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Este e-mail já está cadastrado.", "error")
    return render_template("register.html", admin_enabled=admin_enabled)

# ---------------------------------------------------------------- painel

@app.route("/dashboard")
@login_required
def dashboard():
    with db() as con:
        if g.user["role"] == "admin":
            upcoming = fetch_events(con, "e.event_date >= :today", {"today": today()})[:6]
            occupancy = [{"title": e["title"], "enrolled": e["enrolled"], "capacity": e["capacity"],
                          "pct": min(100, round(e["enrolled"] * 100 / e["capacity"]))} for e in upcoming]
            return render_template("dashboard.html", stats=admin_overview(con),
                                   upcoming=upcoming, occupancy=occupancy)
        mine = fetch_events(con, "EXISTS (SELECT 1 FROM registrations r WHERE r.event_id = e.id "
                                 "AND r.user_id = :uid)")
    mine_upcoming = [e for e in mine if e["event_date"] >= today()]
    mine_past = [e for e in mine if e["event_date"] < today()][::-1]
    summary = {"active": len(mine_upcoming), "total": len(mine),
               "present": sum(1 for e in mine if e["my_attended"])}
    return render_template("dashboard.html", mine_upcoming=mine_upcoming,
                           mine_past=mine_past, summary=summary)

# ---------------------------------------------------------------- eventos

@app.route("/events")
@login_required
def events():
    q = request.args.get("q", "").strip()[:100]
    category = request.args.get("category", "")
    period = request.args.get("period", "all")
    clauses, params = [], {}
    if q:
        clauses.append("(e.title LIKE :q ESCAPE '\\' OR e.description LIKE :q ESCAPE '\\' "
                       "OR e.location LIKE :q ESCAPE '\\')")
        params["q"] = like_pattern(q)
    if category in CATEGORIES:
        clauses.append("e.category = :category")
        params["category"] = category
    else:
        category = ""
    if period == "upcoming":
        clauses.append("e.event_date >= :today")
        params["today"] = today()
    elif period == "past":
        clauses.append("e.event_date < :today")
        params["today"] = today()
    else:
        period = "all"
    order = "e.event_date DESC, e.event_time DESC" if period == "past" else "e.event_date, e.event_time"
    with db() as con:
        rows = fetch_events(con, " AND ".join(clauses), params, order)
    return render_template("events.html", events=rows, q=q, category=category, period=period)

@app.route("/events/new", methods=["GET", "POST"])
@login_required
@admin_required
def event_new():
    if request.method == "POST":
        data, error = parse_event_form()
        if not error:
            with db() as con:
                con.execute("""INSERT INTO events(title,description,event_date,event_time,location,
                                                  capacity,category,cover_url)
                               VALUES(:title,:description,:event_date,:event_time,:location,
                                      :capacity,:category,:cover_url)""", data)
            flash("Evento cadastrado com sucesso.", "success")
            return redirect(url_for("events"))
        flash(error, "error")
        return render_template("event_form.html", event=None, values=request.form)
    return render_template("event_form.html", event=None, values={})

@app.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def event_edit(event_id):
    with db() as con:
        event = con.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        abort(404)
    if request.method == "POST":
        data, error = parse_event_form()
        if not error:
            with db() as con:
                enrolled = con.execute("SELECT COUNT(*) AS n FROM registrations WHERE event_id = ?",
                                       (event_id,)).fetchone()["n"]
                if data["capacity"] < enrolled:
                    error = f"O limite de vagas não pode ser menor que o número de inscritos ({enrolled})."
                else:
                    con.execute("""UPDATE events SET title=:title, description=:description,
                                   event_date=:event_date, event_time=:event_time, location=:location,
                                   capacity=:capacity, category=:category, cover_url=:cover_url
                                   WHERE id=:id""", {**data, "id": event_id})
            if not error:
                flash("Evento atualizado.", "success")
                return redirect(url_for("events"))
        flash(error, "error")
        return render_template("event_form.html", event=event, values=request.form)
    return render_template("event_form.html", event=event, values=dict(event))

@app.route("/events/<int:event_id>/delete", methods=["POST"])
@login_required
@admin_required
def event_delete(event_id):
    with db() as con:
        con.execute("DELETE FROM events WHERE id = ?", (event_id,))
    flash("Evento removido.", "success")
    return redirect(url_for("events"))

@app.route("/events/<int:event_id>/join", methods=["POST"])
@login_required
def join_event(event_id):
    message, category = None, "success"
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        event = con.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            abort(404)
        enrolled = con.execute("SELECT COUNT(*) AS n FROM registrations WHERE event_id = ?",
                               (event_id,)).fetchone()["n"]
        exists = con.execute("SELECT id FROM registrations WHERE user_id = ? AND event_id = ?",
                             (g.user["id"], event_id)).fetchone()
        if exists:
            message, category = "Você já está inscrito neste evento.", "error"
        elif event["event_date"] < today():
            message, category = "Este evento já foi encerrado.", "error"
        elif enrolled >= event["capacity"]:
            message, category = "As vagas deste evento já foram preenchidas.", "error"
        else:
            con.execute("INSERT INTO registrations(user_id,event_id) VALUES(?,?)", (g.user["id"], event_id))
            message = "Inscrição realizada com sucesso."
    flash(message, category)
    return safe_back("events")

@app.route("/events/<int:event_id>/leave", methods=["POST"])
@login_required
def leave_event(event_id):
    with db() as con:
        event = con.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            abort(404)
        reg = con.execute("SELECT id, attended FROM registrations WHERE user_id = ? AND event_id = ?",
                          (g.user["id"], event_id)).fetchone()
        if not reg:
            message, category = "Você não está inscrito neste evento.", "error"
        elif reg["attended"]:
            message, category = "Não é possível cancelar: sua presença já foi confirmada.", "error"
        elif event["event_date"] < today():
            message, category = "Não é possível cancelar a inscrição de um evento já encerrado.", "error"
        else:
            con.execute("DELETE FROM registrations WHERE id = ?", (reg["id"],))
            message, category = "Inscrição cancelada. A vaga foi liberada.", "success"
    flash(message, category)
    return safe_back("events")

@app.route("/events/<int:event_id>/participants")
@login_required
@admin_required
def participants(event_id):
    with db() as con:
        event = con.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            abort(404)
        people = con.execute("""
            SELECT r.id AS registration_id, r.attended, u.name, u.email
            FROM registrations r JOIN users u ON u.id = r.user_id
            WHERE r.event_id = ? ORDER BY u.name
        """, (event_id,)).fetchall()
    return render_template("participants.html", event=event, people=people)

@app.route("/registrations/<int:registration_id>/attendance", methods=["POST"])
@login_required
@admin_required
def attendance(registration_id):
    with db() as con:
        con.execute("UPDATE registrations SET attended = CASE attended WHEN 1 THEN 0 ELSE 1 END WHERE id = ?",
                    (registration_id,))
    return safe_back("dashboard")

@app.route("/certificates")
@login_required
def certificates():
    with db() as con:
        rows = con.execute("""
            SELECT e.title, e.event_date, e.location, r.attended, u.name
            FROM registrations r JOIN events e ON e.id = r.event_id
            JOIN users u ON u.id = r.user_id
            WHERE r.user_id = ? AND r.attended = 1 ORDER BY e.event_date DESC
        """, (g.user["id"],)).fetchall()
    return render_template("certificates.html", certificates=rows)

# ---------------------------------------------------------------- conta

@app.route("/account")
@login_required
def account():
    with db() as con:
        regs = con.execute("SELECT COUNT(*) AS n FROM registrations WHERE user_id = ?",
                           (g.user["id"],)).fetchone()["n"]
    return render_template("account.html", account=g.user, regs=regs)

@app.route("/account/profile", methods=["POST"])
@login_required
def account_profile():
    name = request.form.get("name", "").strip()
    if not 2 <= len(name) <= 100:
        flash("Informe um nome com 2 a 100 caracteres.", "error")
    else:
        with db() as con:
            con.execute("UPDATE users SET name = ? WHERE id = ?", (name, g.user["id"]))
        flash("Nome atualizado.", "success")
    return redirect(url_for("account"))

@app.route("/account/password", methods=["POST"])
@login_required
def account_password():
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    with db() as con:
        row = con.execute("SELECT password_hash FROM users WHERE id = ?", (g.user["id"],)).fetchone()
        if not check_password_hash(row["password_hash"], current):
            flash("A senha atual está incorreta.", "error")
        elif not 6 <= len(new) <= 128:
            flash("A nova senha deve ter entre 6 e 128 caracteres.", "error")
        elif new != confirm:
            flash("A confirmação não é igual à nova senha.", "error")
        else:
            con.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                        (generate_password_hash(new), g.user["id"]))
            flash("Senha alterada com sucesso.", "success")
    return redirect(url_for("account"))

@app.route("/account/delete", methods=["POST"])
@login_required
def account_delete():
    password = request.form.get("password", "")
    error = None
    with db() as con:
        row = con.execute("SELECT password_hash, role FROM users WHERE id = ?", (g.user["id"],)).fetchone()
        if not check_password_hash(row["password_hash"], password):
            error = "Senha incorreta. A conta não foi excluída."
        elif row["role"] == "admin" and con.execute(
                "SELECT COUNT(*) AS n FROM users WHERE role = 'admin'").fetchone()["n"] <= 1:
            error = "Você é o único administrador. Crie outro administrador antes de excluir esta conta."
        else:
            con.execute("DELETE FROM users WHERE id = ?", (g.user["id"],))
    if error:
        flash(error, "error")
        return redirect(url_for("account"))
    session.clear()
    flash("Sua conta foi excluída.", "success")
    return redirect(url_for("login"))

# ---------------------------------------------------------------- erros

@app.errorhandler(403)
def forbidden(_):
    return render_template("message.html", title="Acesso não permitido",
                           message="Esta área é exclusiva para administradores."), 403

@app.errorhandler(404)
def not_found(_):
    return render_template("message.html", title="Página não encontrada",
                           message="O conteúdo solicitado não foi encontrado."), 404

@app.errorhandler(500)
def server_error(_):
    return render_template("message.html", title="Algo deu errado",
                           message="Ocorreu um erro inesperado. Tente novamente em instantes."), 500

init_db()
if __name__ == "__main__":
    app.run(debug=True)