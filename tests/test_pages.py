"""Páginas públicas, painéis, páginas de erro e verificações básicas de acessibilidade."""
import re

from .base import AppTestCase, future


class PageTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.new_user("Chefe", "chefe@x.com", admin=True)
        self.ev = self.create_event(self.admin, title="Feira de Ciências", capacity="1")
        self.ana = self.new_user("Ana", "ana@x.com")
        self.bia = self.new_user("Bia", "bia@x.com")

    def test_home_publica_lista_eventos_sem_dados_pessoais(self):
        html = self.client.get("/").data.decode()
        self.assertIn("Feira de Ciências", html)
        self.assertIn("Entrar para participar", html)
        self.assertNotIn("ana@x.com", html)
        self.assertNotIn("Inscrever-se", html)

    def test_paineis(self):
        self.ana.post(f"/events/{self.ev}/join")
        self.bia.post(f"/events/{self.ev}/waitlist")
        admin = self.admin.get("/dashboard").data.decode()
        self.assertIn("Inscrições nos últimos 7 dias", admin)
        self.assertIn("Na lista de espera", admin)
        aluno = self.bia.get("/dashboard").data.decode()
        self.assertIn("Na lista de espera", aluno)
        self.assertIn("Lista de espera: 1º", aluno)

    def test_paginas_de_erro(self):
        self.assertEqual(self.client.get("/nao-existe").status_code, 404)
        self.assertEqual(self.ana.get("/events/new").status_code, 403)
        grande = self.event_data(); grande["cover_file"] = (__import__("io").BytesIO(b"0" * (6 * 1024 * 1024)), "x.png")
        r = self.admin.post("/events/new", data=grande, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 413)

    def test_cabecalhos_de_seguranca(self):
        r = self.client.get("/")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")


class AccessibilityTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.new_user("Chefe", "chefe@x.com", admin=True)
        self.create_event(self.admin, title="Evento A", capacity="1")
        self.create_event(self.admin, title="Evento B", cover_url="https://exemplo.com/a.jpg")

    def paginas(self):
        return {"home": self.client.get("/").data.decode(), "login": self.client.get("/login").data.decode(),
                "eventos": self.admin.get("/events").data.decode(), "painel": self.admin.get("/dashboard").data.decode(),
                "conta": self.admin.get("/account").data.decode(), "novo": self.admin.get("/events/new").data.decode()}

    def test_estrutura_basica(self):
        for nome, html in self.paginas().items():
            with self.subTest(pagina=nome):
                self.assertIn('lang="pt-br"', html)
                self.assertIn('class="skip-link" href="#conteudo"', html)
                self.assertIn('<main id="conteudo"', html)
                self.assertEqual(html.count("<h1"), 1)                        # um único título principal

    def test_imagens_tem_alt_e_barras_tem_papel(self):
        html = self.paginas()["eventos"]
        for tag in re.findall(r"<img[^>]*>", html):
            self.assertIn("alt=", tag)
        self.assertIn('role="progressbar"', html)
        self.assertIn('aria-valuenow=', html)

    def test_navegacao_marca_pagina_atual(self):
        self.assertIn('aria-current="page"', self.paginas()["eventos"])

    def test_campos_de_formulario_tem_rotulo(self):
        for nome in ("login", "novo", "conta"):
            html = self.paginas()[nome]
            for campo in re.findall(r"<input(?![^>]*type=\"(?:hidden|checkbox)\")[^>]*>", html):
                with self.subTest(pagina=nome, campo=campo[:60]):
                    self.assertIn("<label", html)        # todo campo está dentro de um <label>
        # filtros de busca: rótulos só para leitores de tela
        self.assertIn('<span class="sr-only">Pesquisar eventos</span>', self.paginas()["eventos"])

    def test_avisos_tem_papel(self):
        r = self.client.post("/login", data={"email": "x@x.com", "password": "errada"})
        self.assertIn('role="alert"', r.data.decode())
