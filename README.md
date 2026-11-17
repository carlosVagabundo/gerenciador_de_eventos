# EventManager

Sistema web escolar para gerenciamento de eventos, inscrições, vagas, presença e consulta de certificados.

## Tecnologias
- Python 3
- Flask
- SQLite
- HTML, CSS e JavaScript

## Como executar
1. Instale Python 3.10 ou superior.
2. Abra o terminal na pasta do projeto.
3. Crie um ambiente virtual (recomendado):
   - Windows: `python -m venv .venv` e `.venv\Scripts\activate`
   - Linux/macOS: `python3 -m venv .venv` e `source .venv/bin/activate`
4. Instale as dependências: `pip install -r requirements.txt`
5. Inicie: `python app.py`
6. Acesse `http://127.0.0.1:5000`.

## Contas fictícias para demonstração
- Administrador: `admin@eventmanager.local` / `Admin123!`
- Aluno: `aluno@eventmanager.local` / `Aluno123!`

O cadastro público cria somente contas de aluno. A conta administrativa inicial é criada automaticamente para demonstração. Troque a chave secreta e as credenciais antes de qualquer publicação real.

## Observações
- O banco SQLite `eventmanager.db` é criado automaticamente.
- Certificados aparecem na área do aluno após o administrador confirmar a presença. Nesta versão, a tela funciona como consulta interna; não gera arquivo PDF.
- Use apenas dados fictícios durante os testes escolares.