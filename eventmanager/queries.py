"""Consultas SQL compartilhadas entre as telas."""
from datetime import date, timedelta

EVENT_SELECT = """
    SELECT e.*,
           (SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id) AS enrolled,
           (SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id AND r.attended = 1) AS present,
           (SELECT COUNT(*) FROM waitlist w WHERE w.event_id = e.id) AS waiting,
           EXISTS(SELECT 1 FROM registrations r WHERE r.event_id = e.id AND r.user_id = :uid) AS joined,
           (SELECT r.attended FROM registrations r WHERE r.event_id = e.id AND r.user_id = :uid) AS my_attended,
           (SELECT COUNT(*) FROM waitlist w WHERE w.event_id = e.id AND w.id <=
               (SELECT w2.id FROM waitlist w2 WHERE w2.event_id = e.id AND w2.user_id = :uid)) AS waitlist_pos
    FROM events e
"""


def fetch_events(con, user_id, where="", params=None, order="e.event_date, e.event_time",
                 limit=None, offset=0):
    """Lista eventos já com vagas ocupadas, fila de espera e a situação do usuário (user_id)."""
    values = dict(params or {})
    values["uid"] = user_id
    sql = EVENT_SELECT + (" WHERE " + where if where else "") + " ORDER BY " + order
    if limit is not None:
        sql += " LIMIT :limit OFFSET :offset"
        values.update(limit=limit, offset=offset)
    return con.execute(sql, values).fetchall()


def count_events(con, where="", params=None):
    sql = "SELECT COUNT(*) AS n FROM events e" + (" WHERE " + where if where else "")
    return con.execute(sql, dict(params or {})).fetchone()["n"]


def admin_overview(con):
    """Números e dados dos gráficos do painel do administrador."""
    totals = con.execute("""
        SELECT (SELECT COUNT(*) FROM events) AS events,
               (SELECT COUNT(*) FROM registrations) AS regs,
               (SELECT COUNT(*) FROM users WHERE role = 'student') AS students,
               (SELECT COUNT(*) FROM registrations WHERE attended = 1) AS present,
               (SELECT COUNT(*) FROM waitlist) AS waiting
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
            "rate": rate, "waiting": totals["waiting"], "by_category": by_category, "last7": last7}
