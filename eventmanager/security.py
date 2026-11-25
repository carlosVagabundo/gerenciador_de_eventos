"""Quem está logado e quem pode acessar cada página."""
from functools import wraps

from flask import abort, g, redirect, session, url_for

from .db import db


def current_user_row():
    """Busca no banco o usuário da sessão. Se a conta foi excluída, devolve None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    with db() as con:
        return con.execute("SELECT id, name, email, role FROM users WHERE id = ?", (user_id,)).fetchone()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user_row()
        if not user:
            session.clear()
            return redirect(url_for("auth.login"))
        g.user = user
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    """Use sempre DEPOIS de @login_required (ele é quem preenche g.user)."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if g.user["role"] != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper
