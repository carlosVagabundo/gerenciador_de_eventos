"""Acesso ao SQLite e migrações versionadas do banco de dados."""
import logging
import sqlite3
from contextlib import contextmanager

from flask import current_app

logger = logging.getLogger(__name__)


@contextmanager
def db():
    """Abre uma conexão, confirma (commit) ao final, desfaz (rollback) se der erro e sempre fecha."""
    conn = sqlite3.connect(current_app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # faz o ON DELETE CASCADE funcionar
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------- migrações
# Cada migração é idempotente (pode rodar em um banco novo ou em um banco antigo).
# O número da versão fica gravado no próprio arquivo do banco (PRAGMA user_version).

def _m1_tabelas_base(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','student'))
    );
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        event_date TEXT NOT NULL,
        event_time TEXT NOT NULL,
        location TEXT NOT NULL,
        capacity INTEGER NOT NULL CHECK(capacity > 0),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
        attended INTEGER NOT NULL DEFAULT 0,
        UNIQUE(user_id, event_id)
    );
    CREATE INDEX IF NOT EXISTS idx_registrations_event ON registrations(event_id);
    """)


def _m2_categoria_e_capa(con):
    columns = [row["name"] for row in con.execute("PRAGMA table_info(events)")]
    if "category" not in columns:
        con.execute("ALTER TABLE events ADD COLUMN category TEXT NOT NULL DEFAULT 'Outro'")
    if "cover_url" not in columns:
        con.execute("ALTER TABLE events ADD COLUMN cover_url TEXT NOT NULL DEFAULT ''")


def _m3_lista_de_espera(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS waitlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, event_id)
    );
    CREATE INDEX IF NOT EXISTS idx_waitlist_event ON waitlist(event_id, id);
    """)


def _m4_limite_de_tentativas(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS rate_limits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_rate_limits_key ON rate_limits(key, created_at);
    """)


MIGRATIONS = [
    (1, "tabelas base (usuários, eventos, inscrições)", _m1_tabelas_base),
    (2, "categoria e capa nos eventos", _m2_categoria_e_capa),
    (3, "lista de espera", _m3_lista_de_espera),
    (4, "limite de tentativas (login e recuperação de senha)", _m4_limite_de_tentativas),
]


def run_migrations():
    """Aplica, em ordem, só as migrações que o banco ainda não recebeu."""
    with db() as con:
        current = con.execute("PRAGMA user_version").fetchone()[0]
        for version, description, apply in MIGRATIONS:
            if version > current:
                logger.info("Aplicando migração %s: %s", version, description)
                apply(con)
                con.execute(f"PRAGMA user_version = {int(version)}")
