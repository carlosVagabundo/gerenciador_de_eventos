"""Gera o arquivo .ics (Apple, Outlook, Google) e o link do Google Agenda."""
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

from .constants import DEFAULT_EVENT_HOURS


def event_window(event):
    start = datetime.strptime(f"{event['event_date']} {event['event_time']}", "%Y-%m-%d %H:%M")
    return start, start + timedelta(hours=DEFAULT_EVENT_HOURS)


def _escape(text):
    """Escapa o texto conforme o padrão iCalendar (RFC 5545)."""
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _fold(line):
    """Linhas do .ics têm no máximo 75 bytes; as maiores continuam na linha seguinte, iniciada por espaço."""
    parts, current, size = [], "", 0
    for char in line:
        char_size = len(char.encode("utf-8"))
        if size + char_size > 74:
            parts.append(current)
            current, size = " " + char, 1 + char_size
        else:
            current += char
            size += char_size
    parts.append(current)
    return "\r\n".join(parts)


def build_ics(event, page_url=""):
    start, end = event_window(event)
    fmt = "%Y%m%dT%H%M%S"
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//EventManager//PT-BR", "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:evento-{event['id']}@eventmanager",
        "DTSTAMP:" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "DTSTART:" + start.strftime(fmt),            # horário "local": cada calendário usa o fuso do usuário
        "DTEND:" + end.strftime(fmt),
        "SUMMARY:" + _escape(event["title"]),
        "DESCRIPTION:" + _escape(event["description"] + (f"\n\n{page_url}" if page_url else "")),
        "LOCATION:" + _escape(event["location"]),
        "END:VEVENT", "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def google_calendar_url(event):
    start, end = event_window(event)
    fmt = "%Y%m%dT%H%M%S"
    query = urlencode({
        "action": "TEMPLATE",
        "text": event["title"],
        "dates": f"{start.strftime(fmt)}/{end.strftime(fmt)}",
        "details": event["description"],
        "location": event["location"],
    }, quote_via=quote)
    return "https://calendar.google.com/calendar/render?" + query
