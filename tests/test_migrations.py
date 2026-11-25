import os
import sqlite3
import tempfile
import unittest

from eventmanager import create_app
from eventmanager.db import MIGRATIONS


class MigrationTests(unittest.TestCase):
    def test_banco_antigo_e_atualizado_sem_perder_dados(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, "antigo.db")
            con = sqlite3.connect(caminho)                # banco no formato da primeira versão do projeto
            con.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL);
            CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL, event_date TEXT NOT NULL, event_time TEXT NOT NULL, location TEXT NOT NULL, capacity INTEGER NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE registrations (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, event_id INTEGER NOT NULL, registered_at TEXT DEFAULT CURRENT_TIMESTAMP, attended INTEGER NOT NULL DEFAULT 0, UNIQUE(user_id, event_id));
            INSERT INTO events(title,description,event_date,event_time,location,capacity) VALUES('Antigo','d','2030-01-01','09:00','Sala',10);
            """)
            con.commit(); con.close()
            for _ in range(2):                            # rodar duas vezes: as migrações são idempotentes
                create_app({"TESTING": True, "DATABASE": caminho, "UPLOAD_FOLDER": os.path.join(tmp, "u")})
            con = sqlite3.connect(caminho)
            colunas = [r[1] for r in con.execute("PRAGMA table_info(events)")]
            self.assertIn("category", colunas)
            self.assertIn("cover_url", colunas)
            self.assertEqual(con.execute("SELECT category, cover_url FROM events").fetchone(), ("Outro", ""))
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], MIGRATIONS[-1][0])
            con.execute("SELECT * FROM waitlist")         # as tabelas novas existem
            con.execute("SELECT * FROM rate_limits")
            con.close()
