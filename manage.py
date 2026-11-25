"""Comandos de manutenção. Exemplos:

    python manage.py create-admin ana@email.com "Ana Souza"
    python manage.py reset-password ana@email.com
    python manage.py remove-demo
    python manage.py list-users
    python manage.py backup
"""
import argparse
import getpass
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from flask import current_app

from werkzeug.security import generate_password_hash

from eventmanager import create_app
from eventmanager.db import db

DEMO_EMAILS = ("admin@eventmanager.local", "aluno@eventmanager.local")


def ask_password():
    password = getpass.getpass("Nova senha (mínimo 6 caracteres): ")
    if len(password) < 6 or password != getpass.getpass("Repita a senha: "):
        sys.exit("Senha muito curta ou diferente da confirmação. Nada foi alterado.")
    return password


def create_admin(args):
    with db() as con:
        if con.execute("SELECT 1 FROM users WHERE email = ?", (args.email.lower(),)).fetchone():
            sys.exit("Já existe uma conta com esse e-mail.")
        con.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'admin')",
                    (args.name, args.email.lower(), generate_password_hash(ask_password())))
    print("Administrador criado.")


def reset_password(args):
    with db() as con:
        if not con.execute("SELECT 1 FROM users WHERE email = ?", (args.email.lower(),)).fetchone():
            sys.exit("Nenhuma conta com esse e-mail.")
        con.execute("UPDATE users SET password_hash = ? WHERE email = ?",
                    (generate_password_hash(ask_password()), args.email.lower()))
    print("Senha alterada.")


def remove_demo(_args):
    marks = ",".join("?" * len(DEMO_EMAILS))
    with db() as con:
        other_admins = con.execute(
            f"SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND email NOT IN ({marks})",
            DEMO_EMAILS).fetchone()["n"]
        if other_admins == 0:
            sys.exit("Crie antes o seu próprio administrador (create-admin): sem isso o site ficaria sem admin.")
        cur = con.execute(f"DELETE FROM users WHERE email IN ({marks})", DEMO_EMAILS)
    print(f"{cur.rowcount} conta(s) de demonstração removida(s).")


def list_users(_args):
    with db() as con:
        for row in con.execute("SELECT id, name, email, role FROM users ORDER BY id"):
            print(f"{row['id']:>3}  {row['role']:<8} {row['email']}  ({row['name']})")


def backup(args):
    """Copia o banco com a API de backup do SQLite (cópia consistente, mesmo com o site em uso)."""
    folder = Path(args.folder)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"eventmanager-{datetime.now():%Y%m%d-%H%M%S}.db"
    source, target = sqlite3.connect(current_app.config["DATABASE"]), sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    old = sorted(folder.glob("eventmanager-*.db"))[:-args.keep] if args.keep > 0 else []
    for path in old:                                  # mantém só as cópias mais recentes
        path.unlink()
    print(f"Backup criado: {destination}  (as capas enviadas em static/uploads não entram nesta cópia)")


def main():
    parser = argparse.ArgumentParser(description="Manutenção do EventManager")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-admin", help="cria uma conta de administrador")
    p.add_argument("email"); p.add_argument("name"); p.set_defaults(func=create_admin)
    p = sub.add_parser("reset-password", help="define uma nova senha para uma conta")
    p.add_argument("email"); p.set_defaults(func=reset_password)
    sub.add_parser("remove-demo", help="remove as contas fictícias").set_defaults(func=remove_demo)
    sub.add_parser("list-users", help="lista as contas").set_defaults(func=list_users)
    p = sub.add_parser("backup", help="copia o banco de dados para a pasta backups/")
    p.add_argument("--folder", default="backups"); p.add_argument("--keep", type=int, default=10)
    p.set_defaults(func=backup)
    args = parser.parse_args()
    with create_app().app_context():
        args.func(args)


if __name__ == "__main__":
    main()
