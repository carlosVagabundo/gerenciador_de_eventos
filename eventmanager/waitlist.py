"""Regras da lista de espera: quando abre vaga, o primeiro da fila é inscrito automaticamente."""
from .mailer import send_email


def promote_waitlist(con, event_id):
    """Move pessoas da fila para as inscrições enquanto houver vaga. Retorna quem foi promovido.

    Deve ser chamada dentro de uma transação já aberta (o commit é feito por quem chamou)."""
    promoted = []
    event = con.execute("SELECT capacity FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        return promoted
    while True:
        enrolled = con.execute("SELECT COUNT(*) AS n FROM registrations WHERE event_id = ?",
                               (event_id,)).fetchone()["n"]
        if enrolled >= event["capacity"]:
            break
        nxt = con.execute("""SELECT w.id, w.user_id, u.name, u.email FROM waitlist w
                             JOIN users u ON u.id = w.user_id
                             WHERE w.event_id = ? ORDER BY w.id LIMIT 1""", (event_id,)).fetchone()
        if not nxt:
            break
        con.execute("INSERT INTO registrations(user_id, event_id) VALUES(?, ?)", (nxt["user_id"], event_id))
        con.execute("DELETE FROM waitlist WHERE id = ?", (nxt["id"],))
        promoted.append(nxt)
    return promoted


def notify_promoted(promoted, event):
    """Avisa por e-mail (se houver SMTP) quem saiu da fila. Chamar DEPOIS do commit."""
    for person in promoted:
        send_email(
            person["email"],
            f"Vaga confirmada: {event['title']}",
            f"Olá, {person['name']}!\n\nUma vaga abriu e sua inscrição no evento \"{event['title']}\" "
            f"({event['event_date']} às {event['event_time']}, {event['location']}) foi confirmada "
            f"automaticamente.\n\nEventManager",
        )
