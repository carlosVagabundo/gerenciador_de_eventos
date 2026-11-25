"""Eventos: listagem, cadastro, edição, inscrição, lista de espera, presença e calendário."""
import csv
import io
import logging

from flask import (Blueprint, Response, abort, current_app, flash, g, redirect, render_template,
                   request, url_for)

from ..calendar_utils import build_ics
from ..constants import CATEGORIES
from ..db import db
from ..helpers import like_pattern, paginate, parse_event_form, safe_back, today
from ..queries import count_events, fetch_events
from ..security import admin_required, login_required
from ..uploads import delete_cover, resolve_cover
from ..waitlist import notify_promoted, promote_waitlist

bp = Blueprint("events", __name__)
logger = logging.getLogger(__name__)


def _get_event_or_404(con, event_id):
    event = con.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        abort(404)
    return event


# ---------------------------------------------------------------- listagem

@bp.route("/events")
@login_required
def index():
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
    where = " AND ".join(clauses)
    order = "e.event_date DESC, e.event_time DESC" if period == "past" else "e.event_date, e.event_time"
    with db() as con:
        total = count_events(con, where, params)
        pager = paginate(total, request.args.get("page", 1, type=int), current_app.config["EVENTS_PER_PAGE"])
        rows = fetch_events(con, g.user["id"], where, params, order, pager["per_page"], pager["offset"])
    filters = {key: value for key, value in
               (("q", q), ("category", category), ("period", "" if period == "all" else period)) if value}
    return render_template("events.html", events=rows, q=q, category=category, period=period,
                           pager=pager, filters=filters)


# ---------------------------------------------------------------- administração

@bp.route("/events/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_event():
    if request.method == "POST":
        data, error = parse_event_form()
        cover_url = ""
        if not error:
            cover_url, error = resolve_cover(request.form, request.files)
        if not error:
            data["cover_url"] = cover_url
            try:
                with db() as con:
                    con.execute("""INSERT INTO events(title,description,event_date,event_time,location,
                                                      capacity,category,cover_url)
                                   VALUES(:title,:description,:event_date,:event_time,:location,
                                          :capacity,:category,:cover_url)""", data)
            except Exception:
                delete_cover(cover_url)         # não deixa arquivo órfão se o banco falhar
                raise
            logger.info("Evento criado: %s", data["title"])
            flash("Evento cadastrado com sucesso.", "success")
            return redirect(url_for("events.index"))
        flash(error, "error")
        return render_template("event_form.html", event=None, values=request.form)
    return render_template("event_form.html", event=None, values={})


@bp.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_event(event_id):
    with db() as con:
        event = _get_event_or_404(con, event_id)
    if request.method == "POST":
        data, error = parse_event_form()
        new_cover = event["cover_url"]
        if not error:
            new_cover, error = resolve_cover(request.form, request.files, event["cover_url"])
        promoted = []
        if not error:
            data["cover_url"] = new_cover
            with db() as con:
                con.execute("BEGIN IMMEDIATE")
                enrolled = con.execute("SELECT COUNT(*) AS n FROM registrations WHERE event_id = ?",
                                       (event_id,)).fetchone()["n"]
                if data["capacity"] < enrolled:
                    error = f"O limite de vagas não pode ser menor que o número de inscritos ({enrolled})."
                else:
                    con.execute("""UPDATE events SET title=:title, description=:description,
                                   event_date=:event_date, event_time=:event_time, location=:location,
                                   capacity=:capacity, category=:category, cover_url=:cover_url
                                   WHERE id=:id""", {**data, "id": event_id})
                    promoted = promote_waitlist(con, event_id)     # vagas novas -> chama a fila
            if error and new_cover != event["cover_url"]:
                delete_cover(new_cover)                           # descarta o upload não usado
        if not error:
            if new_cover != event["cover_url"]:
                delete_cover(event["cover_url"])                  # apaga a capa antiga
            notify_promoted(promoted, {**data, "id": event_id})
            flash("Evento atualizado." + (f" {len(promoted)} pessoa(s) saíram da lista de espera."
                                          if promoted else ""), "success")
            return redirect(url_for("events.index"))
        flash(error, "error")
        return render_template("event_form.html", event=event, values=request.form)
    return render_template("event_form.html", event=event, values=dict(event))


@bp.route("/events/<int:event_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_event(event_id):
    with db() as con:
        event = _get_event_or_404(con, event_id)
        con.execute("DELETE FROM events WHERE id = ?", (event_id,))
    delete_cover(event["cover_url"])
    logger.info("Evento %s excluído", event_id)
    flash("Evento removido.", "success")
    return redirect(url_for("events.index"))


@bp.route("/events/<int:event_id>/participants")
@login_required
@admin_required
def participants(event_id):
    with db() as con:
        event = _get_event_or_404(con, event_id)
        people = con.execute("""
            SELECT r.id AS registration_id, r.attended, u.name, u.email
            FROM registrations r JOIN users u ON u.id = r.user_id
            WHERE r.event_id = ? ORDER BY u.name
        """, (event_id,)).fetchall()
        queue = con.execute("""
            SELECT w.id, u.name, u.email FROM waitlist w JOIN users u ON u.id = w.user_id
            WHERE w.event_id = ? ORDER BY w.id
        """, (event_id,)).fetchall()
    return render_template("participants.html", event=event, people=people, queue=queue)


def _csv_safe(value):
    """Evita 'injeção de fórmula' no Excel: textos que começam com = + - @ ganham um apóstrofo."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@bp.route("/events/<int:event_id>/participants.csv")
@login_required
@admin_required
def participants_csv(event_id):
    with db() as con:
        _get_event_or_404(con, event_id)
        people = con.execute("""
            SELECT u.name, u.email, r.attended, r.registered_at FROM registrations r
            JOIN users u ON u.id = r.user_id WHERE r.event_id = ? ORDER BY u.name
        """, (event_id,)).fetchall()
        queue = con.execute("""
            SELECT u.name, u.email, w.created_at FROM waitlist w
            JOIN users u ON u.id = w.user_id WHERE w.event_id = ? ORDER BY w.id
        """, (event_id,)).fetchall()
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")        # ";" e BOM: o Excel em português abre com acentos certos
    writer.writerow(["Nome", "E-mail", "Situação", "Presença", "Registrado em (UTC)"])
    for p in people:
        writer.writerow([_csv_safe(p["name"]), _csv_safe(p["email"]), "Inscrito",
                         "Presente" if p["attended"] else "Pendente", p["registered_at"]])
    for position, w in enumerate(queue, start=1):
        writer.writerow([_csv_safe(w["name"]), _csv_safe(w["email"]), f"Lista de espera ({position}º)", "-", w["created_at"]])
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="participantes-evento-{event_id}.csv"'})


@bp.route("/registrations/<int:registration_id>/attendance", methods=["POST"])
@login_required
@admin_required
def attendance(registration_id):
    with db() as con:
        con.execute("UPDATE registrations SET attended = CASE attended WHEN 1 THEN 0 ELSE 1 END WHERE id = ?",
                    (registration_id,))
    return safe_back("main.dashboard")


# ---------------------------------------------------------------- inscrição e lista de espera

@bp.route("/events/<int:event_id>/join", methods=["POST"])
@login_required
def join_event(event_id):
    with db() as con:
        con.execute("BEGIN IMMEDIATE")         # trava o banco: duas pessoas não pegam a mesma última vaga
        event = _get_event_or_404(con, event_id)
        enrolled = con.execute("SELECT COUNT(*) AS n FROM registrations WHERE event_id = ?",
                               (event_id,)).fetchone()["n"]
        exists = con.execute("SELECT id FROM registrations WHERE user_id = ? AND event_id = ?",
                             (g.user["id"], event_id)).fetchone()
        if exists:
            message, category = "Você já está inscrito neste evento.", "error"
        elif event["event_date"] < today():
            message, category = "Este evento já foi encerrado.", "error"
        elif enrolled >= event["capacity"]:
            message, category = "As vagas acabaram. Você pode entrar na lista de espera.", "error"
        else:
            con.execute("INSERT INTO registrations(user_id, event_id) VALUES(?, ?)", (g.user["id"], event_id))
            con.execute("DELETE FROM waitlist WHERE user_id = ? AND event_id = ?", (g.user["id"], event_id))
            message, category = "Inscrição realizada com sucesso.", "success"
    flash(message, category)
    return safe_back("events.index")


@bp.route("/events/<int:event_id>/leave", methods=["POST"])
@login_required
def leave_event(event_id):
    promoted = []
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        event = _get_event_or_404(con, event_id)
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
            promoted = promote_waitlist(con, event_id)           # a vaga liberada vai para o 1º da fila
            message, category = "Inscrição cancelada. A vaga foi liberada.", "success"
    notify_promoted(promoted, event)
    flash(message, category)
    return safe_back("events.index")


@bp.route("/events/<int:event_id>/waitlist", methods=["POST"])
@login_required
def join_waitlist(event_id):
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        event = _get_event_or_404(con, event_id)
        enrolled = con.execute("SELECT COUNT(*) AS n FROM registrations WHERE event_id = ?",
                               (event_id,)).fetchone()["n"]
        joined = con.execute("SELECT 1 FROM registrations WHERE user_id = ? AND event_id = ?",
                             (g.user["id"], event_id)).fetchone()
        waiting = con.execute("SELECT 1 FROM waitlist WHERE user_id = ? AND event_id = ?",
                              (g.user["id"], event_id)).fetchone()
        if joined:
            message, category = "Você já está inscrito neste evento.", "error"
        elif waiting:
            message, category = "Você já está na lista de espera deste evento.", "error"
        elif event["event_date"] < today():
            message, category = "Este evento já foi encerrado.", "error"
        elif enrolled < event["capacity"]:
            message, category = "Ainda há vagas! Faça a inscrição normalmente.", "error"
        else:
            con.execute("INSERT INTO waitlist(user_id, event_id) VALUES(?, ?)", (g.user["id"], event_id))
            position = con.execute("SELECT COUNT(*) AS n FROM waitlist WHERE event_id = ?",
                                   (event_id,)).fetchone()["n"]
            message, category = f"Você entrou na lista de espera (posição {position}).", "success"
    flash(message, category)
    return safe_back("events.index")


@bp.route("/events/<int:event_id>/waitlist/leave", methods=["POST"])
@login_required
def leave_waitlist(event_id):
    with db() as con:
        _get_event_or_404(con, event_id)
        cur = con.execute("DELETE FROM waitlist WHERE user_id = ? AND event_id = ?", (g.user["id"], event_id))
    flash("Você saiu da lista de espera." if cur.rowcount else "Você não estava na lista de espera.",
          "success" if cur.rowcount else "error")
    return safe_back("events.index")


# ---------------------------------------------------------------- calendário

@bp.route("/events/<int:event_id>/calendar.ics")
@login_required
def calendar_file(event_id):
    with db() as con:
        event = _get_event_or_404(con, event_id)
    content = build_ics(event, url_for("events.index", _external=True))
    return Response(content, mimetype="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="evento-{event_id}.ics"'})
