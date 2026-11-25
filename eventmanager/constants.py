"""Valores fixos usados em várias partes do sistema."""

CATEGORIES = ["Palestra", "Workshop", "Curso", "Esporte", "Cultura", "Feira", "Outro"]

CATEGORY_ICONS = {
    "Palestra": "🎤", "Workshop": "🛠️", "Curso": "📚", "Esporte": "⚽",
    "Cultura": "🎭", "Feira": "🛍️", "Outro": "✨",
}

MONTHS = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]

# Duração usada no calendário, já que o evento só tem data e horário de início.
DEFAULT_EVENT_HOURS = 2
