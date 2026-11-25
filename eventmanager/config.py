"""Configurações lidas das variáveis de ambiente (com valores padrão seguros para testes)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "troque-esta-chave-antes-de-publicar")
    ADMIN_CODE = os.environ.get("ADMIN_CODE", "")
    DATABASE = os.environ.get("DATABASE_PATH", str(BASE_DIR / "eventmanager.db"))

    # Cookies de sessão mais seguros
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SECURE_COOKIES", "0") == "1"   # use 1 em produção (HTTPS)

    CSRF_ENABLED = True                         # token anti-CSRF em todos os formulários POST

    # Limites de tentativas (guardados no banco, valem para todos os processos do servidor)
    LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
    LOGIN_LOCK_MINUTES = int(os.environ.get("LOGIN_LOCK_MINUTES", "10"))
    RESET_MAX_REQUESTS = 3                      # pedidos de "esqueci minha senha" por hora, por e-mail

    # Upload de capas
    UPLOAD_FOLDER = str(BASE_DIR / "static" / "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024        # limite do corpo da requisição
    MAX_COVER_BYTES = 3 * 1024 * 1024           # limite da imagem em si

    EVENTS_PER_PAGE = 9
    USERS_PER_PAGE = 10
    RESET_TOKEN_MAX_AGE = 3600                  # link de "esqueci minha senha" vale 1 hora

    # E-mail (opcional). Sem SMTP_HOST, os e-mails são apenas registrados no log.
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_TLS = os.environ.get("SMTP_TLS", "1") != "0"
    MAIL_FROM = os.environ.get("MAIL_FROM", "")

    LOG_DIR = os.environ.get("LOG_DIR", str(BASE_DIR / "logs"))
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
