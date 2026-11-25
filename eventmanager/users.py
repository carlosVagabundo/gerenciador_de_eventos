"""Regras compartilhadas sobre contas de usuário."""
from .waitlist import promote_waitlist


def delete_user(con, user_id):
    """Apaga o usuário e oferece as vagas que ele ocupava à lista de espera.

    Deve rodar dentro de uma transação aberta. Retorna [(evento, promovidos)] para avisar depois do commit."""
    event_ids = [row["event_id"] for row in con.execute(
        "SELECT event_id FROM registrations WHERE user_id = ?", (user_id,))]
    con.execute("DELETE FROM users WHERE id = ?", (user_id,))     # CASCADE apaga inscrições e fila dele
    freed = []
    for event_id in event_ids:
        event = con.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        promoted = promote_waitlist(con, event_id)
        if event and promoted:
            freed.append((event, promoted))
    return freed
