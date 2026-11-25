from unittest.mock import patch

from .base import AppTestCase


class AdminUsersTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.new_user("Chefe", "chefe@x.com", admin=True)
        self.ana = self.new_user("Ana", "ana@x.com")
        self.bia = self.new_user("Bia", "bia@x.com")

    def id_de(self, email):
        return self.query("SELECT id FROM users WHERE email = ?", (email,))[0]["id"]

    def test_so_administrador_acessa(self):
        self.assertEqual(self.ana.get("/admin/users").status_code, 403)
        self.assertEqual(self.client.get("/admin/users").status_code, 302)
        r = self.admin.get("/admin/users")
        self.assertEqual(r.status_code, 200)
        for nome in ("Chefe", "Ana", "Bia"):
            self.assertIn(nome.encode(), r.data)

    def test_busca_filtro_e_paginacao(self):
        for i in range(4):
            self.new_user(f"Extra{i}", f"extra{i}@x.com")                      # total: 7 usuários, 3 por página
        linhas = lambda url: self.admin.get(url).data.count(b'<td>') // 4     # 4 células por usuário
        self.assertEqual(linhas("/admin/users"), 3)
        self.assertEqual(linhas("/admin/users?page=3"), 1)
        self.assertEqual(linhas("/admin/users?q=extra"), 3)
        self.assertEqual(linhas("/admin/users?q=ana"), 1)
        self.assertEqual(linhas("/admin/users?role=admin"), 1)
        self.assertEqual(self.admin.get("/admin/users?q=%25").status_code, 200)
        self.assertIn("page=2&amp;q=extra", self.admin.get("/admin/users?q=extra").data.decode())   # filtro mantido nos links

    def test_mudar_tipo_de_conta(self):
        ana = self.id_de("ana@x.com")
        r = self.admin.post(f"/admin/users/{ana}/role", follow_redirects=True)
        self.assertIn("agora é administrador".encode(), r.data)
        self.assertEqual(self.ana.get("/admin/users").status_code, 200)         # Ana já acessa a área admin
        r = self.admin.post(f"/admin/users/{ana}/role", follow_redirects=True)
        self.assertIn("agora é aluno".encode(), r.data)
        self.assertEqual(self.ana.get("/admin/users").status_code, 403)

    def test_nao_altera_nem_exclui_a_si_mesmo_por_aqui(self):
        eu = self.id_de("chefe@x.com")
        self.assertIn("próprio tipo de conta".encode(), self.admin.post(f"/admin/users/{eu}/role", follow_redirects=True).data)
        self.assertIn("Minha conta".encode(), self.admin.post(f"/admin/users/{eu}/delete", follow_redirects=True).data)
        self.assertEqual(self.query("SELECT role FROM users WHERE id = ?", (eu,))[0]["role"], "admin")

    def test_aluno_nao_usa_as_acoes(self):
        bia = self.id_de("bia@x.com")
        self.assertEqual(self.ana.post(f"/admin/users/{bia}/delete").status_code, 403)
        self.assertEqual(self.ana.post(f"/admin/users/{bia}/role").status_code, 403)

    def test_excluir_usuario_libera_vaga_para_a_fila(self):
        ev = self.create_event(self.admin, capacity="1")
        self.ana.post(f"/events/{ev}/join")
        self.bia.post(f"/events/{ev}/waitlist")
        with patch("eventmanager.waitlist.send_email") as send:
            r = self.admin.post(f"/admin/users/{self.id_de('ana@x.com')}/delete", follow_redirects=True)
        self.assertIn("foi excluída".encode(), r.data)
        inscritos = [x["email"] for x in self.query("SELECT u.email FROM registrations r JOIN users u ON u.id=r.user_id")]
        self.assertEqual(inscritos, ["bia@x.com"])
        self.assertEqual(send.call_count, 1)

    def test_usuario_inexistente_da_404(self):
        self.assertEqual(self.admin.post("/admin/users/9999/delete").status_code, 404)
        self.assertEqual(self.admin.post("/admin/users/9999/role").status_code, 404)
