import os
import sqlite3
import unittest
from unittest.mock import patch

import manage
from eventmanager.db import db
from werkzeug.security import generate_password_hash

from .base import AppTestCase


class ManageTests(AppTestCase):
    def add(self, email, role):
        with self.app.app_context():
            with db() as con:
                con.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                            (email, email, generate_password_hash("x12345"), role))

    def test_remove_demo_exige_outro_admin(self):
        self.add("admin@eventmanager.local", "admin")
        self.add("aluno@eventmanager.local", "student")
        with self.app.app_context():
            with self.assertRaises(SystemExit):
                manage.remove_demo(None)
        self.assertEqual(len(self.query("SELECT 1 FROM users")), 2)
        self.add("meu@admin.com", "admin")
        with self.app.app_context():
            manage.remove_demo(None)
        self.assertEqual([r["email"] for r in self.query("SELECT email FROM users")], ["meu@admin.com"])

    def test_create_admin_e_reset_password(self):
        class Args:
            email = "novo@admin.com"; name = "Novo"
        with self.app.app_context(), patch("manage.ask_password", return_value="senha123"):
            manage.create_admin(Args)
            manage.reset_password(Args)
        self.assertEqual(self.query("SELECT role FROM users")[0]["role"], "admin")
        self.assertEqual(self.login(self.app.test_client(), "novo@admin.com", "senha123").status_code, 302)


class BackupTests(AppTestCase):
    def test_backup_cria_copia_valida_e_apaga_as_mais_antigas(self):
        self.new_user("Ana", "ana@x.com")
        pasta = os.path.join(self.tmp.name, "bkp")

        class Args:
            folder = pasta; keep = 2
        with self.app.app_context():
            for nome in ("eventmanager-20200101-000000.db", "eventmanager-20200102-000000.db"):
                os.makedirs(pasta, exist_ok=True)
                open(os.path.join(pasta, nome), "w").close()                # cópias antigas falsas
            manage.backup(Args)
        arquivos = sorted(os.listdir(pasta))
        self.assertEqual(len(arquivos), 2)                                  # só as 2 mais recentes ficam
        self.assertNotIn("eventmanager-20200101-000000.db", arquivos)
        copia = sqlite3.connect(os.path.join(pasta, arquivos[-1]))
        self.assertEqual(copia.execute("SELECT email FROM users").fetchone()[0], "ana@x.com")
        copia.close()
