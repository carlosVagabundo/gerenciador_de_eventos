"""Página inicial pública e painel (dashboard)."""
from flask import Blueprint, g, redirect, render_template, url_for

from ..db import db
from ..helpers import today
from ..queries import admin_overview, count_events, fetch_events
from ..security import current_user_row, login_required

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if current_user_row():
        return redirect(url_for("main.dashboard"))
    with db() as con:
        upcoming = fetch_events(con, 0, "e.event_date >= :today", {"today": today()}, limit=6)
        upcoming_total = count_events(con, "e.event_date >= :today", {"today": today()})
    return render_template("home.html", upcoming=upcoming, upcoming_total=upcoming_total)


@bp.route("/dashboard")
@login_required
def dashboard():
    uid = g.user["id"]
    with db() as con:
        if g.user["role"] == "admin":
            upcoming = fetch_events(con, uid, "e.event_date >= :today", {"today": today()}, limit=6)
            occupancy = [{"title": e["title"], "enrolled": e["enrolled"], "capacity": e["capacity"],
                          "pct": min(100, round(e["enrolled"] * 100 / e["capacity"]))} for e in upcoming]
            return render_template("dashboard.html", stats=admin_overview(con),
                                   upcoming=upcoming, occupancy=occupancy)
        mine = fetch_events(con, uid, "EXISTS (SELECT 1 FROM registrations r WHERE r.event_id = e.id "
                                      "AND r.user_id = :uid)")
        waiting = fetch_events(con, uid, "EXISTS (SELECT 1 FROM waitlist w WHERE w.event_id = e.id "
                                         "AND w.user_id = :uid)")
    mine_upcoming = [e for e in mine if e["event_date"] >= today()]
    mine_past = [e for e in mine if e["event_date"] < today()][::-1]
    summary = {"active": len(mine_upcoming), "total": len(mine), "waiting": len(waiting),
               "present": sum(1 for e in mine if e["my_attended"])}
    return render_template("dashboard.html", mine_upcoming=mine_upcoming, mine_past=mine_past,
                           waiting=waiting, summary=summary)
