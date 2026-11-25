"""Limite de tentativas (login e pedidos de recuperação), guardado no banco para valer em todos os processos."""


def too_many(con, key, limit, minutes):
    """True se já houve `limit` ou mais registros dessa chave nos últimos `minutes` minutos."""
    count = con.execute(
        "SELECT COUNT(*) AS n FROM rate_limits WHERE key = ? AND created_at >= datetime('now', ?)",
        (key, f"-{int(minutes)} minutes")).fetchone()["n"]
    return count >= limit


def record(con, key):
    con.execute("INSERT INTO rate_limits(key) VALUES(?)", (key,))
    con.execute("DELETE FROM rate_limits WHERE created_at < datetime('now', '-1 day')")   # limpeza


def clear(con, key):
    con.execute("DELETE FROM rate_limits WHERE key = ?", (key,))
