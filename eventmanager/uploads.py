"""Upload seguro de imagens de capa."""
import logging
import re
import secrets
from pathlib import Path

from flask import current_app

logger = logging.getLogger(__name__)
UPLOAD_URL_PREFIX = "/static/uploads/"


def detect_image_extension(data):
    """Descobre o tipo REAL da imagem pelos primeiros bytes (não confia no nome do arquivo)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def save_cover(file_storage):
    """Valida e grava a imagem. Retorna (url, erro)."""
    limit = current_app.config["MAX_COVER_BYTES"]
    data = file_storage.read(limit + 1)
    if not data:
        return None, "O arquivo enviado está vazio."
    if len(data) > limit:
        return None, f"A imagem é grande demais (máximo de {limit // (1024 * 1024)} MB)."
    extension = detect_image_extension(data)
    if not extension:
        return None, "Envie uma imagem nos formatos PNG, JPG, GIF ou WEBP."
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    name = secrets.token_hex(12) + extension          # nome aleatório: nunca usamos o nome enviado
    (folder / name).write_bytes(data)
    return UPLOAD_URL_PREFIX + name, None


def delete_cover(cover_url):
    """Apaga o arquivo de uma capa enviada por upload (links externos são ignorados)."""
    if not cover_url or not cover_url.startswith(UPLOAD_URL_PREFIX):
        return
    path = Path(current_app.config["UPLOAD_FOLDER"]) / Path(cover_url).name   # .name bloqueia "../"
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        logger.exception("Não foi possível apagar a capa %s", path)


def resolve_cover(form, files, current_url=""):
    """Decide qual será a capa do evento. Retorna (url, erro).

    Prioridade: arquivo enviado > link informado > remover > manter a atual."""
    file = files.get("cover_file")
    link = form.get("cover_url", "").strip()
    if file and file.filename:
        return save_cover(file)
    if link:
        if len(link) > 500 or not re.match(r"^https?://\S+$", link):
            return None, "O link da imagem de capa deve começar com http:// ou https://."
        return link, None
    if form.get("remove_cover"):
        return "", None
    return current_url, None
