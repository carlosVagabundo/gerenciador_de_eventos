from unittest.mock import patch

from eventmanager.db import db

from .base import AppTestCase


class AuthTests(AppTestCase):
    def test_nao_existem_contas_ficticias(self):
        self.assertEqual(self.query("SELECT COUNT(*) AS n FROM users")[0]["n"], 0)
        self.assertNotIn(b"Admin123", self.client.get("/login").data)

    def test_cadastro_valida_campos(self):
        r = self.register(self.client, "Ana", "email-invalido")
        self.assertIn("e-mail válido".encode(), r.data)
        r = self.client.post("/register", data={"name": "Ana", "email": "a@x.com", "password": "abc123",
                                               "password2": "outra"}, follow_redirects=True)
        self.assertIn("não são iguais".encode(), r.data)
        r = self.register(self.client, "Ana", "a@x.com", password="123")
        self.assertIn("entre 6 e 128".encode(), r.data)

    def test_cadastro_login_e_logout(self):
        r = self.register(self.client, "Ana Souza", "ana@x.com")
        self.assertIn("Conta criada".encode(), r.data)
        self.assertIn("já está cadastrado".encode(), self.register(self.client, "Ana", "ana@x.com").data)
        self.assertEqual(self.login(self.client, "ana@x.com", "errada").status_code, 200)
        self.assertEqual(self.login(self.client, "ana@x.com").status_code, 302)
        self.assertEqual(self.client.get("/dashboard").status_code, 200)
        self.client.post("/logout")
        self.assertEqual(self.client.get("/dashboard").status_code, 302)

    def test_codigo_de_administrador(self):
        r = self.register(self.client, "Chefe", "c@x.com", admin_code="errado")
        self.assertIn("inválido".encode(), r.data)
        self.assertEqual(self.query("SELECT COUNT(*) AS n FROM users")[0]["n"], 0)
        self.register(self.client, "Chefe", "c@x.com", admin_code="codigo-teste")
        self.assertEqual(self.query("SELECT role FROM users")[0]["role"], "admin")

    def test_campo_admin_some_sem_codigo_configurado(self):
        self.app.config["ADMIN_CODE"] = ""
        self.assertNotIn(b"admin_code", self.client.get("/register").data)

    def test_pagina_inicial_publica(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Criar minha conta", r.data)
        user = self.new_user("Ana", "ana@x.com")
        self.assertEqual(user.get("/").status_code, 302)       # logado vai para o painel

    def test_sessao_invalida_quando_conta_some(self):
        user = self.new_user("Ana", "ana@x.com")
        with self.app.app_context():
            with db() as con:
                con.execute("DELETE FROM users")
        self.assertEqual(user.get("/dashboard").status_code, 302)


class PasswordResetTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.register(self.client, "Ana", "ana@x.com")

    def pedir_link(self, email="ana@x.com"):
        with patch("eventmanager.blueprints.auth.send_email") as send:
            r = self.client.post("/forgot-password", data={"email": email}, follow_redirects=True)
        return r, send

    def test_resposta_igual_para_email_inexistente(self):
        r1, send1 = self.pedir_link("ninguem@x.com")
        r2, send2 = self.pedir_link("ana@x.com")
        self.assertIn("Se o e-mail estiver cadastrado".encode(), r1.data)
        self.assertIn("Se o e-mail estiver cadastrado".encode(), r2.data)
        send1.assert_not_called()
        send2.assert_called_once()

    def test_fluxo_completo_e_link_de_uso_unico(self):
        _, send = self.pedir_link()
        corpo = send.call_args[0][2]
        link = [p for p in corpo.split() if "/reset-password/" in p][0]
        caminho = "/reset-password/" + link.split("/reset-password/")[1]
        self.assertEqual(self.client.get(caminho).status_code, 200)
        r = self.client.post(caminho, data={"new_password": "nova123", "confirm_password": "diferente"})
        self.assertIn("não são iguais".encode(), r.data)
        r = self.client.post(caminho, data={"new_password": "nova123", "confirm_password": "nova123"},
                             follow_redirects=True)
        self.assertIn("Senha alterada".encode(), r.data)
        self.assertEqual(self.login(self.client, "ana@x.com", "abc123").status_code, 200)   # senha antiga falha
        self.assertEqual(self.login(self.client, "ana@x.com", "nova123").status_code, 302)
        self.client.post("/logout")
        self.assertEqual(self.client.get(caminho).status_code, 302)       # link já usado não vale mais

    def test_link_adulterado_ou_expirado(self):
        self.assertEqual(self.client.get("/reset-password/token-falso").status_code, 302)
        _, send = self.pedir_link()
        corpo = send.call_args[0][2]
        token = [p for p in corpo.split() if "/reset-password/" in p][0].split("/reset-password/")[1]
        self.app.config["RESET_TOKEN_MAX_AGE"] = -1                         # força expiração
        self.assertEqual(self.client.get("/reset-password/" + token).status_code, 302)


class RateLimitTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.register(self.client, "Ana", "ana@x.com")

    def tentar(self, senha, email="ana@x.com"):
        return self.client.post("/login", data={"email": email, "password": senha})

    def test_bloqueia_apos_cinco_erros_mesmo_com_senha_certa(self):
        for _ in range(5):
            self.assertEqual(self.tentar("errada").status_code, 200)
        r = self.tentar("abc123")                                 # senha correta, mas já bloqueado
        self.assertEqual(r.status_code, 429)
        self.assertIn("Muitas tentativas".encode(), r.data)

    def test_bloqueio_vale_tambem_para_email_inexistente(self):
        for _ in range(5):
            self.tentar("x", email="ninguem@x.com")
        self.assertEqual(self.tentar("x", email="ninguem@x.com").status_code, 429)   # não revela se a conta existe

    def test_bloqueio_expira_e_sucesso_zera_o_contador(self):
        for _ in range(5):
            self.tentar("errada")
        with self.app.app_context():
            from eventmanager.db import db
            with db() as con:                                       # simula 11 minutos depois
                con.execute("UPDATE rate_limits SET created_at = datetime('now', '-11 minutes')")
        self.assertEqual(self.tentar("abc123").status_code, 302)    # entrou
        self.client.post("/logout")
        for _ in range(3):
            self.tentar("errada")
        self.assertEqual(self.tentar("abc123").status_code, 302)    # 3 erros novos não bloqueiam (contador zerou)

    def test_pedidos_de_recuperacao_tem_limite(self):
        with patch("eventmanager.blueprints.auth.send_email") as send:
            for _ in range(5):
                r = self.client.post("/forgot-password", data={"email": "ana@x.com"}, follow_redirects=True)
                self.assertIn("Se o e-mail estiver cadastrado".encode(), r.data)   # resposta sempre igual
        self.assertEqual(send.call_count, 3)
