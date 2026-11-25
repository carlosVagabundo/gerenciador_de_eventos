import os

from .base import PNG, AppTestCase, future, past


class EventTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.new_user("Chefe", "chefe@x.com", admin=True)

    def test_permissoes(self):
        aluno = self.new_user("Ana", "ana@x.com")
        self.assertEqual(aluno.get("/events/new").status_code, 403)
        self.assertEqual(self.client.get("/events").status_code, 302)

    def test_cadastro_valida_e_escapa_html(self):
        r = self.admin.post("/events/new", data=self.event_data(capacity="0"), follow_redirects=True)
        self.assertIn("entre 1 e 100000".encode(), r.data)
        r = self.admin.post("/events/new", data=self.event_data(event_date="31/12/2030"), follow_redirects=True)
        self.assertIn("data e um hor".encode(), r.data)
        self.admin.post("/events/new", data=self.event_data(title="<b>X</b>"), follow_redirects=True)
        pagina = self.admin.get("/events").data.decode()
        self.assertIn("&lt;b&gt;X&lt;/b&gt;", pagina)
        self.assertNotIn("<b>X</b>", pagina)

    def test_filtros(self):
        self.create_event(self.admin, title="A", category="Curso")
        self.create_event(self.admin, title="B", category="Feira")
        self.create_event(self.admin, title="Antigo", category="Curso", event_date=past())
        cartoes = lambda url: self.admin.get(url).data.count(b'class="event-card"')
        self.assertEqual(cartoes("/events"), 3)
        self.assertEqual(cartoes("/events?category=Curso"), 2)
        self.assertEqual(cartoes("/events?period=upcoming"), 2)
        self.assertEqual(cartoes("/events?period=past"), 1)
        self.assertEqual(cartoes("/events?q=antigo"), 1)
        self.assertEqual(self.admin.get("/events?q=%25").status_code, 200)    # % é tratado como texto

    def test_paginacao(self):
        for i in range(7):
            self.create_event(self.admin, title=f"Evento {i}", event_date=future(10 + i))
        cartoes = lambda url: self.admin.get(url).data.count(b'class="event-card"')
        self.assertEqual(cartoes("/events"), 3)
        self.assertEqual(cartoes("/events?page=2"), 3)
        self.assertEqual(cartoes("/events?page=3"), 1)
        self.assertEqual(cartoes("/events?page=99"), 1)                       # página inexistente: usa a última
        self.assertEqual(cartoes("/events?page=abc"), 3)                      # valor inválido: página 1
        html = self.admin.get("/events?category=Palestra&page=2").data.decode()
        self.assertIn("page=3&amp;category=Palestra", html)                   # filtros preservados nos links
        self.assertIn('aria-current="page"', html)

    def test_edicao_nao_reduz_vagas_abaixo_dos_inscritos(self):
        ev = self.create_event(self.admin, capacity="3")
        for i in range(2):
            self.new_user(f"U{i}", f"u{i}@x.com").post(f"/events/{ev}/join")
        data = self.event_data(capacity="1")
        r = self.admin.post(f"/events/{ev}/edit", data=data, follow_redirects=True)
        self.assertIn("menor que o número de inscritos".encode(), r.data)
        r = self.admin.post(f"/events/{ev}/edit", data=self.event_data(capacity="4", title="Novo nome"),
                            follow_redirects=True)
        self.assertIn("Evento atualizado".encode(), r.data)


class CoverUploadTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.new_user("Chefe", "chefe@x.com", admin=True)

    def enviar(self, conteudo, nome="capa.png", **extra):
        from io import BytesIO
        data = self.event_data(**extra)
        data["cover_file"] = (BytesIO(conteudo), nome)
        return self.admin.post("/events/new", data=data, content_type="multipart/form-data",
                               follow_redirects=True)

    def arquivos(self):
        pasta = self.app.config["UPLOAD_FOLDER"]
        return os.listdir(pasta) if os.path.isdir(pasta) else []

    def test_upload_valido_e_servido(self):
        r = self.enviar(PNG, title="Com capa")
        self.assertIn("cadastrado com sucesso".encode(), r.data)
        url = self.query("SELECT cover_url FROM events")[0]["cover_url"]
        self.assertTrue(url.startswith("/static/uploads/") and url.endswith(".png"))
        self.assertEqual(len(self.arquivos()), 1)
        self.assertIn(url.encode(), self.admin.get("/events").data)

    def test_upload_rejeita_arquivo_falso_e_grande(self):
        r = self.enviar(b"isto nao e uma imagem", nome="foto.png")
        self.assertIn("PNG, JPG, GIF ou WEBP".encode(), r.data)
        r = self.enviar(PNG + b"0" * (3 * 1024 * 1024), nome="grande.png")
        self.assertIn("grande demais".encode(), r.data)
        self.assertEqual(self.arquivos(), [])
        self.assertEqual(self.query("SELECT COUNT(*) AS n FROM events")[0]["n"], 0)

    def test_trocar_remover_e_excluir_apagam_arquivos(self):
        self.enviar(PNG, title="E1")
        ev = self.query("SELECT id FROM events")[0]["id"]
        antigo = self.arquivos()[0]
        from io import BytesIO
        data = self.event_data(title="E1")
        data["cover_file"] = (BytesIO(PNG + b"1"), "outra.png")
        self.admin.post(f"/events/{ev}/edit", data=data, content_type="multipart/form-data")
        self.assertEqual(len(self.arquivos()), 1)
        self.assertNotIn(antigo, self.arquivos())                              # a capa antiga foi apagada
        data = self.event_data(title="E1"); data["remove_cover"] = "1"
        self.admin.post(f"/events/{ev}/edit", data=data, content_type="multipart/form-data")
        self.assertEqual(self.arquivos(), [])
        self.assertEqual(self.query("SELECT cover_url FROM events")[0]["cover_url"], "")
        self.enviar(PNG, title="E2")
        ev2 = self.query("SELECT id FROM events WHERE title='E2'")[0]["id"]
        self.admin.post(f"/events/{ev2}/delete")
        self.assertEqual(self.arquivos(), [])

    def test_link_externo_e_mantem_capa_na_edicao(self):
        self.admin.post("/events/new", data=self.event_data(cover_url="javascript:alert(1)"),
                        follow_redirects=True)
        self.assertEqual(self.query("SELECT COUNT(*) AS n FROM events")[0]["n"], 0)
        self.admin.post("/events/new", data=self.event_data(cover_url="https://exemplo.com/a.jpg"))
        ev = self.query("SELECT id FROM events")[0]["id"]
        self.admin.post(f"/events/{ev}/edit", data=self.event_data(title="Renomeado"))
        linha = self.query("SELECT title, cover_url FROM events")[0]
        self.assertEqual(linha["cover_url"], "https://exemplo.com/a.jpg")      # sem novo envio: mantém
        self.assertEqual(linha["title"], "Renomeado")


class CsvExportTests(AppTestCase):
    def test_exporta_participantes_e_fila_com_protecao_de_formula(self):
        admin = self.new_user("Chefe", "chefe@x.com", admin=True)
        ev = self.create_event(admin, capacity="1")
        ana = self.new_user("=HYPERLINK(1)", "ana@x.com")                  # nome malicioso (injeção de fórmula)
        bia = self.new_user("Bia", "bia@x.com")
        ana.post(f"/events/{ev}/join")
        bia.post(f"/events/{ev}/waitlist")
        r = admin.get(f"/events/{ev}/participants.csv")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "text/csv")
        self.assertIn("attachment", r.headers["Content-Disposition"])
        texto = r.data.decode("utf-8")
        self.assertTrue(texto.startswith("\ufeffNome;E-mail;Situação;Presença"))
        self.assertIn("'=HYPERLINK(1);ana@x.com;Inscrito;Pendente", texto)     # apóstrofo neutraliza a fórmula
        self.assertIn("Bia;bia@x.com;Lista de espera (1º);-", texto)
        self.assertEqual(self.app.test_client().get(f"/events/{ev}/participants.csv").status_code, 302)
        self.assertEqual(ana.get(f"/events/{ev}/participants.csv").status_code, 403)
