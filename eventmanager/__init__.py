"""Fábrica da aplicação (create_app): monta configuração, logs, blueprints e tratadores de erro."""
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, render_template

from .calendar_utils import google_calendar_url
from .config import BASE_DIR, Config
from .csrf import csrf_field, protect
from .constants import CATEGORIES, CATEGORY_ICONS, MONTHS
from .db import run_migrations
from .helpers import today
from .security import current_user_row


def configure_logging(app):
    level = getattr(logging, str(app.config["LOG_LEVEL"]).upper(), logging.INFO)
    logger = logging.getLogger("eventmanager")
    logger.setLevel(level)
    if logger.handlers:                       # evita duplicar handlers se create_app rodar de novo
        return
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    if not app.config.get("TESTING"):
        try:
            log_dir = Path(app.config["LOG_DIR"])
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(log_dir / "eventmanager.log", maxBytes=1_000_000,
                                               backupCount=3, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError:
            logger.warning("Não foi possível criar o arquivo de log; usando só o console.")


def register_template_helpers(app):
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

    app.jinja_env.globals["google_calendar_url"] = google_calendar_url
    app.jinja_env.globals["csrf_field"] = csrf_field
    app.before_request(protect)

    @app.context_processor
    def inject_globals():
        from flask import g
        user = getattr(g, "user", None) or current_user_row()
        return {"current_user": user["name"] if user else None,
                "current_role": user["role"] if user else None,
                "CATEGORIES": CATEGORIES, "CATEGORY_ICONS": CATEGORY_ICONS, "today": today()}

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response


def register_error_handlers(app):
    def page(title, message, code):
        return render_template("message.html", title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(_):
        return page("Formulário expirado", "Não foi possível confirmar o envio (a página pode ter ficado aberta "
                    "por muito tempo). Volte, recarregue a página e tente de novo.", 400)

    @app.errorhandler(403)
    def forbidden(_):
        return page("Acesso não permitido", "Esta área é exclusiva para administradores.", 403)

    @app.errorhandler(404)
    def not_found(_):
        return page("Página não encontrada", "O conteúdo solicitado não foi encontrado.", 404)

    @app.errorhandler(413)
    def too_large(_):
        return page("Arquivo grande demais", "O arquivo enviado passa do tamanho permitido (5 MB).", 413)

    @app.errorhandler(500)
    def server_error(_):
        logging.getLogger("eventmanager").exception("Erro interno não tratado")
        return page("Algo deu errado", "Ocorreu um erro inesperado. Tente novamente em instantes.", 500)


def create_app(test_config=None):
    app = Flask(__name__, template_folder=str(BASE_DIR / "templates"),
                static_folder=str(BASE_DIR / "static"))
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    configure_logging(app)
    register_template_helpers(app)

    from .blueprints import account, admin, auth, events, main
    for module in (main, auth, events, account, admin):
        app.register_blueprint(module.bp)
    register_error_handlers(app)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    with app.app_context():
        run_migrations()
    return app
