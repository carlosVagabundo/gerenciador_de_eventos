"""Envio de e-mails. Sem SMTP configurado, a mensagem apenas aparece no log (modo desenvolvimento)."""
import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

logger = logging.getLogger(__name__)


def send_email(to, subject, body):
    """Tenta enviar um e-mail. Nunca derruba o site: devolve True/False."""
    cfg = current_app.config
    if not cfg.get("SMTP_HOST"):
        logger.warning("SMTP não configurado: e-mail NÃO enviado.\nPara: %s\nAssunto: %s\n%s", to, subject, body)
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = cfg.get("MAIL_FROM") or cfg.get("SMTP_USER")
        msg["To"] = to
        msg.set_content(body)
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=10) as server:
            if cfg.get("SMTP_TLS"):
                server.starttls()
            if cfg.get("SMTP_USER"):
                server.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            server.send_message(msg)
        logger.info("E-mail enviado: %s", subject)
        return True
    except Exception:
        logger.exception("Falha ao enviar e-mail (%s)", subject)
        return False
