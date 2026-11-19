# EventManager

Sistema web para gerenciar eventos escolares, feito com Flask e SQLite.

## Funcionalidades

- Login, cadastro e contas de **aluno** e **administrador** (o administrador é criado com um código secreto)
- Eventos com **categorias**, imagem de capa opcional, data, horário, local e limite de vagas
- Busca e filtros por texto, categoria e período (próximos / passados)
- Inscrição e **cancelamento de inscrição**, com controle de vagas
- Controle de presença e certificados para imprimir ou salvar em PDF
- Painel do administrador com **gráficos e estatísticas**
- Página **Minha conta**: alterar nome, alterar senha e excluir a conta
- **Tema claro e escuro** e layout adaptado para celular

## Como rodar localmente

```bash
pip install -r requirements.txt
python app.py
```

Abra http://127.0.0.1:5000. O banco `eventmanager.db` é criado automaticamente.

## Variáveis de ambiente

| Variável | Para que serve |
| --- | --- |
| `SECRET_KEY` | Chave secreta das sessões (use um texto longo e aleatório em produção) |
| `ADMIN_CODE` | Código para criar contas de administrador no cadastro. Sem ele, o campo não aparece |
| `DEMO_ACCOUNTS` | Use `0` para não criar as contas fictícias de demonstração |

## Publicação

Comandos usados no Render: **Build** `pip install -r requirements.txt` e **Start** `python -m gunicorn app:app --bind 0.0.0.0:$PORT`.

## Contas de demonstração (se `DEMO_ACCOUNTS` não for `0`)

- Admin: `admin@eventmanager.local` / `Admin123!`
- Aluno: `aluno@eventmanager.local` / `Aluno123!`