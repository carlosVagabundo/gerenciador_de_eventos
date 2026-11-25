"""Base comum dos testes: cria um app com banco temporário e funções de apoio."""
import os
import tempfile
import unittest
from datetime import date, timedelta

from eventmanager import create_app
from eventmanager.db import db

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200


def future(days=10):
    return (date.today() + timedelta(days=days)).isoformat()


def past(days=5):
    return (date.today() - timedelta(days=days)).isoformat()


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True, "SECRET_KEY": "teste", "ADMIN_CODE": "codigo-teste",
            "DATABASE": os.path.join(self.tmp.name, "teste.db"),
            "UPLOAD_FOLDER": os.path.join(self.tmp.name, "uploads"),
            "EVENTS_PER_PAGE": 3, "LOG_LEVEL": "CRITICAL", "USERS_PER_PAGE": 3,
            "CSRF_ENABLED": False,        # os testes de CSRF ligam de novo (test_security.py)
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    # ---------- apoio ----------
    def query(self, sql, params=()):
        with self.app.app_context():
            with db() as con:
                return [dict(row) for row in con.execute(sql, params).fetchall()]

    def register(self, client, name, email, password="abc123", **extra):
        data = {"name": name, "email": email, "password": password, "password2": password}
        data.update(extra)
        return client.post("/register", data=data, follow_redirects=True)

    def login(self, client, email, password="abc123"):
        return client.post("/login", data={"email": email, "password": password})

    def new_user(self, name, email, admin=False):
        """Cria a conta, entra e devolve um cliente já logado."""
        client = self.app.test_client()
        extra = {"admin_code": "codigo-teste"} if admin else {}
        self.register(client, name, email, **extra)
        self.login(client, email)
        return client

    def event_data(self, **overrides):
        data = {"title": "Evento", "description": "Descrição", "event_date": future(),
                "event_time": "10:00", "location": "Sala 1", "capacity": "5", "category": "Palestra"}
        data.update(overrides)
        return data

    def create_event(self, admin, **overrides):
        data = self.event_data(**overrides)
        admin.post("/events/new", data=data, follow_redirects=True)
        return self.query("SELECT id FROM events WHERE title = ?", (data["title"],))[-1]["id"]
