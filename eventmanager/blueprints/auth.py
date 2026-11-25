"""Login, cadastro, logout e recuperação de senha."""
import hashlib
import logging
import secrets
import sqlite3

from flask import (Blueprint, current_app, flash, redirect, render_template, request, session, url_for)
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import db
from ..helpers import EMAIL_RE
from ..mailer import send_email
from ..ratelimit import clear, record, too_many
from ..security import current_user_row

bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- token de recuperação de senha

def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset")


def _fingerprint(password_hash):
    """Impressão digital da senha atual: quando a senha muda, o link antigo deixa de valer."""
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def make_reset_token(user):
    return _serializer().dumps({"uid": user["id"], "fp": _fingerprint(user["password_hash"])})


def user_from_reset_token(token):
    try:
        data = _serializer().loads(token, max_age=current_app.config["RESET_TOKEN_MAX_AGE"])
    except BadSignature:                       # inclui SignatureExpired (link vencido)
        return None
    with db() as con:
        user = con.execute("SELECT * FROM users WHERE id = ?", (data.get("uid"),)).fetchone()
    if user and secrets.compare_digest(_fingerprint(user["password_hash"]), str(data.get("fp"))):
        return user
    return None


# ---------------------------------------------------------------- rotas

@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user_row():
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        cfg = current_app.config
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        key = "login:" + email[:150]
        user, locked = None, False
        with db() as con:
            if too_many(con, key, cfg["LOGIN_MAX_ATTEMPTS"], cfg["LOGIN_LOCK_MINUTES"]):
                locked = True                      # vale também para e-mails que não existem
            else:
                user = con.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
                if user and check_password_hash(user["password_hash"], password):
                    clear(con, key)
                else:
                    user = None
                    record(con, key)
        if locked:
            logger.warning("Login bloqueado temporariamente por excesso de tentativas")
            flash(f"Muitas tentativas de login. Aguarde {cfg['LOGIN_LOCK_MINUTES']} minutos e tente de novo.", "error")
            return render_template("login.html"), 429
        if user:
            session.clear()                        # nova sessão a cada login
            session["user_id"] = user["id"]
            logger.info("Login do usuário %s", user["id"])
            return redirect(url_for("main.dashboard"))
        logger.warning("Tentativa de login com credenciais incorretas")
        flash("E-mail ou senha incorretos.", "error")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user_row():
        return redirect(url_for("main.dashboard"))
    admin_code_config = current_app.config["ADMIN_CODE"]
    admin_enabled = bool(admin_code_config)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")
        admin_code = request.form.get("admin_code", "").strip()
        role = "student"
        if admin_code:
            if admin_code_config and secrets.compare_digest(admin_code.encode(), admin_code_config.encode()):
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
                logger.info("Nova conta criada (%s)", role)
                flash("Conta de administrador criada! Faça login para continuar." if role == "admin"
                      else "Conta criada! Faça login para continuar.", "success")
                return redirect(url_for("auth.login"))
            except sqlite3.IntegrityError:
                flash("Este e-mail já está cadastrado.", "error")
    return render_template("register.html", admin_enabled=admin_enabled)


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        key = "reset:" + email[:150]
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            allowed = not too_many(con, key, current_app.config["RESET_MAX_REQUESTS"], 60)
            if allowed:
                record(con, key)                   # conta o pedido exista ou não a conta (resposta uniforme)
        if user and allowed:
            link = url_for("auth.reset_password", token=make_reset_token(user), _external=True)
            minutes = current_app.config["RESET_TOKEN_MAX_AGE"] // 60
            send_email(user["email"], "Redefinição de senha - EventManager",
                       f"Olá, {user['name']}!\n\nPara criar uma nova senha, abra o link abaixo "
                       f"(ele vale por {minutes} minutos):\n\n{link}\n\n"
                       "Se você não pediu isso, ignore esta mensagem: sua senha continua a mesma.")
            logger.info("Redefinição de senha solicitada pelo usuário %s", user["id"])
        elif user:
            logger.warning("Pedidos de redefinição em excesso para o usuário %s", user["id"])
        # A resposta é sempre a mesma, exista ou não a conta (não revela quem está cadastrado).
        flash("Se o e-mail estiver cadastrado, enviamos um link para criar uma nova senha.", "success")
        return redirect(url_for("auth.login"))
    return render_template("forgot_password.html")


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = user_from_reset_token(token)
    if not user:
        flash("Este link é inválido ou expirou. Peça um novo.", "error")
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not 6 <= len(new) <= 128:
            flash("A senha deve ter entre 6 e 128 caracteres.", "error")
        elif new != confirm:
            flash("As senhas digitadas não são iguais.", "error")
        else:
            with db() as con:
                con.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                            (generate_password_hash(new), user["id"]))
            logger.info("Senha redefinida pelo usuário %s", user["id"])
            flash("Senha alterada! Entre com a nova senha.", "success")
            return redirect(url_for("auth.login"))
    return render_template("reset_password.html", token=token)
