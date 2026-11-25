"""Conta do usuário (nome, senha, exclusão) e certificados."""
import logging

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import db
from ..security import login_required
from ..users import delete_user
from ..waitlist import notify_promoted

bp = Blueprint("account", __name__)
logger = logging.getLogger(__name__)


@bp.route("/account")
@login_required
def index():
    with db() as con:
        regs = con.execute("SELECT COUNT(*) AS n FROM registrations WHERE user_id = ?",
                           (g.user["id"],)).fetchone()["n"]
    return render_template("account.html", account=g.user, regs=regs)


@bp.route("/account/profile", methods=["POST"])
@login_required
def update_profile():
    name = request.form.get("name", "").strip()
    if not 2 <= len(name) <= 100:
        flash("Informe um nome com 2 a 100 caracteres.", "error")
    else:
        with db() as con:
            con.execute("UPDATE users SET name = ? WHERE id = ?", (name, g.user["id"]))
        flash("Nome atualizado.", "success")
    return redirect(url_for("account.index"))


@bp.route("/account/password", methods=["POST"])
@login_required
def change_password():
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
            logger.info("Senha alterada pelo usuário %s", g.user["id"])
            flash("Senha alterada com sucesso.", "success")
    return redirect(url_for("account.index"))


@bp.route("/account/delete", methods=["POST"])
@login_required
def delete_account():
    password = request.form.get("password", "")
    error, freed = None, []
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT password_hash, role FROM users WHERE id = ?", (g.user["id"],)).fetchone()
        if not check_password_hash(row["password_hash"], password):
            error = "Senha incorreta. A conta não foi excluída."
        elif row["role"] == "admin" and con.execute(
                "SELECT COUNT(*) AS n FROM users WHERE role = 'admin'").fetchone()["n"] <= 1:
            error = "Você é o único administrador. Crie outro administrador antes de excluir esta conta."
        else:
            freed = delete_user(con, g.user["id"])      # libera as vagas para a lista de espera
    if error:
        flash(error, "error")
        return redirect(url_for("account.index"))
    for event, promoted in freed:
        notify_promoted(promoted, event)
    logger.info("Conta %s excluída pelo próprio usuário", g.user["id"])
    session.clear()
    flash("Sua conta foi excluída.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/certificates")
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
