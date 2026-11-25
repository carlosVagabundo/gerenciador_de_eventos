"""Funções pequenas e reutilizáveis (datas, busca, paginação, validação de formulário)."""
import re
from datetime import date, datetime
from urllib.parse import urlparse

from flask import redirect, request, url_for

from .constants import CATEGORIES

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def today():
    return date.today().isoformat()


def like_pattern(text):
    """Transforma o texto digitado em um padrão LIKE, tratando % e _ como letras comuns."""
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def safe_back(default_endpoint):
    """Volta para a página anterior, mas só se ela for deste mesmo site (evita redirecionamento aberto)."""
    ref = request.referrer
    if ref and urlparse(ref).netloc == request.host:
        return redirect(ref)
    return redirect(url_for(default_endpoint))


def paginate(total, page, per_page):
    """Calcula tudo que a tela precisa para mostrar a paginação."""
    pages = max(1, -(-total // per_page))          # divisão para cima
    page = min(max(page, 1), pages)
    wanted = sorted({1, pages, *range(max(1, page - 2), min(pages, page + 2) + 1)})
    numbers, last = [], None
    for n in wanted:
        if last is not None and n - last > 1:
            numbers.append(None)                    # None vira "…" na tela
        numbers.append(n)
        last = n
    return {"page": page, "pages": pages, "total": total, "per_page": per_page,
            "offset": (page - 1) * per_page, "has_prev": page > 1, "has_next": page < pages,
            "numbers": numbers}


def parse_event_form():
    """Valida os campos de texto do formulário de evento. Retorna (dados, erro)."""
    form = request.form
    title = form.get("title", "").strip()
    description = form.get("description", "").strip()
    event_date = form.get("event_date", "").strip()
    event_time = form.get("event_time", "").strip()
    location = form.get("location", "").strip()
    category = form.get("category", "Outro")
    if category not in CATEGORIES:
        category = "Outro"
    if not (title and description and location):
        return None, "Preencha o nome, a descrição e o local do evento."
    if len(title) > 120 or len(location) > 120 or len(description) > 2000:
        return None, "Algum texto está grande demais (nome e local: até 120 caracteres; descrição: até 2000)."
    try:
        datetime.strptime(event_date, "%Y-%m-%d")
        datetime.strptime(event_time, "%H:%M")
    except ValueError:
        return None, "Informe uma data e um horário válidos."
    try:
        capacity = int(form.get("capacity", "0"))
    except ValueError:
        capacity = 0
    if not 1 <= capacity <= 100000:
        return None, "Informe um limite de vagas entre 1 e 100000."
    return {"title": title, "description": description, "event_date": event_date,
            "event_time": event_time, "location": location, "capacity": capacity,
            "category": category}, None
