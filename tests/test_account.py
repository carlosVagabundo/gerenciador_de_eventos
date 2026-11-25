from .base import AppTestCase


class AccountTests(AppTestCase):
    def test_nome_e_senha(self):
        ana = self.new_user("Ana", "ana@x.com")
        self.assertIn("2 a 100".encode(), ana.post("/account/profile", data={"name": "A"}, follow_redirects=True).data)
        self.assertIn("Nome atualizado".encode(), ana.post("/account/profile", data={"name": "Ana Maria"},
                                                         follow_redirects=True).data)
        self.assertIn("incorreta".encode(), ana.post("/account/password", data={
            "current_password": "x", "new_password": "nova123", "confirm_password": "nova123"}, follow_redirects=True).data)
        self.assertIn("alterada com sucesso".encode(), ana.post("/account/password", data={
            "current_password": "abc123", "new_password": "nova123", "confirm_password": "nova123"},
            follow_redirects=True).data)
        self.assertEqual(self.login(self.app.test_client(), "ana@x.com", "nova123").status_code, 302)

    def test_excluir_conta(self):
        ana = self.new_user("Ana", "ana@x.com")
        self.assertIn("não foi excluída".encode(), ana.post("/account/delete", data={"password": "x"},
                                                           follow_redirects=True).data)
        self.assertIn("conta foi excluída".encode(), ana.post("/account/delete", data={"password": "abc123"},
                                                             follow_redirects=True).data)
        self.assertEqual(ana.get("/dashboard").status_code, 302)

    def test_ultimo_administrador_nao_se_exclui(self):
        chefe = self.new_user("Chefe", "chefe@x.com", admin=True)
        self.assertIn("único administrador".encode(), chefe.post("/account/delete", data={"password": "abc123"},
                                                                follow_redirects=True).data)
        self.new_user("Outro", "outro@x.com", admin=True)
        self.assertIn("conta foi excluída".encode(), chefe.post("/account/delete", data={"password": "abc123"},
                                                               follow_redirects=True).data)
