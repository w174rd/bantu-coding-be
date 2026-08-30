# Bantu Coding — Backend

Backend for **Bantu Coding**, a collaborative coding-assistant app where a user debates a problem with
four AI personas in a shared Slack-style room, the personas turn the debate into backlog tickets, and
dragging a ticket into **In Progress** hands it to Claude Code for execution against a real repository.

The frontend lives in a separate repo, `bantu-coding-fe`.

---

## 1. Specification

### Product flow

| # | Stage | State |
|---|---|---|
| 0 | **Create a project** — the user names a project; nothing else exists outside one | Built |
| 1 | **Multi-persona chat** — the user and four AI personas talk in one shared room | Built |
| 2 | **Backlog tickets** — the Arbiter turns the discussion into one or more tickets | Built |
| 3 | **Drag to In Progress** — only the user may move a ticket *into* In Progress | Board API built |
| 4 | **Automatic execution** — the move triggers Claude Code via the Claude Agent SDK | Not built |
| 5 | **Auto commit & push** — the run's work is committed and a PR is opened on the target repo | Not built |

Step 3 is the product's primary control gate: it is the only thing between an AI-written ticket and an
AI-executed change on a real repo. Nothing in the codebase may move a ticket into In Progress on the
user's behalf.

### Core concepts

| Term | Meaning |
|---|---|
| **Project** | The container everything belongs to, and where the target repo is recorded. |
| **Persona** | One AI personality the user can talk to. |
| **Conversation** / **Message** | A chat thread and its entries. |
| **Ticket** | A backlog item created out of a conversation. The unit of work. |
| **Agent run** | One Claude Agent SDK execution against a ticket. *(not implemented yet)* |
| **Target repo** | The external GitHub repo an agent run reads and pushes to — never this repo. |

### Projects

A project is created before anything else: it is what the user names first, and every conversation and
every ticket carries a **non-null** `project_id`. That is enforced by the database, not by convention, and
deleting a project cascades to its rooms and its board.

| Column | Notes |
|---|---|
| `name` | Required, **unique** — two identically named projects are indistinguishable on a board. Creating a duplicate returns `409`. |
| `description` | Optional. |
| `repo_url` | The target repo. Optional at creation; validated as an **`https://` URL**. |
| `default_branch` | The **PR base**, never a push target — a run pushes to its own branch (§7, control 3). |

`repo_url` being pinned to `https` at the schema is not cosmetic: security §6.4 requires a run's target to
come from a typed column, and a column that also accepts `file://` or `ssh://` is not that guarantee.

There is no GitHub credential column yet. Where the agent runner's per-repo credential lives is decided
with the code that uses it — see *Not decided yet*.

### The board

`Backlog → In Progress → In Review → Done`, defined once as `TicketStatus` in `app/core/enums.py` and
shared by the model and the schemas. The database column is a **native Postgres enum**, so adding a
column is a migration, not a config tweak.

**In Review** is where a ticket waits while the agent's pull request is open — runs open PRs, they never
push to a default branch. A successful run auto-advances a ticket from In Progress to In Review; that is
not a violation of the drag gate, which guards *entry* into In Progress only.

### The discussion room

One shared channel, four fixed characters plus the human. The cast is not user-configurable — `PersonaRole`
is a native Postgres enum, so a fifth character would be a migration.

| Role | Name | Avatar | Accent | What they do |
|---|---|---|---|---|
| `ARCHITECT` | Architect | 🏗️ | `#6366f1` | Proposes the solution |
| `RESEARCHER` | Researcher | 📚 | `#14b8a6` | Supplies facts, constraints, prior art |
| `CHALLENGER` | Challenger | 🧨 | `#f43f5e` | Antithesis — attacks the proposal |
| `ARBITER` | Arbiter | ⚖️ | `#f59e0b` | Scores the options and writes the ticket(s) |

Each persona may run on its own model: `personas.ai_provider_config_id` points at an
`ai_provider_configs` row, or is null to follow whichever config is active. The provider is resolved once
per speaker, so a single round can mix models. Deleting a configuration sets the column back to null rather
than deleting the persona.

Identity and display data live in the `personas` table (seeded by migration). System prompts live in
`app/core/personas.py`, keyed by role, and are **never** returned by any endpoint. Personas reply in
whatever language the user writes in.

**How a round runs.** `GET /api/v1/conversations/{id}/stream` runs the round *inline* and streams it over
SSE — opening that stream is what makes the personas speak, so it is deliberately non-idempotent. Order is
`Architect → Researcher → Challenger`; the Arbiter steps in on its own every `ARBITER_EVERY_N_ROUNDS`
rounds, scores the options as percentages, and writes the winning ticket(s) into **Backlog**.

An `asyncio.Lock` per conversation makes a second concurrent stream return `409` instead of a duplicate
round. Two consequences worth knowing: a closed tab abandons the round (committed messages survive, the
rest never happen), and the lock is per **process** — this stops being correct the moment the app is not
single-user on localhost.

Streaming is **message-level**: a persona appears when it finishes. That is what keeps the provider
interface down to a single `chat()` returning `str` across all four vendors.

**One verdict produces one *or several* tickets.** The Arbiter splits work that has independently
shippable parts, ordered so each unblocks the next. The foreign key lives on `tickets.verdict_id` (null
for anything typed by hand on the board). `ArbiterVerdict.tickets` is capped at `MAX_TICKETS_PER_VERDICT`
(8) — every entry is a row written on the model's say-so, and the cap is what stops a confused Arbiter
flooding the board in one write.

`ArbiterTicket` has **no status field**; the status is hardcoded to `BACKLOG` in `app/services/arbiter.py`
and asserted by `tests/test_arbiter_verdict.py`. That is the drag gate expressed in code.

### The AI layer

Provider-agnostic: an `AIProvider` ABC with one `chat()` method, one adapter per vendor, and an
`ai_provider_configs` row (provider, model, Fernet-encrypted key, `is_active`) that is CRUD'd over the
API. Provider and model are switched **at runtime**, not through `.env`. Exactly one config may be active.

Supported `provider` values: `anthropic`, `gemini`, `groq`, `openrouter`.

The **Claude Agent SDK is not used for chat** — it stays reserved for ticket execution (stage 4).

Vendor exception text is never forwarded to a client: it can echo the request it came from, and the API
key travels in that request. Only messages this codebase wrote itself (`AIProviderError.safe_to_display`)
reach the browser.

Uploaded `.txt` / `.md` documents are ingested as `document` messages: decoded in memory, never written to
disk, the filename kept for display only.

---

## 2. Tech stack

| Component | Choice |
|---|---|
| Language | Python 3.12+ |
| HTTP API | FastAPI |
| Database | PostgreSQL 18 |
| ORM | SQLAlchemy 2.0 |
| DB driver | Psycopg 3 |
| Migrations | Alembic |
| Validation & config | Pydantic / Pydantic Settings |
| Secret encryption | `cryptography` (Fernet) |
| Chat providers | `anthropic`, `google-genai`, `groq`, `openai` (also used for OpenRouter) |
| Ticket execution | Claude Agent SDK *(planned — stage 4)* |
| Tests | pytest |

Default model: `claude-opus-5`, unless configured otherwise.

Exact pinned versions live in `requirements.txt`.

---

## 3. Setup

### Prerequisites

- **Python 3.12+.** On the primary dev machine bare `python` is a 32-bit Python 3.10, so name the
  interpreter explicitly: `py -3.12`.
- **PostgreSQL 18**, with a role and database already created for the app.
  On the dev machine PG 18 listens on **port 5433** (5432 is PG 17, 5434 is PG 14) — pointing at 5432
  silently connects to the wrong server. `psql` on PATH there is 17.2, so use `psql -p 5433` to reach 18.

### First-time install

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env
```

Then fill in `.env`:

1. `DB_USER`, `DB_PASSWORD`, `DB_NAME` — blank in the example on purpose; real identifiers are never
   committed. Use whatever role and database you created.
2. `AI_CONFIG_ENCRYPTION_KEY` — generate once:

   ```powershell
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Rotating this key orphans every stored provider API key — they become undecryptable and must be
   re-entered through `PATCH /api/v1/ai-provider-configs/{id}`.

**The app will not start without a `.env`.** `Settings` gives `DB_*` and `AI_CONFIG_ENCRYPTION_KEY` no
defaults, deliberately: missing configuration fails loudly instead of quietly connecting somewhere
unintended.

### Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `APP_NAME` | `Bantu Coding` | FastAPI app title |
| `APP_ENV` | `development` | Environment label |
| `LOG_LEVEL` | `INFO` | Log level |
| `DB_HOST` | *(required)* | Postgres host |
| `DB_PORT` | *(required)* | Postgres port — **5433** for PG 18 on the dev machine |
| `DB_USER` | *(required)* | Postgres role |
| `DB_PASSWORD` | *(required)* | Role password (percent-encoded into the URL) |
| `DB_NAME` | *(required)* | Database name |
| `AI_CONFIG_ENCRYPTION_KEY` | *(required)* | Fernet key encrypting `ai_provider_configs.api_key` at rest |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated origin allowlist — never `*` |
| `DOCUMENT_MAX_BYTES` | `262144` | Max size of an uploaded `.txt`/`.md` document (256 KiB) |
| `CHAT_HISTORY_CHAR_BUDGET` | `10000` | Characters of room history sent per persona turn; oldest dropped first |
| `PERSONA_MAX_TOKENS` | `4096` | Cap on one persona reply |
| `ARBITER_EVERY_N_ROUNDS` | `2` | Arbiter cadence; a conversation can override it per row |

### Database migrations

```powershell
alembic upgrade head      # apply
alembic current           # what the database is actually at
alembic history           # the six migrations
alembic downgrade -1      # roll one back
```

Migration chain: `ef720fa92c78` (tickets) → `f52211af4ab5` (discussion room) → `b7c4e0d51a93` (verdicts)
→ `22b059f01724` (a verdict can produce many tickets) → `db5519dc8798` (projects)
→ `a3f1c27b5e04` (a model per persona).

`db5519dc8798` **deletes every existing ticket, conversation, message and verdict** — they predate
projects and have no project to belong to, and its `downgrade()` does not bring them back. `personas` and
`ai_provider_configs` are untouched.

### Configure an AI provider

Personas cannot speak until one `ai_provider_configs` row is active:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ai-provider-configs \
  -H "Content-Type: application/json" \
  -d '{"provider":"anthropic","model":"claude-opus-5","api_key":"...","is_active":true}'
```

The key is Fernet-encrypted at rest and never returned — reads expose a preview only.

---

## 4. Running

```powershell
.\.venv\Scripts\Activate.ps1

uvicorn app.main:app --reload    # http://127.0.0.1:8000
```

Interactive API docs: `http://127.0.0.1:8000/docs`.

There is **no `/health` endpoint** and none is wanted — it was proposed once and rejected as ceremony.

The app **binds to localhost and stays there until it has authentication**. There is no auth yet; an
unauthenticated endpoint that eventually triggers code execution and a git push is the worst thing in this
codebase to expose.

### Tests

```powershell
pytest
```

Tests are pure-Python and do not touch a database — schema validation, config, document ingest, message
mapping, persona wiring, and the Arbiter's verdict gate.

### Build

There is no build step: this is a plain Python service run under Uvicorn. A production deployment target
has not been decided yet, and neither has the isolation mechanism for agent runs — see *Not decided yet*.

---

## 5. API

Base URL `/api/v1`. No response envelope: endpoints return the resource itself and use HTTP status codes
for the outcome (`201` create, `204` delete, `404` missing, `422` validation). `PATCH` uses `exclude_unset`,
so an omitted field is left alone while an explicit `null` clears it.

### Projects

| Method | Path | Description |
|---|---|---|
| `GET` | `/projects` | List projects |
| `POST` | `/projects` | Create one; a duplicate name returns `409` |
| `GET` | `/projects/{id}` | One project |
| `PATCH` | `/projects/{id}` | Partial update |
| `DELETE` | `/projects/{id}` | Delete it, its rooms and its board — cascading, immediate |
| `GET` | `/projects/{id}/tickets` | That project's board |
| `GET` | `/projects/{id}/conversations` | That project's rooms |

### Tickets

| Method | Path | Description |
|---|---|---|
| `GET` | `/tickets` | List all tickets, across every project |
| `POST` | `/tickets` | Create a ticket; `project_id` is required, `404` if unknown |
| `GET` | `/tickets/{id}` | One ticket |
| `PATCH` | `/tickets/{id}` | Partial update (title, body, status) |
| `DELETE` | `/tickets/{id}` | Delete |

### Personas

| Method | Path | Description |
|---|---|---|
| `GET` | `/personas` | The four seeded characters (never their system prompts) |
| `PATCH` | `/personas/{id}` | Point a persona at an `ai_provider_config`, or send `null` to follow the active one |

### Conversations

| Method | Path | Description |
|---|---|---|
| `GET` | `/conversations` | List conversations, across every project |
| `POST` | `/conversations` | Create one; `project_id` is required, `404` if unknown |
| `GET` | `/conversations/{id}` | One conversation |
| `DELETE` | `/conversations/{id}` | Delete it and its messages |
| `GET` | `/conversations/{id}/messages` | Room history, ordered by id |
| `POST` | `/conversations/{id}/messages` | Post the user's own message |
| `POST` | `/conversations/{id}/documents` | Upload a `.txt`/`.md` file as a `document` message |
| `GET` | `/conversations/{id}/verdicts` | Verdicts, ordered by round |
| `GET` | `/conversations/{id}/stream` | **Runs the next round** and streams it as SSE |

### AI provider configs

| Method | Path | Description |
|---|---|---|
| `GET` | `/ai-provider-configs` | List configs (API key shown as a preview only) |
| `POST` | `/ai-provider-configs` | Create; activating one deactivates the rest |
| `PATCH` | `/ai-provider-configs/{id}` | Update provider, model, key, or active flag |
| `DELETE` | `/ai-provider-configs/{id}` | Delete |

### SSE events on `/conversations/{id}/stream`

`text/event-stream`, consumed with `EventSource`. Event types:

| `event:` | Payload |
|---|---|
| `round_started` | `round_index` |
| `persona_thinking` | `round_index`, `persona_id`, `role` |
| `message` | the finished `MessageRead` |
| `verdict` | the `VerdictRead`, including the ids of the tickets it wrote |
| `round_completed` | `round_index` |
| `error` | a `detail` string this codebase wrote itself |

A second concurrent stream on the same conversation gets `409`.

---

## 6. Project layout

```
app/
  api/          HTTP only — accept, validate, call a service, return
  core/         config, enums, security, persona system prompts
  db/           engine, session, declarative base
  models/       SQLAlchemy tables
  schemas/      Pydantic request/response contracts
  services/     business logic — discussion, arbiter, documents, ai/ adapters
  main.py       app + CORS + router registration
alembic/        migration environment and versions
tests/          mirrors app/
.claude/specs/  plan-driven work history (plans -> in-progress -> plans-executed)
```

**Dependency direction:** `API → Services → (DB, Claude Agent SDK, Git/GitHub)`. Models (DB representation)
and schemas (API contract) are never interchangeable. Enums shared between a model and its schemas live in
`app/core/enums.py`, so neither imports the other.

---

## 7. Security

The sharpest surface in this project is stage 4: the backend will run Claude Code with Bash, Write, and
Edit against a real repository, holding real credentials, and push the result to GitHub.

Ticket text is **untrusted input that becomes instructions for a process with shell access**:

```
chat content -> AI writes a ticket -> user drags -> agent runs (Bash/Write/Edit) -> push to GitHub
```

Everything upstream is attacker-reachable in ordinary use — a pasted error log, a quoted web page, a
dependency's README, an uploaded document. The target repo's own contents are untrusted too. This is not
solved by filtering; it is solved by limiting what a compromised run can reach.

Non-negotiable controls for agent-run code (full text in `CLAUDE.md` section 6):

1. Every run is isolated — a boundary per run, with only the target repo mounted. `cwd` is not a boundary.
2. The runner gets **its own** credentials: an `ANTHROPIC_API_KEY` separate from the app's, and a GitHub
   credential scoped to the target repos only. Never an account-wide classic token.
3. Never push to a target repo's default branch — a run pushes to its own branch and opens a PR.
4. Never bypass the Agent SDK permission model to make a task easier.
5. Restrict network egress from a run.
6. The app binds to localhost until it has authentication; CORS stays an explicit allowlist.

Plus, for the driving code: nothing from a ticket's *prose* may choose a repo, branch, credential, or
directory — those come from typed columns and foreign keys. Never interpolate ticket text into a shell
command or git argument. Log metadata, never payloads. A failed run still tears down its workspace, in a
`finally`.

### Secrets

Every secret comes from `.env`, never from source. `.env` is gitignored; `.env.example` documents the
*shape* of configuration with blank values. Real database names, roles, and hostnames stay out of every
committed file — including specs, tests, and fixtures. The app's secrets and the agent runner's secrets are
two separate sets, and the app's `.env` must never be reachable from inside a run.

---

## 8. Working on this repo

`.claude/specs/` holds a plan-driven history: `plans/` (written, not approved) → `in-progress/` (active
work) → `plans-executed/` (permanent archive, with execution notes). `.claude/specs/INDEX.md` indexes
every executed spec with grep hints. Non-trivial work gets a spec before code.

Behavioral rules for AI assistants working here live in `CLAUDE.md` — read it before changing anything.
Auto-commit and auto-push are a **product feature** aimed at *target* repos; they are not a permission to
push this repo.

---

## 9. Status

**Built:** projects, the ticket board API, the four-persona discussion room, document ingest, the SSE round
stream, the Arbiter's scored verdict writing tickets, and runtime-switchable AI providers. The local
database is migrated to head (`db5519dc8798`) and is empty of tickets and conversations — that migration
cleared the pre-project rows.

**Not built:** agent runs — nothing yet executes a ticket, clones a target repo, or pushes. No
authentication. The frontend chat UI is still a placeholder in `bantu-coding-fe`.

**Next:** verify a full discussion round end to end, then the FE chat UI, then agent execution — which
needs its isolation decision settled first.

### Not decided yet

- **How** agent runs are isolated (Docker, a VM, or a dedicated unprivileged user). *That* they are
  isolated is settled and required.
- Authentication. Single-user on localhost is the current assumption.
- The agent runner's GitHub credential, and how a target repo is cloned. **Where the repo record lives is
  now settled** — `projects.repo_url` and `projects.default_branch`. What is still open is the credential:
  its *shape* is fixed (per-repo scoped, separate from the app's), but whether it is a PAT per project, one
  shared, or a GitHub App installation is decided with the code that uses it.
- The production deployment target.
