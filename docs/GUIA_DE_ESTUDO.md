# Guia de estudo do EventManager

Este guia explica **como o sistema funciona, por que cada parte existe e como estudar o código**. Foi escrito para você conseguir explicar o projeto na apresentação, responder à banca e fazer alterações com segurança.

## Sumário

1. [Resumo completo do funcionamento](#1-resumo-completo-do-funcionamento)
2. [Tecnologias e conceitos](#2-tecnologias-e-conceitos)
3. [Mapa de pastas e arquivos](#3-mapa-de-pastas-e-arquivos)
4. [Ciclo de vida de uma requisição](#4-ciclo-de-vida-de-uma-requisição)
5. [Banco de dados](#5-banco-de-dados)
6. [Módulos Python, um por um](#6-módulos-python-um-por-um)
7. [Funcionalidades passo a passo](#7-funcionalidades-passo-a-passo)
8. [Templates (HTML com Jinja2)](#8-templates-html-com-jinja2)
9. [Front-end: CSS e JavaScript](#9-front-end-css-e-javascript)
10. [Segurança](#10-segurança)
11. [Acessibilidade](#11-acessibilidade)
12. [Qualidade: testes, logs, migrações e manutenção](#12-qualidade-testes-logs-migrações-e-manutenção)
13. [Publicação e configuração](#13-publicação-e-configuração)
14. [Roteiro de estudo sugerido](#14-roteiro-de-estudo-sugerido)
15. [Perguntas que a banca pode fazer (com respostas)](#15-perguntas-que-a-banca-pode-fazer-com-respostas)
16. [Exercícios práticos](#16-exercícios-práticos)
17. [Glossário](#17-glossário)

---

## 1. Resumo completo do funcionamento

### Em uma frase

O EventManager é um site em que **administradores** cadastram eventos escolares e **alunos** se inscrevem neles; quando as vagas acabam, os alunos entram em uma **lista de espera** e são promovidos automaticamente se alguém cancelar.

### Quem usa e o que cada pessoa pode fazer

| Perfil | O que consegue fazer |
| --- | --- |
| **Visitante** (sem login) | Ver a página inicial pública com os próximos eventos, entrar, criar conta e pedir recuperação de senha. |
| **Aluno** (`role = 'student'`) | Ver e filtrar eventos, inscrever-se, cancelar inscrição, entrar/sair da lista de espera, adicionar o evento ao calendário, ver certificados, mudar nome e senha, excluir a própria conta. |
| **Administrador** (`role = 'admin'`) | Tudo o que o aluno vê da agenda, mais: criar/editar/excluir eventos (com categoria e capa), ver participantes e lista de espera, confirmar presença, exportar participantes em CSV, ver gráficos e estatísticas e **gerenciar usuários** (buscar contas, mudar o tipo de conta e excluir contas). |

### O caminho típico de uso

1. O visitante abre o site e vê a **página inicial** com os próximos eventos (sem dados pessoais).
2. Cria uma conta (**cadastro**) e entra (**login**). O servidor guarda "quem é você" em um cookie de sessão assinado.
3. No **painel**, o aluno vê suas inscrições. Em **Eventos**, usa busca, filtros e a **paginação**.
4. Clica em **Inscrever-se**. O sistema confere se há vaga, se o evento ainda não passou e se você já não está inscrito.
5. Se o evento está lotado, aparece **Entrar na lista de espera**. A posição na fila é mostrada ("Lista de espera: 2º").
6. Se alguém cancela (ou o administrador aumenta o número de vagas), o primeiro da fila vira inscrito **na mesma operação** e recebe um e-mail (se o SMTP estiver configurado).
7. O aluno usa **Calendário** para levar o evento ao Google Agenda ou baixar o arquivo `.ics`.
8. No dia, o administrador abre **Participantes** e confirma a presença. O aluno então vê o **certificado** (imprimir ou salvar como PDF).
9. Em **Minha conta**, o aluno troca nome/senha ou exclui a conta (as vagas dele são liberadas para a fila).

### O que acontece "por baixo"

- O navegador faz uma **requisição HTTP** (por exemplo, `POST /events/7/join`).
- O **Flask** encontra a função (a "rota") responsável, executa a regra de negócio, consulta o **SQLite** e devolve uma página HTML montada com **Jinja2** (ou redireciona para outra página).
- O CSS cuida da aparência (incluindo tema escuro) e o JavaScript só faz pequenos acabamentos (tema, menu no celular, caixa de confirmação, fechar avisos).

---

## 2. Tecnologias e conceitos

| Tecnologia | Papel no projeto | Por que importa |
| --- | --- | --- |
| **Python 3** | Linguagem de todo o servidor | Legível e com biblioteca padrão rica (`sqlite3`, `smtplib`, `unittest`...). |
| **Flask** | Framework web: rotas, sessões, templates | Pequeno e explícito: dá para ler e entender tudo. |
| **Werkzeug** | Base do Flask; fornece o hash de senha (`generate_password_hash`) e o servidor de desenvolvimento | Transforma senha em hash seguro (scrypt, com sal). |
| **itsdangerous** | Assina dados (token de "esqueci minha senha") | Garante que o link não foi adulterado e que expira. |
| **Jinja2** | Motor de templates (`{{ }}`, `{% %}`) | Gera HTML dinâmico e **escapa** textos automaticamente (protege contra XSS). |
| **SQLite** | Banco de dados em um único arquivo | Simples de instalar e de explicar; suficiente para o porte do projeto. |
| **gunicorn** | Servidor de produção | Roda o app no Render (`gunicorn app:app`). |
| **HTML/CSS/JS** | Interface | CSS com variáveis para os temas; JS sem bibliotecas. |
| **unittest** | Testes automáticos | Já vem com o Python. |

### Conceitos que aparecem o tempo todo

- **Rota:** associação entre um endereço (`/events`) e uma função Python.
- **Blueprint:** "módulo de rotas". Aqui há quatro: `main`, `auth`, `events`, `account`.
- **App factory (`create_app`):** função que monta e devolve o aplicativo. Permite criar um app novo para cada teste.
- **Sessão:** dados do usuário guardados em um cookie **assinado** (o usuário não consegue alterar sem a `SECRET_KEY`).
- **Transação:** conjunto de comandos SQL que valem "tudo ou nada".
- **Migração:** alteração versionada do banco (criar tabela, adicionar coluna).
- **Idempotente:** pode ser executado várias vezes com o mesmo resultado.

---

## 3. Mapa de pastas e arquivos

```
app.py                      ponto de entrada
manage.py                   comandos de manutenção
requirements.txt            dependências de produção (Flask, gunicorn)
requirements-dev.txt        dependências de desenvolvimento (pytest, opcional)
eventmanager/               o "coração" do sistema (pacote Python)
templates/                  páginas HTML
static/                     css, js e uploads
tests/                      testes automáticos
docs/                       este guia e o diagrama do banco
```

### Arquivos Python

| Arquivo | O que faz | Importância |
| --- | --- | --- |
| `app.py` | Chama `create_app()` e expõe a variável `app`. | O gunicorn (`app:app`) e o PythonAnywhere importam essa variável. Sem ela o site não sobe. |
| `eventmanager/__init__.py` | Define `create_app`: carrega configuração, liga os logs, registra filtros do Jinja, blueprints e páginas de erro, e roda as migrações. | É o "maestro". Qualquer novo recurso global (cabeçalho de segurança, filtro) entra aqui. |
| `eventmanager/config.py` | Lê as variáveis de ambiente (`SECRET_KEY`, `ADMIN_CODE`, SMTP...) e define limites (3 MB por capa, 9 eventos por página...). | Centraliza configurações: você muda um valor num lugar só. |
| `eventmanager/constants.py` | Categorias, ícones, meses abreviados, duração padrão do evento no calendário. | Evita "números mágicos" espalhados. |
| `eventmanager/db.py` | Abre conexões (`db()`), define e executa as **migrações** do banco. | Garante que o banco tem as tabelas certas e que toda conexão é fechada. |
| `eventmanager/security.py` | `current_user_row`, `login_required`, `admin_required`. | Controla quem acessa o quê. É a base da segurança de acesso. |
| `eventmanager/queries.py` | A grande consulta `EVENT_SELECT`, `fetch_events`, `count_events`, `admin_overview`. | Mantém o SQL complexo em um só lugar, usado por várias telas. |
| `eventmanager/csrf.py` | Gera o token anti-CSRF (`csrf_field`) e recusa POST sem o token certo (`protect`). | Impede que outro site faça o navegador do usuário enviar ações escondidas. |
| `eventmanager/ratelimit.py` | `too_many`, `record`, `clear`: contam tentativas no banco (tabela `rate_limits`). | Freia adivinhação de senhas e abuso do "esqueci minha senha". |
| `eventmanager/users.py` | `delete_user`: apaga a conta e oferece as vagas liberadas à lista de espera. | Regra usada em dois lugares (Minha conta e administração de usuários): evita código repetido. |
| `eventmanager/helpers.py` | `today`, `like_pattern`, `safe_back`, `paginate`, `parse_event_form`, `EMAIL_RE`. | Funções pequenas e testáveis usadas em muitas rotas. |
| `eventmanager/uploads.py` | Valida, salva e apaga imagens de capa; decide qual capa vale (`resolve_cover`). | Upload é uma das áreas mais perigosas de um site; aqui está toda a defesa. |
| `eventmanager/calendar_utils.py` | Monta o arquivo `.ics` e o link do Google Agenda. | Implementa o padrão iCalendar (RFC 5545). |
| `eventmanager/waitlist.py` | `promote_waitlist` (move a fila para inscritos) e `notify_promoted` (avisa por e-mail). | A regra de negócio mais delicada: nunca deixar vaga vazia com gente esperando. |
| `eventmanager/mailer.py` | `send_email`: envia por SMTP ou grava o texto no log. | O site não quebra se o e-mail falhar. |
| `eventmanager/blueprints/main.py` | Página inicial pública e painel (`/`, `/dashboard`). | Primeira tela do visitante e do usuário logado. |
| `eventmanager/blueprints/auth.py` | Login, logout, cadastro, "esqueci minha senha" e redefinição. | Porta de entrada do sistema. |
| `eventmanager/blueprints/events.py` | Lista, cria, edita, exclui, inscreve, cancela, fila, presença, calendário. | O maior módulo: o "negócio" do sistema. |
| `eventmanager/blueprints/admin.py` | Lista usuários (busca, filtro, paginação), muda o tipo de conta e exclui contas. | Dá ao administrador controle sobre as contas sem precisar do terminal. |
| `eventmanager/blueprints/account.py` | Minha conta (nome, senha, exclusão) e certificados. | Autonomia do usuário sobre seus dados. |
| `manage.py` | Comandos de terminal: criar admin, redefinir senha, remover contas fictícias, listar usuários e fazer **backup** do banco. | Recuperar o acesso sem depender do site. |

### Templates e arquivos estáticos

| Arquivo | O que faz |
| --- | --- |
| `base.html` | Estrutura comum: `<head>`, tema, link "pular para o conteúdo", cabeçalho, avisos, rodapé, caixa de confirmação. |
| `_macros.html` | Peças reutilizáveis: capa, vagas, cartão de evento, cartão público, paginação. |
| `home.html` | Página inicial pública. |
| `login.html`, `register.html`, `forgot_password.html`, `reset_password.html` | Telas de acesso. |
| `dashboard.html` | Painel do aluno e do administrador (com gráficos). |
| `events.html`, `event_form.html`, `participants.html` | Lista (filtros e paginação), formulário (com upload) e controle de presença. |
| `account.html`, `certificates.html` | Minha conta e certificados. |
| `admin_users.html` | Administração de usuários (tabela com busca, filtro, paginação e ações). |
| `message.html` | Páginas de erro (403, 404, 413, 500). |
| `static/css/style.css` | Todo o visual (temas claro/escuro, responsivo, impressão). |
| `static/js/app.js` | Tema, menu móvel, avisos, menu do calendário e caixa de confirmação. |
| `static/uploads/` | Capas enviadas (não vão para o Git). |

---

## 4. Ciclo de vida de uma requisição

Exemplo: o aluno clica em **Inscrever-se** no evento 7.

1. **Navegador:** envia `POST /events/7/join` com o cookie de sessão.
2. **Flask (roteamento):** encontra a função `join_event` do blueprint `events`, porque a rota é `/events/<int:event_id>/join`. O `<int:event_id>` converte o "7" em número.
3. **`login_required`:** lê `session["user_id"]`, consulta o banco (`current_user_row`). Se a conta não existe mais, limpa a sessão e redireciona para o login. Se existe, guarda o usuário em `g.user`.
4. **`BEGIN IMMEDIATE`:** trava a escrita no banco para que ninguém "pegue a mesma última vaga" ao mesmo tempo.
5. **Regras:** o evento existe? Já estou inscrito? Já passou? Há vaga? Cada "não" gera uma mensagem de erro; só o caminho feliz faz `INSERT INTO registrations`.
6. **`db()` termina:** faz `commit` (ou `rollback` se deu erro) e **fecha** a conexão.
7. **`flash(...)`:** guarda a mensagem na sessão para a próxima página.
8. **`safe_back("events.index")`:** redireciona para a página de onde veio (só se for do próprio site).
9. **Navegador:** faz `GET /events`. O Flask renderiza `events.html`, o Jinja mostra a mensagem (uma vez só) e o cartão agora exibe "Inscrito".

> **Padrão POST → redirect → GET:** depois de gravar algo, nunca devolvemos HTML direto; redirecionamos. Assim, se o usuário apertar F5, o navegador não repete a inscrição.

---

## 5. Banco de dados

### Tabelas

Veja o desenho em [`diagrama_banco.svg`](diagrama_banco.svg).

**`users`**: `id`, `name`, `email` (único), `password_hash`, `role` (`admin` ou `student`, garantido por `CHECK`).

**`events`**: `id`, `title`, `description`, `event_date` (texto `AAAA-MM-DD`), `event_time` (`HH:MM`), `location`, `capacity` (`CHECK capacity > 0`), `category`, `cover_url`, `created_at`.

**`registrations`**: `id`, `user_id`, `event_id`, `registered_at`, `attended` (0 ou 1). `UNIQUE(user_id, event_id)`.

**`waitlist`**: `id`, `user_id`, `event_id`, `created_at`. `UNIQUE(user_id, event_id)`.

**`rate_limits`** (tabela técnica, sem relações): `id`, `key`, `created_at`. Cada tentativa de login errada grava `login:<e-mail>` e cada pedido de recuperação grava `reset:<e-mail>`; registros com mais de 1 dia são apagados sozinhos.

### Por que as datas são texto?

O SQLite não tem tipo "data". No formato `AAAA-MM-DD`, comparar textos dá o mesmo resultado que comparar datas (`'2026-11-05' < '2026-12-01'`). Por isso `WHERE event_date >= :today` funciona.

### Chaves, relacionamentos e `ON DELETE CASCADE`

- `user_id` e `event_id` são **chaves estrangeiras**: só aceitam valores que existem em `users` e `events`.
- `ON DELETE CASCADE`: ao excluir um usuário ou evento, o banco apaga sozinho as inscrições e a fila ligadas a ele. Para funcionar no SQLite, **cada conexão** precisa rodar `PRAGMA foreign_keys = ON` (feito em `db()`).
- `UNIQUE(user_id, event_id)`: mesmo que o código tenha um erro, o banco impede inscrição duplicada.

### Índices

`idx_registrations_event` e `idx_waitlist_event` aceleram "quantos inscritos tem o evento X?", pergunta feita em toda listagem.

### Migrações versionadas (`db.py`)

O SQLite guarda um número no próprio arquivo: `PRAGMA user_version`. A lista `MIGRATIONS` tem funções numeradas:

| Versão | O que faz |
| --- | --- |
| 1 | Cria `users`, `events`, `registrations` (`IF NOT EXISTS`). |
| 2 | Adiciona `category` e `cover_url` em `events` se ainda não existirem. |
| 3 | Cria `waitlist`. |
| 4 | Cria `rate_limits` (limite de tentativas). |

`run_migrations()` lê a versão atual e executa **só as migrações maiores que ela**. Como cada uma é idempotente, funciona em três situações: banco novo, banco da primeira versão do projeto e banco da segunda versão (já com categoria e capa). Isso é testado em `tests/test_migrations.py`.

**Para adicionar uma coluna no futuro:** escreva `_m4_...(con)` com `ALTER TABLE ... ADD COLUMN ...` (verificando antes se a coluna já existe) e acrescente `(4, "descrição", _m4_...)` à lista.

### A consulta `EVENT_SELECT` (queries.py)

Ela devolve cada evento já com informações calculadas por **subconsultas**:

| Coluna calculada | Significado |
| --- | --- |
| `enrolled` | Quantos estão inscritos. |
| `present` | Quantos tiveram presença confirmada. |
| `waiting` | Quantos estão na fila. |
| `joined` | `1` se o usuário atual está inscrito. |
| `my_attended` | Se o usuário atual teve presença confirmada. |
| `waitlist_pos` | Posição do usuário na fila (`0` se não está). É o número de pessoas da fila com `id` menor ou igual ao dele. |

`:uid` é o id do usuário atual (ou `0` para o visitante da página inicial). Uma consulta só alimenta todos os cartões, evitando rodar dezenas de consultas por página.

### Transações (`db()` e `BEGIN IMMEDIATE`)

`db()` é um *context manager*: ao sair do bloco `with`, faz `commit`; se ocorreu erro, `rollback`; e sempre `close`. Operações que "leem e depois escrevem" (inscrever, cancelar, entrar na fila, mudar vagas) começam com `BEGIN IMMEDIATE`, que bloqueia outros escritores até o fim. Sem isso, dois alunos poderiam ler "há 1 vaga" ao mesmo tempo e ambos se inscreverem.

---

## 6. Módulos Python, um por um

### `eventmanager/__init__.py`

- `configure_logging`: cria o logger `eventmanager` com saída no console e arquivo rotativo `logs/eventmanager.log` (1 MB, 3 cópias). Nos testes, só console.
- `register_template_helpers`: filtros `br_date` (`2026-11-05` → `05/11/2026`) e `month_short` (→ `NOV`); a função `google_calendar_url` disponível em qualquer template; `inject_globals` (quem está logado, categorias, `today`); e `security_headers`.
- `register_error_handlers`: páginas amigáveis para 403, 404, 413 (arquivo grande) e 500 (que também grava o erro no log).
- `create_app`: ordem importa: configuração → logs → helpers → blueprints → erros → pasta de uploads → migrações.

### `security.py`

```python
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user_row()
        if not user:
            session.clear()
            return redirect(url_for("auth.login"))
        g.user = user
        return fn(*args, **kwargs)
    return wrapper
```

É um **decorador**: uma função que "embrulha" outra. Cada requisição consulta o banco, então: conta excluída = sessão inválida, e mudança de papel vale na hora. `admin_required` usa `g.user` (por isso vem depois, na ordem `@login_required` → `@admin_required`).

### `helpers.py`

- `like_pattern("50%")` → `%50\%%`: faz `%` e `_` serem letras comuns na busca.
- `safe_back`: só redireciona para o `Referer` se o domínio for o do próprio site (evita *open redirect*).
- `paginate(total, page, per_page)`: `pages = ceil(total / per_page)`; força `page` entre 1 e `pages`; `offset = (page - 1) * per_page`; monta `numbers` mostrando a primeira, a última e duas páginas ao redor da atual, com `None` onde vai "…".
- `parse_event_form`: valida título, descrição, local, tamanhos, data (`%Y-%m-%d`), hora (`%H:%M`), vagas (1 a 100000) e categoria. Devolve `(dados, None)` ou `(None, "mensagem")`.

### `uploads.py`

- `detect_image_extension`: olha os primeiros bytes ("assinatura"): PNG `\x89PNG`, JPEG `\xff\xd8\xff`, GIF `GIF87a/GIF89a`, WEBP `RIFF....WEBP`. **Não confia no nome nem no tipo informado pelo navegador.**
- `save_cover`: lê no máximo 3 MB + 1 byte (se passar, recusa), descobre o tipo, gera nome aleatório (`secrets.token_hex(12)`) e grava em `static/uploads/`.
- `delete_cover`: só apaga se o endereço começa com `/static/uploads/` e usa `Path(...).name` (descarta `../`).
- `resolve_cover(form, files, current_url)`: decide a capa nesta ordem: **arquivo enviado > link informado > "remover" marcado > manter a atual**.

### `calendar_utils.py`

- `event_window`: início = data + hora do evento; fim = início + 2 horas (`DEFAULT_EVENT_HOURS`), pois o sistema não guarda a duração.
- `_escape`: no iCalendar, `\`, `;`, `,` e quebras de linha precisam de escape.
- `_fold`: linhas do `.ics` têm no máximo 75 bytes; as maiores continuam na linha seguinte, começando com um espaço. A função conta **bytes em UTF-8**, não caracteres (acentos ocupam 2 bytes).
- `build_ics`: monta `VCALENDAR` → `VEVENT` com `UID`, `DTSTAMP`, `DTSTART`, `DTEND`, `SUMMARY`, `DESCRIPTION`, `LOCATION`, linhas separadas por `\r\n`. As datas não têm `Z`/fuso: cada calendário interpreta no horário local de quem importa.
- `google_calendar_url`: monta a URL `calendar.google.com/calendar/render?action=TEMPLATE&...` com `urlencode`.

### `waitlist.py`

```python
def promote_waitlist(con, event_id):
    while True:
        enrolled = <conta inscritos>
        if enrolled >= capacity: break
        nxt = <primeiro da fila: ORDER BY id LIMIT 1>
        if not nxt: break
        INSERT INTO registrations ...
        DELETE FROM waitlist WHERE id = ...
```

Recebe a **conexão já aberta** e **não** faz commit: assim a promoção acontece na mesma transação que liberou a vaga. `notify_promoted` só roda **depois** do commit, porque enviar e-mail é lento e pode falhar, e isso não deve desfazer a promoção.

### `mailer.py`

`send_email` tenta SMTP (com TLS opcional e login). Sem `SMTP_HOST`, grava o e-mail inteiro no log e retorna `False`. Se o envio falhar, registra o erro e **não derruba** a página.

### Blueprints

**`main.py`**
- `index` (`/`): se há login, vai para o painel; senão mostra `home.html` com até 6 próximos eventos (usuário `0`, sem dados pessoais).
- `dashboard` (`/dashboard`): administrador recebe `admin_overview` e a ocupação; aluno recebe suas inscrições (futuras e passadas), a fila e um resumo.

**`auth.py`**
- `login`: antes de conferir a senha, pergunta ao `ratelimit` se aquele e-mail já errou demais; confere o hash com `check_password_hash`; em caso de sucesso zera o contador, faz `session.clear()` e grava só `user_id`; em caso de erro registra a tentativa.
- `logout`: agora só aceita **POST** (o botão "Sair" é um formulário), para que outro site não consiga deslogar o usuário.
- `register`: valida nome, e-mail (regex), tamanho e confirmação de senha; compara o código de administrador com `secrets.compare_digest` (comparação em tempo constante).
- `forgot_password` / `reset_password`: veja a seção 7.3.

**`events.py`**
- `index`: monta o `WHERE` dinamicamente com parâmetros nomeados (nunca concatena texto do usuário), pagina e renderiza.
- `new_event` / `edit_event`: validam, resolvem a capa, gravam. Na edição, vagas novas chamam `promote_waitlist`.
- `delete_event`: apaga o evento (e, por `CASCADE`, inscrições e fila) e depois o arquivo da capa.
- `join_event`, `leave_event`, `join_waitlist`, `leave_waitlist`: regras de vaga e fila.
- `participants`, `attendance`: lista de inscritos/fila e alternância da presença.
- `participants_csv`: exporta inscritos e fila em CSV (`;` como separador, com BOM para o Excel abrir os acentos; `_csv_safe` coloca um apóstrofo em textos que começam com `=`, `+`, `-` ou `@`).
- `calendar_file`: devolve o `.ics` com `Content-Disposition: attachment`.

**`account.py`**
- `update_profile`, `change_password` (exige a senha atual), `delete_account` (exige a senha, impede o último administrador e usa `users.delete_user`) e `certificates`.

**`admin.py`**
- `users`: lista com busca por nome/e-mail, filtro por tipo e paginação (10 por página), mostrando inscrições e fila de cada pessoa.
- `toggle_role`: alterna `admin`/`student`. Não deixa o administrador mudar **o próprio** tipo de conta.
- `remove_user`: exclui a conta (com `delete_user`, que libera as vagas para a fila). Não deixa excluir a si mesmo por ali (para isso existe Minha conta). Como o administrador que executa a ação continua existindo, o site nunca fica sem admin.

**`csrf.py`**
- `get_token`: cria (uma vez por sessão) um texto aleatório de 256 bits e guarda na sessão.
- `csrf_field()`: devolve `<input type="hidden" name="csrf_token" ...>`; vai dentro de **todo** `<form method="post">`.
- `protect()`: roda antes de cada requisição (`before_request`). Se for POST e o token enviado não for igual ao da sessão (comparado com `secrets.compare_digest`), responde 400.

**`ratelimit.py`**
- `too_many(con, chave, limite, minutos)`, `record(con, chave)` e `clear(con, chave)` sobre a tabela `rate_limits`.

---

## 7. Funcionalidades passo a passo

### 7.1 Login e sessão

1. O formulário envia e-mail e senha por `POST`.
2. O servidor busca o usuário pelo e-mail e usa `check_password_hash` (o hash guarda algoritmo, sal e custo).
3. Se confere: `session.clear()` (evita *session fixation*), `session["user_id"] = id`. O Flask coloca isso num cookie **assinado** com `SECRET_KEY`: o usuário pode ler, mas não consegue alterar sem invalidar a assinatura.
4. O cookie tem `HttpOnly` (JavaScript não lê) e `SameSite=Lax` (não é enviado em requisições vindas de outros sites).
5. A mensagem de erro é a mesma para "e-mail não existe" e "senha errada".
6. **Limite de tentativas:** depois de 5 erros seguidos (`LOGIN_MAX_ATTEMPTS`) para o mesmo e-mail, o login fica bloqueado por 10 minutos (`LOGIN_LOCK_MINUTES`) e responde 429, **mesmo que a senha esteja certa**. Vale também para e-mails que não existem, para não revelar quem tem conta. Um login bem-sucedido zera o contador.

### 7.2 Cadastro e administrador

- Todo cadastro vira `student`, **exceto** se informar o `ADMIN_CODE` correto.
- Se `ADMIN_CODE` não está definido, o campo nem aparece e nenhum código funciona.
- O primeiro administrador também pode ser criado por `python manage.py create-admin`.

### 7.3 Esqueci minha senha

1. O usuário informa o e-mail em `/forgot-password`.
2. Se a conta existe, `make_reset_token` gera um token assinado com `{uid, fp}`, onde `fp` é uma "impressão digital" (SHA-256) do hash da senha atual.
3. O link `/reset-password/<token>` é enviado por e-mail (ou gravado no log, se não houver SMTP).
4. A resposta na tela é **sempre a mesma**, exista ou não a conta, para não revelar quem está cadastrado.
5. Ao abrir o link, `user_from_reset_token` verifica: assinatura válida? Menos de 1 hora (`RESET_TOKEN_MAX_AGE`)? A impressão digital ainda bate com a senha atual?
6. Depois que a senha muda, a impressão digital muda, então **o mesmo link não funciona uma segunda vez**.
7. Para ninguém "bombardear" a caixa de entrada de outra pessoa, só os 3 primeiros pedidos por hora para o mesmo e-mail geram mensagem; a tela responde igual em qualquer caso.

> **Se você não configurar SMTP:** o link aparece no log do servidor (no PythonAnywhere, em *Error log*; no Render, em *Logs*). Útil para testes, mas trate esses logs como sensíveis.

### 7.4 Página inicial pública

`/` mostra, para quem não está logado, a apresentação, até 6 próximos eventos (`public_event_card`, sem botões de ação) e os recursos do sistema. Quem já está logado é redirecionado ao painel.

### 7.5 Painel

- **Administrador:** `admin_overview` calcula totais (eventos, inscrições, alunos, taxa de presença, fila), eventos por categoria e inscrições dos últimos 7 dias (`GROUP BY substr(registered_at, 1, 10)`), preenchendo com zero os dias sem inscrição. Os gráficos são feitos só com HTML e CSS (larguras e alturas em `%`).
- **Aluno:** separa inscrições futuras, passadas (mais recentes primeiro) e fila.

### 7.6 Listagem, filtros e paginação

1. Os filtros chegam por `GET` (`?q=...&category=...&period=...&page=2`).
2. O código monta uma lista de condições e um dicionário de parâmetros (`:q`, `:category`, `:today`). Valores inválidos de categoria/período são ignorados.
3. `count_events` conta o total; `paginate` calcula páginas e `offset`; `fetch_events` aplica `LIMIT :limit OFFSET :offset`.
4. A macro `pagination` gera os links preservando os filtros (`**filters`).
5. Pedir `?page=99` mostra a última página; `?page=abc` mostra a primeira.

### 7.7 Cadastro e edição de evento

1. `parse_event_form` valida os campos de texto.
2. `resolve_cover` decide a capa (arquivo, link, remover ou manter).
3. Na edição, `BEGIN IMMEDIATE` + conferência: o novo limite de vagas **não pode ser menor que o número de inscritos**.
4. Se algo falha, o formulário volta preenchido com o que foi digitado (`values=request.form`) e o upload que não foi usado é apagado.
5. Se a capa mudou, a antiga é apagada do disco.

### 7.8 Upload de capa

Defesas em camadas: limite do corpo da requisição (5 MB, resposta 413) → limite da imagem (3 MB) → tipo detectado pelo conteúdo → nome aleatório → extensão escolhida pelo servidor (SVG não é aceito, pois pode carregar scripts) → apagar arquivos órfãos → cabeçalho `nosniff`.

### 7.9 Inscrição, cancelamento e vagas

- **Inscrever:** exige evento existente, não encerrado, sem inscrição prévia e com vaga. Também remove o usuário da fila, se ele estava lá.
- **Cancelar:** só se há inscrição, a presença ainda não foi confirmada e o evento não passou. A vaga liberada é oferecida ao primeiro da fila **na mesma transação**.

### 7.10 Lista de espera

- **Entrar na fila:** só se o evento está lotado, não encerrado, e o usuário nem está inscrito nem já está na fila. A mensagem informa a posição.
- **Promoção automática** acontece em três situações: cancelamento, aumento de vagas pelo administrador e exclusão de conta de alguém inscrito.
- **Ordem:** quem entrou primeiro tem o menor `id` em `waitlist`.

### 7.11 Calendário

Dois caminhos a partir do menu "Calendário" (`<details>`/`<summary>`, que já é acessível por padrão):
- **Google Agenda:** link para `calendar.google.com/calendar/render?...` que abre o evento pré-preenchido.
- **Arquivo `.ics`:** funciona em Apple Calendar, Outlook e também importa no Google.

### 7.12 Minha conta

- Mudar nome: valida de 2 a 100 caracteres.
- Mudar senha: exige a senha atual, 6 a 128 caracteres e confirmação.
- Excluir conta: exige a senha; **bloqueia o último administrador**; apaga o usuário (inscrições e fila saem por `CASCADE`); promove as filas dos eventos que ele ocupava; limpa a sessão.

### 7.13 Presença e certificados

O administrador alterna `attended` (0/1) em cada inscrição. O certificado do aluno lista as inscrições com `attended = 1` e usa `window.print()` (o CSS de impressão esconde o resto da página).

### 7.14 Gerenciar usuários (administrador)

1. Menu **Usuários** → `/admin/users`: tabela com nome, e-mail, tipo, inscrições (e posição em fila) de cada pessoa.
2. Busca por nome/e-mail (`LIKE` com `%` e `_` neutralizados), filtro por tipo e paginação de 10 em 10.
3. **Tornar administrador / Tornar aluno** e **Excluir** abrem a caixa de confirmação do site.
4. Proteções: não dá para mudar ou excluir **a própria conta** nessa tela; as vagas de quem é excluído vão para a lista de espera; toda ação é registrada no log com o id de quem a fez.
5. É por aqui (ou por `manage.py remove-demo`) que se remove a conta fictícia antiga, depois de criar o seu administrador.

### 7.15 Exportar participantes em CSV

Na página de participantes, **Baixar CSV** gera `participantes-evento-<id>.csv` com nome, e-mail, situação (inscrito ou posição na fila), presença e data de registro. Detalhes que importam: separador `;` e BOM no início (o Excel brasileiro abre certo), e proteção contra **injeção de fórmula** (um nome como `=HYPERLINK(...)` viraria uma fórmula executável na planilha; o apóstrofo à frente impede).

### 7.16 Backup do banco

`python manage.py backup` usa a API de backup do SQLite (`source.backup(target)`), que gera uma cópia **consistente** mesmo com o site em uso. As cópias vão para `backups/` (fora do Git) e só as 10 mais recentes ficam. As capas enviadas (`static/uploads/`) não entram: copie essa pasta à parte. No PythonAnywhere, baixe os arquivos pela aba **Files**.

---

## 8. Templates (HTML com Jinja2)

### Herança

`base.html` define blocos (`{% block content %}`, `anon_header`, `main_class`, `title`). Cada página faz `{% extends "base.html" %}` e preenche só o que muda. A `home.html` sobrescreve `anon_header` para mostrar o cabeçalho público.

### Macros (`_macros.html`)

Como funções de template: `cover(e)`, `capacity(e)`, `event_card(e)`, `public_event_card(e)`, `pagination(pager, filters)`. Importadas com `{% from "_macros.html" import event_card with context %}` (o `with context` permite usar `today`, `current_role` etc.).

### A lógica do cartão de evento

`event_card` decide qual botão mostrar:

| Situação | O que aparece |
| --- | --- |
| Administrador | Editar, Participantes, Excluir (com confirmação) |
| Inscrito, presença confirmada | "✓ Presença confirmada" |
| Inscrito, evento passou | "Evento encerrado" |
| Inscrito, evento futuro | "Inscrito" + Calendário + Cancelar inscrição |
| Na fila | "Lista de espera: Nº" + Sair da lista |
| Não inscrito, evento passou | Botão desativado "Evento encerrado" |
| Não inscrito, lotado | "Entrar na lista de espera" |
| Não inscrito, com vaga | "Inscrever-se" |

### Escape automático

`{{ e.title }}` converte `<` em `&lt;`. Se alguém cadastrar um título com `<script>`, ele aparece como texto e não executa. Está testado em `test_events.py`.

### Filtros próprios

`{{ data|br_date }}` e `{{ data|month_short }}` (definidos em `__init__.py`).

---

## 9. Front-end: CSS e JavaScript

### CSS

- **Variáveis** (`--bg`, `--surface`, `--ink`, `--primary`...) em `:root`. O tema escuro redefine essas variáveis em `:root[data-theme="dark"]`. Trocar de tema é só trocar o atributo `data-theme` no `<html>`.
- Um pequeno script no `<head>` aplica o tema salvo **antes** da página aparecer (evita o "piscar" branco).
- **Responsivo:** `grid` com `repeat(auto-fill, minmax(300px, 1fr))` para os cartões; `@media (max-width: 760px)` troca o menu por um botão ☰.
- **Animações** (`rise`, `grow`, `pop`...) são desligadas para quem pediu "reduzir movimento" (`prefers-reduced-motion`).
- **Impressão:** `@media print` esconde menus e botões para o certificado sair limpo.

### JavaScript (`app.js`)

| Trecho | O que faz |
| --- | --- |
| Tema | Alterna `data-theme`, salva em `localStorage` e atualiza `aria-pressed`/`aria-label`. |
| Menu móvel | Abre/fecha o menu e atualiza `aria-expanded`. |
| Avisos | Somem sozinhos após alguns segundos. |
| Menu "Calendário" | Fecha ao clicar fora ou apertar Esc. |
| Envio duplo | Depois do primeiro envio de um formulário, desativa seus botões (evita inscrição ou exclusão repetida por clique duplo em conexão lenta). Não age quando a caixa de confirmação cancelou o envio. |
| Caixa de confirmação | Intercepta o `submit` de formulários com `data-confirm-title`, abre o modal e só envia o formulário se a pessoa confirmar. O foco começa em "Cancelar", fica preso dentro da caixa e volta ao botão original ao fechar. |

Se o JavaScript falhar, o site continua usável (só as confirmações deixam de aparecer).

---

## 10. Segurança

| Ameaça | Como o projeto se defende | Onde |
| --- | --- | --- |
| **Senha vazada** | Só o hash (scrypt, com sal) é guardado. | `auth.py`, `account.py` |
| **SQL injection** | Todas as consultas usam parâmetros (`?`, `:nome`); o texto do usuário nunca é concatenado. A busca ainda neutraliza `%` e `_`. | `queries.py`, `events.py`, `helpers.py` |
| **XSS** (script injetado em textos) | O Jinja escapa tudo automaticamente. | Templates |
| **CSRF** (site malicioso fazendo você enviar um formulário) | Duas camadas: cookie `SameSite=Lax` **e** token secreto em todo formulário POST (`csrf_field` + `protect`). O logout só funciona por POST. | `csrf.py`, `config.py` |
| **Força bruta de senha** | Máximo de 5 erros por e-mail em 10 minutos (tabela `rate_limits`), com resposta 429. | `ratelimit.py`, `auth.py` |
| **Abuso do "esqueci minha senha"** | Só 3 pedidos por hora por e-mail. | `auth.py` |
| **Injeção de fórmula em planilha** | O CSV põe um apóstrofo em textos que começam com `=`, `+`, `-`, `@`. | `events.py` |
| **Cookie interceptado em rede aberta** | `SECURE_COOKIES=1` marca o cookie como `Secure` (só viaja por HTTPS). | `config.py` |
| **Sessão roubada/forjada** | Cookie assinado, `HttpOnly`, renovado no login, validado no banco a cada requisição. | `security.py`, `auth.py` |
| **Acesso indevido** | `login_required` e `admin_required` em cada rota; o papel é lido do banco, não do cookie. | `security.py` |
| **Enumeração de usuários** | Mesma mensagem para e-mail existente ou não (login e recuperação de senha). | `auth.py` |
| **Link de recuperação reutilizado** | Assinado, expira em 1 hora e invalida ao trocar a senha. | `auth.py` |
| **Upload malicioso** | Tipo pelo conteúdo, nome aleatório, limite de tamanho, sem SVG, `nosniff`. | `uploads.py`, `__init__.py` |
| **Redirecionamento aberto** | `safe_back` só aceita o próprio domínio. | `helpers.py` |
| **Corrida por vagas** | `BEGIN IMMEDIATE` nas operações de inscrição. | `events.py` |
| **Ficar sem administrador** | O último admin não pode se excluir. | `account.py` |
| **Contas com senha pública** | Contas fictícias foram removidas do código; `manage.py remove-demo` limpa as antigas. | `manage.py` |

**O que ainda não existe** (diga com honestidade na banca): verificação de e-mail no cadastro e autenticação em dois fatores. O bloqueio de login é por e-mail (não por IP), então alguém mal-intencionado pode travar a conta de outra pessoa por 10 minutos: é um trade-off assumido, porque em hospedagens com proxy o IP visto pelo servidor costuma ser o mesmo para todos.

---

## 11. Acessibilidade

Baseada nas diretrizes **WCAG 2.2, nível AA**:

| Prática | Como foi aplicada |
| --- | --- |
| Navegação por teclado | Tudo é link ou botão nativo; foco sempre visível (`:focus-visible`); o modal prende o foco e fecha com Esc. |
| Pular repetições | Link "Pular para o conteúdo" no início da página. |
| Estrutura | `lang="pt-br"`, um `<h1>` por página, regiões (`<header>`, `<nav aria-label>`, `<main>`, `<footer>`). |
| Rótulos | Todo campo tem `<label>`; nos filtros, rótulos só para leitores de tela (`.sr-only`). |
| Estado atual | `aria-current="page"` no menu e na paginação; `aria-pressed` no botão de tema; `aria-expanded` no menu móvel. |
| Avisos | `role="alert"` (erros) e `role="status"` (sucessos) são lidos automaticamente. |
| Gráficos e barras | Barras de vaga usam `role="progressbar"` com valores; os gráficos têm texto equivalente invisível. |
| Imagens e ícones | Capas têm `alt`; emojis decorativos têm `aria-hidden`. Botões repetidos ("Inscrever-se") ganham o nome do evento em texto invisível. |
| Contraste | Todas as cores de texto têm razão de pelo menos 4,5:1 nos dois temas (conferido por cálculo). Bordas de campos têm pelo menos 3:1. |
| Movimento | Animações desligadas com `prefers-reduced-motion`. |
| Alvos de toque | Botões com pelo menos 36–40 px de altura. |
| Tabelas | `<caption>` e `scope="col"`. |

Os testes de `tests/test_pages.py` (classe `AccessibilityTests`) conferem automaticamente: `lang`, link de pular, um único `<h1>`, `alt` nas imagens, `progressbar`, `aria-current`, rótulos e `role="alert"`.

> Nenhuma ferramenta automática substitui testar de verdade: navegue pelo site só com o teclado (Tab, Enter, Esc) e, se puder, com um leitor de tela (NVDA, VoiceOver).

---

## 12. Qualidade: testes, logs, migrações e manutenção

### Testes (`tests/`)

Rodar: `python -m unittest discover -s tests -t . -v` (66 testes, cerca de 30 segundos; a maior parte do tempo é o cálculo do hash das senhas).

| Arquivo | O que cobre |
| --- | --- |
| `base.py` | Cria um app com banco temporário e funções de apoio (`new_user`, `create_event`...). |
| `test_auth.py` | Cadastro, login, código de admin, página inicial, "esqueci minha senha" (fluxo, uso único, expiração, link adulterado) e **limite de tentativas** (bloqueio, expiração, e-mail inexistente, pedidos de recuperação). |
| `test_security.py` | **CSRF** (sem token, token errado, token de outra sessão, logout só por POST) uma varredura que garante que **nenhum** formulário POST do site fica sem token e um **fluxo de ponta a ponta com o CSRF ligado** (cadastro, login, evento com upload, fila, administração, conta e logout, como um navegador faria). |
| `test_admin.py` | Gerenciar usuários: permissões, busca, filtro, paginação, mudar tipo de conta, não alterar a si mesmo, excluir libera vaga para a fila. |
| `test_events.py` | Permissões, validações, XSS, filtros, paginação, edição, upload (válido, falso, grande, trocar/remover/excluir) e exportação CSV (inclusive proteção de fórmula). |
| `test_registrations.py` | Inscrição, cancelamento, fila (ordem, promoção, aumento de vagas, exclusão de conta), eventos encerrados, `safe_back`. |
| `test_account.py` | Nome, senha, exclusão, último administrador. |
| `test_calendar.py` | Conteúdo do `.ics` (escape, dobra de linhas, horários) e link do Google. |
| `test_migrations.py` | Subir um banco antigo sem perder dados; rodar migrações duas vezes. |
| `test_manage.py` | `remove-demo`, `create-admin`, `reset-password` e `backup` (cópia válida e limpeza das antigas). |
| `test_pages.py` | Página inicial pública, painéis, erros 403/404/413 e acessibilidade. |

Cada teste usa `setUp` para criar um banco **novo e isolado**, então um teste nunca interfere em outro. `unittest.mock.patch` substitui `send_email` para capturar o link de recuperação e verificar o envio da promoção da fila.

### Logs

`logs/eventmanager.log` (rotativo) registra logins, bloqueios por excesso de tentativas, ações de administrador sobre contas, contas criadas, eventos criados/excluídos, redefinições de senha, migrações aplicadas, falhas de e-mail e erros 500 com o rastro completo. **Nunca** se grava senha. O log serve para descobrir problemas sem depender do print de um usuário.

### Migrações

Veja a seção 5. Regra de ouro: **nunca edite uma migração antiga**; crie uma nova.

### `manage.py`

Recupera o acesso quando o site não ajuda: criar administrador, redefinir senha, remover contas fictícias (recusa se isso deixaria o site sem admin) e listar usuários.

### Organização do código

Cada módulo tem **uma responsabilidade** (consultas, uploads, calendário, fila...). Rotas ficam finas: validam, chamam funções e renderizam. Isso facilita testar e explicar.

---

## 13. Publicação e configuração

### Variáveis de ambiente

| Variável | Obrigatória? | Função |
| --- | --- | --- |
| `SECRET_KEY` | **Sim** em produção | Assina sessões e links de recuperação. Se mudar, todo mundo é deslogado e links antigos deixam de valer. |
| `ADMIN_CODE` | Não | Habilita o campo de código de administrador no cadastro. |
| `SECURE_COOKIES` | Recomendada em produção | `1` marca o cookie de sessão como `Secure` (só HTTPS). Não use ao testar em `http://127.0.0.1`. |
| `LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCK_MINUTES` | Não | Limite e tempo de bloqueio do login (padrão 5 e 10). |
| `DATABASE_PATH` | Não | Local do arquivo do banco. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `SMTP_TLS` | Não | Envio de e-mails. |
| `LOG_DIR`, `LOG_LEVEL` | Não | Onde e quanto registrar nos logs. |

### PythonAnywhere

- Código: `git pull` num console Bash dentro da pasta do projeto, depois **Reload** na aba Web.
- O arquivo WSGI define as variáveis **antes** de importar o app:

```python
import sys, os
path = '/home/SEUUSUARIO/gerenciador_de_eventos'
if path not in sys.path:
    sys.path.insert(0, path)
os.environ['SECRET_KEY'] = 'texto-longo-e-aleatorio'
os.environ['ADMIN_CODE'] = 'seu-codigo-de-administrador'
os.environ['SECURE_COOKIES'] = '1'      # o site está em HTTPS
from app import app as application
```

- O banco e os uploads ficam no disco e **persistem**.
- E-mail: contas gratuitas só conseguem SMTP com o Gmail (`smtp.gmail.com`, porta 587, TLS), usando uma **senha de app** da conta Google. Se o envio falhar, o link continua aparecendo no log.

### Render

- Build: `pip install -r requirements.txt`; Start: `python -m gunicorn app:app --bind 0.0.0.0:$PORT`.
- O disco gratuito é **temporário**: banco e uploads somem a cada reinício.

---

## 14. Roteiro de estudo sugerido

Leia nesta ordem, abrindo cada arquivo ao lado do guia:

1. `app.py` → `eventmanager/__init__.py` (como o app é montado).
2. `config.py` e `constants.py` (o que é configurável).
3. `db.py` (conexão e migrações) e o diagrama do banco.
4. `security.py` (quem pode o quê).
5. `blueprints/auth.py` (login e cadastro) e `templates/login.html`.
6. `queries.py` (`EVENT_SELECT`) e `helpers.py` (paginação).
7. `blueprints/events.py`, **rota por rota**: `index` → `join_event` → `leave_event` → `join_waitlist`.
8. `waitlist.py` e `uploads.py`.
9. `templates/base.html`, `_macros.html` e `events.html`.
10. `static/css/style.css` (variáveis e responsivo) e `static/js/app.js`.
11. `tests/base.py` e depois `test_registrations.py` (os testes são uma "documentação executável" das regras).

**Dica:** para cada rota, escreva em uma frase "quem pode usar, o que valida, o que grava e para onde redireciona".

---

## 15. Perguntas que a banca pode fazer (com respostas)

**1. Por que Flask e não Django?**
Porque o projeto é pequeno e quisemos código explícito: cada rota, validação e consulta é visível. Django traz mais estrutura pronta (admin, ORM, autenticação) do que o projeto precisava.

**2. Por que SQLite?**
É um arquivo único, sem instalação, e atende o porte do projeto. Para muitos usuários simultâneos trocaríamos por PostgreSQL; como usamos SQL padrão, a mudança seria pequena.

**3. Como as senhas são protegidas?**
Guardamos apenas o hash (scrypt, com sal), nunca a senha. Na entrada, o hash da senha digitada é comparado ao armazenado.

**4. O que impede SQL injection?**
Todas as consultas usam parâmetros (`?` ou `:nome`). O texto do usuário é enviado separado do comando SQL, então nunca é interpretado como código.

**5. E XSS?**
O Jinja2 escapa automaticamente tudo que vem do usuário. Há um teste que cadastra `<b>X</b>` como título e confirma que aparece escapado.

**6. Como a lista de espera funciona?**
Há uma tabela `waitlist`. Quando a vaga abre (cancelamento, aumento de vagas ou exclusão de conta), a função `promote_waitlist` move o primeiro da fila para `registrations` **na mesma transação**, então nunca sobra vaga livre com gente esperando.

**7. O que acontece se duas pessoas pegam a última vaga ao mesmo tempo?**
`BEGIN IMMEDIATE` trava a escrita durante "contar vagas e inserir". A segunda pessoa espera, vê que lotou e recebe a mensagem de vagas esgotadas.

**8. Como funciona o "esqueci minha senha"?**
Geramos um token assinado com a data e uma impressão digital da senha atual. Ele expira em 1 hora e deixa de valer assim que a senha muda. Sempre mostramos a mesma mensagem, exista ou não o e-mail.

**9. Como o upload de imagem é protegido?**
Verificamos o tipo real pelos primeiros bytes, limitamos o tamanho, sorteamos o nome do arquivo, recusamos SVG e apagamos arquivos que ficam sem uso.

**10. Como o banco é atualizado sem perder dados?**
Com migrações numeradas. O número da versão fica no próprio arquivo do banco (`PRAGMA user_version`) e cada migração só roda se for maior que a versão atual.

**11. Por que usar blueprints e `create_app`?**
Para separar responsabilidades e permitir um app isolado em cada teste, com banco temporário.

**12. Como vocês testaram?**
66 testes automáticos com `unittest`: regras de negócio, permissões, migração de banco antigo e acessibilidade básica.

**13. O sistema é acessível?**
Seguimos práticas do WCAG AA: teclado, rótulos, contraste conferido, leitores de tela, tema escuro e respeito a "reduzir movimento". Há testes automáticos para o básico, mas o ideal é validar também com usuários reais.

**14. Quais as limitações?**
Não há verificação de e-mail nem autenticação em dois fatores. O bloqueio de login é por e-mail e não por IP (trade-off explicado no guia). No Render gratuito, o disco é temporário. O envio de e-mail depende do SMTP da hospedagem.

**14b. Como vocês protegem contra CSRF?**
Todo formulário POST leva um token aleatório guardado na sessão, e uma função que roda antes de cada requisição recusa o POST se o token não bater. Além disso, o cookie usa `SameSite=Lax` e o logout só funciona por POST. Há um teste que varre todas as páginas e garante que nenhum formulário ficou sem token.

**14c. E contra tentativas de adivinhar senha?**
Depois de 5 erros para o mesmo e-mail em 10 minutos, o login é bloqueado (resposta 429), mesmo com a senha certa. A contagem fica no banco, então vale para todos os processos do servidor, e o bloqueio também vale para e-mails inexistentes, para não revelar quem tem conta.

**15. Como o sistema escalaria?**
Trocar o SQLite por PostgreSQL, guardar uploads em um serviço de armazenamento (S3), rodar vários processos do gunicorn e adicionar cache e fila de e-mails.

---

## 16. Exercícios práticos

1. **Nova categoria:** adicione "Música" em `constants.py` e um gradiente `.cat-musica` no CSS. Rode os testes.
2. **Mudar a duração no calendário:** altere `DEFAULT_EVENT_HOURS` e veja o `.ics`. Depois adicione um campo "duração" ao evento (nova migração `_m4`, formulário, `event_window`).
3. **Itens por página:** mude `EVENTS_PER_PAGE` para 6 e observe a paginação.
4. **Exportar CSV:** crie a rota `/events/<id>/participants.csv` (use o módulo `csv` e `Response`).
5. **Limite por IP:** além do limite por e-mail, bloqueie um IP que erre 20 logins em 10 minutos. Pense: por que `request.remote_addr` pode ser o mesmo para todos numa hospedagem com proxy? (dica: `ProxyFix`).
6. **Verificação de e-mail:** gere um token assinado no cadastro e só deixe logar depois de abrir o link (reaproveite a ideia de `make_reset_token`).
7. **Novo gráfico:** adicione "presenças por evento" ao painel (consulta em `admin_overview` + HTML/CSS).
8. **Confirmação por e-mail:** envie um e-mail de boas-vindas no cadastro usando `send_email`.
9. **Explorar o banco:** abra `eventmanager.db` (extensão *SQLite Viewer* do VS Code) e escreva as consultas: eventos mais lotados, alunos com mais presenças, eventos sem inscritos.
10. **Quebrar de propósito:** remova `PRAGMA foreign_keys = ON` e rode os testes. Qual falha? Por quê?

---

## 17. Glossário

| Termo | Significado |
| --- | --- |
| **Blueprint** | Grupo de rotas do Flask que pode ser registrado no app. |
| **Cascade** | Regra do banco: ao apagar o "pai", apaga os "filhos". |
| **CSRF** | Ataque em que outro site faz seu navegador enviar uma ação a um site em que você está logado. |
| **Token CSRF** | Texto aleatório secreto que acompanha cada formulário; sem ele o servidor recusa o envio. |
| **Rate limit** | Limite de quantas vezes uma ação pode ser tentada em certo tempo (ex.: 5 logins errados em 10 minutos). |
| **BOM** | Marca no início de um arquivo de texto que avisa ao Excel que ele está em UTF-8 (acentos corretos). |
| **Decorador** | Função que modifica outra (`@login_required`). |
| **Hash** | Resumo irreversível de um texto; usado para guardar senhas. |
| **Idempotente** | Que pode ser repetido sem mudar o resultado. |
| **Jinja2** | Motor de templates do Flask. |
| **Migração** | Alteração versionada na estrutura do banco. |
| **ORM** | Biblioteca que mapeia tabelas para objetos (não usada aqui). |
| **Paginação** | Dividir uma lista longa em páginas. |
| **Parâmetro (SQL)** | Valor enviado separado do comando, evitando injeção. |
| **Rota** | Endereço do site ligado a uma função. |
| **Sal (salt)** | Texto aleatório misturado à senha antes do hash. |
| **Sessão** | Informações de um usuário mantidas entre requisições (cookie assinado). |
| **Transação** | Grupo de comandos SQL com efeito "tudo ou nada". |
| **WCAG** | Diretrizes internacionais de acessibilidade web. |
| **WSGI** | Padrão de comunicação entre o servidor web e aplicações Python. |
| **XSS** | Ataque que injeta scripts em páginas por meio de texto. |
