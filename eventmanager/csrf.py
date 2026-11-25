"""Proteção CSRF: cada formulário POST leva um token secreto que só o nosso site conhece."""
import secrets

from flask import abort, current_app, request, session
from markupsafe import Markup


def get_token():
    """Token da sessão atual (criado na primeira vez que alguém pede)."""
    token = session.get("csrf_token")
    if not token:
        token = session["csrf_token"] = secrets.token_urlsafe(32)
    return token


def csrf_field():
    """HTML do campo escondido. Nos templates: {{ csrf_field() }} dentro de cada <form method="post">."""
    return Markup('<input type="hidden" name="csrf_token" value="%s">') % get_token()


def protect():
    """Roda antes de cada requisição: recusa POST sem o token correto (erro 400)."""
    if not current_app.config.get("CSRF_ENABLED", True):
        return
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf_token", "")
        if not expected or not secrets.compare_digest(sent.encode(), expected.encode()):
            abort(400)
