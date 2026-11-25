from .base import AppTestCase, future


class CalendarTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.new_user("Chefe", "chefe@x.com", admin=True)
        self.ev = self.create_event(self.admin, title="Feira, de ciências; 2026", description="Linha 1\nLinha 2 " + "x" * 120,
                                    event_time="14:30", location="Auditório, bloco A")

    def test_arquivo_ics(self):
        r = self.admin.get(f"/events/{self.ev}/calendar.ics")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.mimetype == "text/calendar")
        self.assertIn("attachment", r.headers["Content-Disposition"])
        texto = r.data.decode()
        self.assertTrue(texto.startswith("BEGIN:VCALENDAR\r\n") and texto.endswith("END:VCALENDAR\r\n"))
        dia = future().replace("-", "")
        self.assertIn(f"DTSTART:{dia}T143000", texto)
        self.assertIn(f"DTEND:{dia}T163000", texto)
        self.assertIn("SUMMARY:Feira\\, de ciências\\; 2026", texto)     # vírgula e ponto e vírgula escapados
        self.assertIn("LOCATION:Auditório\\, bloco A", texto)
        for linha in texto.split("\r\n"):
            self.assertLessEqual(len(linha.encode("utf-8")), 75)           # linhas longas foram dobradas

    def test_link_google_e_acesso(self):
        ana = self.new_user("Ana", "ana@x.com")
        ana.post(f"/events/{self.ev}/join")
        html = ana.get("/dashboard").data.decode()
        self.assertIn("calendar.google.com/calendar/render?action=TEMPLATE", html)
        self.assertIn("calendar.ics", html)
        self.assertEqual(self.client.get(f"/events/{self.ev}/calendar.ics").status_code, 302)
        self.assertEqual(ana.get("/events/9999/calendar.ics").status_code, 404)
