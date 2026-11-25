from unittest.mock import patch

from .base import AppTestCase, future, past


class RegistrationTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.new_user("Chefe", "chefe@x.com", admin=True)
        self.ana = self.new_user("Ana", "ana@x.com")
        self.bia = self.new_user("Bia", "bia@x.com")
        self.davi = self.new_user("Davi", "davi@x.com")

    def inscritos(self, ev):
        return [r["name"] for r in self.query(
            "SELECT u.name FROM registrations r JOIN users u ON u.id=r.user_id WHERE r.event_id=? ORDER BY r.id", (ev,))]

    def fila(self, ev):
        return [r["name"] for r in self.query(
            "SELECT u.name FROM waitlist w JOIN users u ON u.id=w.user_id WHERE w.event_id=? ORDER BY w.id", (ev,))]

    def test_inscricao_duplicada_e_cancelamento(self):
        ev = self.create_event(self.admin)
        self.assertIn("realizada".encode(), self.ana.post(f"/events/{ev}/join", follow_redirects=True).data)
        self.assertIn("já está inscrito".encode(), self.ana.post(f"/events/{ev}/join", follow_redirects=True).data)
        self.assertIn("cancelada".encode(), self.ana.post(f"/events/{ev}/leave", follow_redirects=True).data)
        self.assertIn("não está inscrito".encode(), self.ana.post(f"/events/{ev}/leave", follow_redirects=True).data)

    def test_evento_encerrado_nao_aceita_inscricao_nem_fila(self):
        ev = self.create_event(self.admin, event_date=past())
        self.assertIn("encerrado".encode(), self.ana.post(f"/events/{ev}/join", follow_redirects=True).data)
        self.assertIn("encerrado".encode(), self.ana.post(f"/events/{ev}/waitlist", follow_redirects=True).data)

    def test_presenca_confirmada_nao_pode_cancelar(self):
        ev = self.create_event(self.admin)
        self.ana.post(f"/events/{ev}/join")
        reg = self.query("SELECT id FROM registrations")[0]["id"]
        self.admin.post(f"/registrations/{reg}/attendance")
        r = self.ana.post(f"/events/{ev}/leave", follow_redirects=True)
        self.assertIn("presença já foi confirmada".encode(), r.data)
        self.assertIn("Certificamos que".encode(), self.ana.get("/certificates").data)

    def test_lista_de_espera_promove_na_ordem(self):
        ev = self.create_event(self.admin, capacity="1")
        self.ana.post(f"/events/{ev}/join")
        self.assertIn("As vagas acabaram".encode(), self.bia.post(f"/events/{ev}/join", follow_redirects=True).data)
        self.assertIn("posição 1".encode(), self.bia.post(f"/events/{ev}/waitlist", follow_redirects=True).data)
        self.assertIn("posição 2".encode(), self.davi.post(f"/events/{ev}/waitlist", follow_redirects=True).data)
        self.assertIn("já está na lista".encode(), self.bia.post(f"/events/{ev}/waitlist", follow_redirects=True).data)
        self.assertIn("1º".encode(), self.bia.get("/events").data)
        with patch("eventmanager.waitlist.send_email") as send:
            self.ana.post(f"/events/{ev}/leave")               # a vaga vai para a Bia
        self.assertEqual(self.inscritos(ev), ["Bia"])
        self.assertEqual(self.fila(ev), ["Davi"])
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args[0][0], "bia@x.com")

    def test_nao_entra_na_fila_se_ha_vaga_e_pode_sair_da_fila(self):
        ev = self.create_event(self.admin, capacity="1")
        self.assertIn("Ainda há vagas".encode(), self.ana.post(f"/events/{ev}/waitlist", follow_redirects=True).data)
        self.ana.post(f"/events/{ev}/join")
        self.bia.post(f"/events/{ev}/waitlist")
        self.assertIn("saiu da lista".encode(), self.bia.post(f"/events/{ev}/waitlist/leave", follow_redirects=True).data)
        self.assertEqual(self.fila(ev), [])

    def test_aumentar_vagas_chama_a_fila(self):
        ev = self.create_event(self.admin, capacity="1")
        self.ana.post(f"/events/{ev}/join")
        self.bia.post(f"/events/{ev}/waitlist")
        self.davi.post(f"/events/{ev}/waitlist")
        r = self.admin.post(f"/events/{ev}/edit", data=self.event_data(capacity="3"), follow_redirects=True)
        self.assertIn("2 pessoa(s) saíram da lista".encode(), r.data)
        self.assertEqual(self.inscritos(ev), ["Ana", "Bia", "Davi"])
        self.assertEqual(self.fila(ev), [])

    def test_excluir_conta_libera_vaga_para_a_fila(self):
        ev = self.create_event(self.admin, capacity="1")
        self.ana.post(f"/events/{ev}/join")
        self.bia.post(f"/events/{ev}/waitlist")
        self.ana.post("/account/delete", data={"password": "abc123"})
        self.assertEqual(self.inscritos(ev), ["Bia"])

    def test_nao_estoura_o_limite_de_vagas(self):
        ev = self.create_event(self.admin, capacity="2")
        for cliente in (self.ana, self.bia, self.davi):
            cliente.post(f"/events/{ev}/join")
        self.assertEqual(len(self.inscritos(ev)), 2)

    def test_redirecionamento_externo_e_bloqueado(self):
        ev = self.create_event(self.admin)
        r = self.ana.post(f"/events/{ev}/join", headers={"Referer": "https://site-malicioso.com/x"})
        self.assertNotIn("site-malicioso", r.headers["Location"])

    def test_participantes_mostra_fila(self):
        ev = self.create_event(self.admin, capacity="1")
        self.ana.post(f"/events/{ev}/join")
        self.bia.post(f"/events/{ev}/waitlist")
        html = self.admin.get(f"/events/{ev}/participants").data.decode()
        self.assertIn("Ana", html)
        self.assertIn("Lista de espera", html)
        self.assertIn("Bia", html)
