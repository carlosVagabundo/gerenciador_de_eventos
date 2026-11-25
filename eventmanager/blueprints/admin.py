"""Área do administrador: gerenciar contas de usuários."""
import logging

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from ..db import db
from ..helpers import like_pattern, paginate, safe_back
from ..security import admin_required, login_required
from ..users import delete_user
from ..waitlist import notify_promoted

bp = Blueprint("admin", __name__, url_prefix="/admin")
logger = logging.getLogger(__name__)


@bp.route("/users")
@login_required
@admin_required
def users():
    q = request.args.get("q", "").strip()[:100]
    role = request.args.get("role", "")
    clauses, params = [], {}
    if q:
        clauses.append("(u.name LIKE :q ESCAPE '\\' OR u.email LIKE :q ESCAPE '\\')")
        params["q"] = like_pattern(q)
    if role in ("admin", "student"):
        clauses.append("u.role = :role")
        params["role"] = role
    else:
        role = ""
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with db() as con:
        total = con.execute("SELECT COUNT(*) AS n FROM users u" + where, params).fetchone()["n"]
        pager = paginate(total, request.args.get("page", 1, type=int), current_app.config["USERS_PER_PAGE"])
        rows = con.execute(
            "SELECT u.id, u.name, u.email, u.role,"
            " (SELECT COUNT(*) FROM registrations r WHERE r.user_id = u.id) AS regs,"
            " (SELECT COUNT(*) FROM waitlist w WHERE w.user_id = u.id) AS waiting"
            " FROM users u" + where + " ORDER BY u.name COLLATE NOCASE LIMIT :limit OFFSET :offset",
            {**params, "limit": pager["per_page"], "offset": pager["offset"]}).fetchall()
    filters = {key: value for key, value in (("q", q), ("role", role)) if value}
    return render_template("admin_users.html", users=rows, q=q, role=role, pager=pager, filters=filters)


@bp.route("/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def toggle_role(user_id):
    if user_id == g.user["id"]:
        flash("Você não pode mudar o seu próprio tipo de conta. Peça a outro administrador.", "error")
        return safe_back("admin.users")
    with db() as con:
        row = con.execute("SELECT id, name, role FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            abort(404)
        new_role = "student" if row["role"] == "admin" else "admin"
        con.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    logger.info("Admin %s mudou o usuário %s para %s", g.user["id"], user_id, new_role)
    flash(f"{row['name']} agora é {'administrador' if new_role == 'admin' else 'aluno'}.", "success")
    return safe_back("admin.users")


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def remove_user(user_id):
    if user_id == g.user["id"]:
        flash("Para excluir a sua própria conta, use a página Minha conta.", "error")
        return safe_back("admin.users")
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT id, name FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            abort(404)
        freed = delete_user(con, user_id)
    for event, promoted in freed:
        notify_promoted(promoted, event)
    logger.info("Admin %s excluiu o usuário %s", g.user["id"], user_id)
    flash(f"A conta de {row['name']} foi excluída.", "success")
    return safe_back("admin.users")
