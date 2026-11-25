"""Proteção CSRF e verificação de que todos os formulários POST carregam o token."""
import re
from html.parser import HTMLParser

from .base import AppTestCase


def token_de(html):
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


class CsrfTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.app.config["CSRF_ENABLED"] = True

    def dados(self, **extra):
        d = {"name": "Ana", "email": "ana@x.com", "password": "abc123", "password2": "abc123"}
        d.update(extra)
        return d

    def test_post_sem_token_e_recusado(self):
        r = self.client.post("/register", data=self.dados())
        self.assertEqual(r.status_code, 400)
        self.assertIn("Formulário expirado".encode(), r.data)
        self.assertEqual(self.query("SELECT COUNT(*) AS n FROM users")[0]["n"], 0)

    def test_token_errado_e_recusado(self):
        self.client.get("/register")
        r = self.client.post("/register", data=self.dados(csrf_token="invalido"))
        self.assertEqual(r.status_code, 400)

    def test_post_com_token_correto_funciona(self):
        token = token_de(self.client.get("/register").data.decode())
        r = self.client.post("/register", data=self.dados(csrf_token=token), follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.query("SELECT COUNT(*) AS n FROM users")[0]["n"], 1)

    def test_token_e_estavel_na_sessao_e_diferente_entre_sessoes(self):
        outro = self.app.test_client()
        a1 = token_de(self.client.get("/login").data.decode())
        a2 = token_de(self.client.get("/register").data.decode())
        b = token_de(outro.get("/login").data.decode())
        self.assertEqual(a1, a2)
        self.assertNotEqual(a1, b)
        self.assertEqual(outro.post("/register", data=self.dados(csrf_token=a1)).status_code, 400)   # token de outra sessão

    def test_logout_so_por_post_com_token(self):
        self.app.config["CSRF_ENABLED"] = False
        user = self.new_user("Ana", "ana@x.com")
        self.app.config["CSRF_ENABLED"] = True
        self.assertEqual(user.get("/logout").status_code, 405)              # GET não desloga mais
        self.assertEqual(user.post("/logout").status_code, 400)             # sem token
        token = token_de(user.get("/dashboard").data.decode())
        self.assertEqual(user.post("/logout", data={"csrf_token": token}).status_code, 302)
        self.assertEqual(user.get("/dashboard").status_code, 302)           # sessão encerrada


class FormScanner(HTMLParser):
    """Lê o HTML e anota quais formulários POST não têm o campo csrf_token."""
    def __init__(self):
        super().__init__()
        self.current = None
        self.sem_token = []
        self.total = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form" and (a.get("method") or "get").lower() == "post":
            self.current = {"action": a.get("action", "?"), "token": False}
            self.total += 1
        elif tag == "input" and self.current is not None and a.get("name") == "csrf_token":
            self.current["token"] = True

    def handle_endtag(self, tag):
        if tag == "form" and self.current is not None:
            if not self.current["token"]:
                self.sem_token.append(self.current["action"])
            self.current = None


class TodosOsFormulariosTemTokenTests(AppTestCase):
    def test_nenhuma_pagina_tem_formulario_post_sem_token(self):
        admin = self.new_user("Chefe", "chefe@x.com", admin=True)
        ev = self.create_event(admin, capacity="1")
        ana = self.new_user("Ana", "ana@x.com")
        bia = self.new_user("Bia", "bia@x.com")
        ana.post(f"/events/{ev}/join")
        bia.post(f"/events/{ev}/waitlist")
        paginas = [(self.client, "/"), (self.client, "/login"), (self.client, "/register"),
                   (self.client, "/forgot-password"), (admin, "/dashboard"), (admin, "/events"),
                   (admin, f"/events/{ev}/edit"), (admin, "/events/new"), (admin, f"/events/{ev}/participants"),
                   (admin, "/admin/users"), (admin, "/account"), (ana, "/dashboard"), (ana, "/events"),
                   (bia, "/dashboard"), (bia, "/events"), (ana, "/account")]
        total = 0
        for cliente, url in paginas:
            with self.subTest(pagina=url):
                scanner = FormScanner()
                scanner.feed(cliente.get(url).data.decode())
                total += scanner.total
                self.assertEqual(scanner.sem_token, [], f"formulário sem token em {url}")
        self.assertGreater(total, 20)           # garante que o teste realmente encontrou formulários


class FluxoCompletoComCsrfTests(AppTestCase):
    """Usa o site como um navegador de verdade, com o CSRF LIGADO: busca o token na página e envia no POST."""

    def setUp(self):
        super().setUp()
        self.app.config["CSRF_ENABLED"] = True

    def enviar(self, cliente, pagina, acao, dados=None, **kwargs):
        token = token_de(cliente.get(pagina).data.decode())
        return cliente.post(acao, data={**(dados or {}), "csrf_token": token}, **kwargs)

    def test_fluxo_de_ponta_a_ponta(self):
        from io import BytesIO

        from .base import PNG, future
        admin, ana = self.app.test_client(), self.app.test_client()
        # cadastro e login do administrador e do aluno
        r = self.enviar(admin, "/register", "/register", {"name": "Chefe", "email": "chefe@x.com", "password": "abc123",
                                                          "password2": "abc123", "admin_code": "codigo-teste"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.enviar(admin, "/login", "/login", {"email": "chefe@x.com", "password": "abc123"}).status_code, 302)
        self.enviar(ana, "/register", "/register", {"name": "Ana", "email": "ana@x.com", "password": "abc123", "password2": "abc123"})
        self.enviar(ana, "/login", "/login", {"email": "ana@x.com", "password": "abc123"})
        # evento com capa enviada (formulário multipart)
        r = self.enviar(admin, "/events/new", "/events/new", {
            "title": "Feira", "description": "d", "event_date": future(), "event_time": "10:00", "location": "L",
            "capacity": "1", "category": "Feira", "cover_file": (BytesIO(PNG), "capa.png")},
            content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)
        ev = self.query("SELECT id FROM events")[0]["id"]
        # inscrição, lista de espera e cancelamento com promoção
        self.assertEqual(self.enviar(ana, "/events", f"/events/{ev}/join").status_code, 302)
        bia = self.app.test_client()
        self.enviar(bia, "/register", "/register", {"name": "Bia", "email": "bia@x.com", "password": "abc123", "password2": "abc123"})
        self.enviar(bia, "/login", "/login", {"email": "bia@x.com", "password": "abc123"})
        self.enviar(bia, "/events", f"/events/{ev}/waitlist")
        self.enviar(ana, "/events", f"/events/{ev}/leave")
        self.assertEqual([r["email"] for r in self.query("SELECT u.email FROM registrations r JOIN users u ON u.id=r.user_id")], ["bia@x.com"])
        # administração e conta
        ana_id = self.query("SELECT id FROM users WHERE email='ana@x.com'")[0]["id"]
        self.enviar(admin, "/admin/users", f"/admin/users/{ana_id}/role")
        self.assertEqual(self.query("SELECT role FROM users WHERE id=?", (ana_id,))[0]["role"], "admin")
        r = self.enviar(ana, "/account", "/account/password", {"current_password": "abc123", "new_password": "nova123",
                                                               "confirm_password": "nova123"}, follow_redirects=True)
        self.assertIn("alterada com sucesso".encode(), r.data)
        self.assertEqual(admin.get(f"/events/{ev}/participants.csv").status_code, 200)
        # sair
        self.assertEqual(self.enviar(admin, "/dashboard", "/logout").status_code, 302)
        self.assertEqual(admin.get("/dashboard").status_code, 302)
