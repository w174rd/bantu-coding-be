---
date: 2026-08-29
title: Discussion room — data layer, persona cast, and provider-agnostic AI config
status: done
tags: [persona, conversation, message, discussion, ai-provider, agnostic, document-ingest, migration, api]
commits: []
---

# Discussion room — data layer, persona cast, and provider-agnostic AI config

## Context

User request: a Slack-style **discussion panel** where four AI characters debate a problem the user brings in
(typed, or uploaded as a `.txt` / `.md` document), the user can speak in the room too, and one of the four
eventually decides, shows a percentage breakdown, and writes a ticket from the winning solution.

Grepped `INDEX.md` for `persona|conversation|message|chat|provider|ai`: **no prior spec covers any of it.**
The index lists "Multi-Persona Chat — personas, conversations, messages" as an *expected* area with no entry yet.
Two prior specs are relevant as carry-overs, not as overlap:

- [initial-scaffolding](../plans-executed/2026-08-29-initial-scaffolding.md) — `Settings` has no defaults for
  required config on purpose; Alembic reads the URL from `Settings`, not `alembic.ini`; PG18 is on **5433**.
- [ticket-model-and-crud](../plans-executed/2026-08-29-ticket-model-and-crud.md) — settled the API conventions this
  spec must follow (`/api/v1/<plural>`, **no response envelope**, `exclude_unset` PATCH, shared enums in
  `app/core/enums.py`). Also recorded three migration gotchas reused below: `app/models/__init__.py` must import
  every model or autogenerate emits a drop-everything migration; `drop_table` leaves a native enum **type**
  behind so `downgrade` must drop it explicitly; and `values_callable` is required or SQLAlchemy persists enum
  *names* instead of values.

### Reference project: `nara-persona-api`

The user asked for the AI layer to be **model/provider agnostic, like Nara**. That sibling repo
(`../nara-persona-api`) already solves this, and its shape is adopted here:

- `app/services/ai/base.py` — an `AIProvider` ABC with one method, `chat(messages, system) -> str`, plus `AIProviderError`.
- `app/services/ai/provider.py` — one adapter class per vendor and a `get_provider(db)` factory.
- An `ai_provider_configs` table (provider, model, encrypted `api_key`, `is_active`) CRUD'd over the API, so the
  provider and model are switched **at runtime without a redeploy or an env change**.
- `app/core/security.py` — Fernet encrypt/decrypt for the stored API key, keyed from an env var.

**What is deliberately NOT copied from Nara**, because this repo settled differently:

| Nara does | This repo | Why |
|---|---|---|
| `ApiResponse{status,message,code,content}` envelope | plain resources + status codes | settled in the ticket spec |
| `X-API-Key` header auth (`verify_api_key`) | none | CLAUDE.md §0 — auth undecided, app stays on localhost |
| Message bodies encrypted with a user passphrase (`X-Encryption-Key`) | stored as plain text | Nara's content is a private diary; a discussion room's content becomes a ticket body the app itself must read. A passphrase header would also require the auth decision that is still open. **Only the provider API key is encrypted.** |
| `settings` as a module-level object | `get_settings()` (`lru_cache`) | this repo's existing pattern |

**Note on exclusive activation.** `get_provider` reads the active config with `scalar_one_or_none()`, which raises
`MultipleResultsFound` if two rows are ever active at once. Nara keeps that from happening in its route layer —
`_deactivate_others` runs on both create and patch — and this spec does the same. The constraint is enforced in
the routes, not in the schema; a partial unique index (`... WHERE is_active`) would enforce it in the database
instead, but it interacts badly with SQLAlchemy autoflush ordering on PATCH, so it is deliberately not used here.

### Decisions this task settles

Four items sat under CLAUDE.md §0 "Decisions NOT yet made". The user's answers close three of them:

1. **The persona model** — **four fixed personas, one shared Slack-style channel**, the user is a participant in
   that same channel. Not user-configurable yet.
2. **AI layer for persona chat** — provider-agnostic, DB-configured, Nara's pattern. The Claude Agent SDK stays
   reserved for *ticket execution* and is untouched here.
3. **Progress streaming to the FE** — **SSE**. (Consumed in the follow-up spec; this one adds no streaming.)
4. **Discussion flow** — a round runs `Architect → Researcher → Challenger` automatically, and **the Arbiter
   steps in on its own after N rounds**. (Also the follow-up spec.)

`CLAUDE.md` in both repos must be updated to record 1–4, the same way the ticket spec moved the board-columns
decision out of the open list.

## Goal

Everything the discussion room needs **that costs zero API spend to build and test**: the four-persona cast, the
conversation/message tables, document ingest, room CRUD, and the provider-agnostic AI configuration table with
its encrypted key storage. No provider is called and no persona speaks yet — that is the follow-up spec.

## The cast

Four characters, named to map onto the user's A/B/C/D. Avatar is an emoji and accent colour is a hex string;
both are display data the FE reads from `GET /api/v1/personas` rather than hardcoding.

| | Role (`PersonaRole`) | Name | Avatar | Accent | What they do |
|---|---|---|---|---|---|
| A | `ARCHITECT` | **Architect** | 🏗️ | `#6366f1` | Proposes the solution; revises it when the Challenger lands a hit |
| B | `RESEARCHER` | **Researcher** | 📚 | `#14b8a6` | Feeds the Architect facts, constraints, prior art, trade-offs |
| C | `CHALLENGER` | **Challenger** | 🧨 | `#f43f5e` | Antithesis — attacks the proposal to prove it holds |
| D | `ARBITER` | **Arbiter** | ⚖️ | `#f59e0b` | Scores the options, emits percentages, writes the ticket |

**Update during execution:** the cast was first drafted with personal names (Arka, Bayu, Citra, Damar). The user
asked for those to be dropped in favour of the role names above, so `name` now mirrors `role`. The column stays
separate: `name` is display text the FE renders, `role` is the enum that code branches on. The system prompts
were rewritten to address each other by role ("the Challenger", not "Citra").

System prompts live in `app/core/personas.py`, keyed by role — one source of truth, editable without a
migration. The DB table stores identity and display data only; **prompts are never returned by the API**.

Each prompt instructs the persona to answer in whatever language the user writes in, so the room follows the
user rather than forcing English or Indonesian.

## Approach

1. **`app/core/enums.py`** — add two enums beside `TicketStatus`, both backed by native Postgres enums:
   - `PersonaRole`: `architect`, `researcher`, `challenger`, `arbiter` (type `persona_role`).
   - `MessageAuthorKind`: `user`, `persona`, `document` (type `message_author_kind`).

2. **`app/core/personas.py`** — new. The cast as a frozen mapping `PersonaRole -> PersonaProfile`
   (name, avatar, accent colour, tagline, display order, system prompt). No DB import; pure constants.

3. **Models** — four new files, each registered in `app/models/__init__.py` (the autogenerate trap above):
   - `app/models/persona.py` — `id`, `role` (unique, native enum), `name`, `avatar`, `accent_color`,
     `tagline`, `display_order`. No timestamps: it is a seeded, static table.
   - `app/models/conversation.py` — `id`, `title` (nullable), `created_at`, `updated_at`.
   - `app/models/message.py` — `id`, `conversation_id` (FK, `ondelete="CASCADE"`), `author_kind`,
     `persona_id` (FK, nullable — set only when `author_kind == persona`), `content` (Text),
     `round_index` (Integer, default 0), `source_name` (nullable — the uploaded filename, display only),
     `created_at`. Index on `(conversation_id, id)`.
   - `app/models/ai_provider_config.py` — `id`, `title` (nullable), `provider`, `model`, `api_key` (Text,
     Fernet ciphertext), `is_active`, `created_at`, `updated_at`.

4. **Migration** — one revision creating the four tables and the two enum types, plus a `bulk_insert` seeding the
   four personas. `downgrade` drops the tables **and** both enum types explicitly, per the gotcha the ticket spec
   recorded. Autogenerated, then read line by line and hand-corrected — autogenerate output is a draft.

5. **`app/core/security.py`** — new, trimmed from Nara: `encrypt`, `decrypt`, `EncryptionError`, and
   `get_ai_config_key()` reading `AI_CONFIG_ENCRYPTION_KEY` from `Settings`. Nara's passphrase-derivation and
   `X-API-Key` helpers are **not** carried over (no auth decision yet).

6. **Schemas + routes** — following the settled conventions (plural URLs, no envelope, `exclude_unset` PATCH):
   - `GET /api/v1/personas` — the cast, ordered by `display_order`.
   - `GET|POST /api/v1/conversations`, `GET|DELETE /api/v1/conversations/{id}`.
   - `GET /api/v1/conversations/{id}/messages` — ordered by `id`, not `created_at`. Nara hit this: messages
     written in one transaction share an identical `now()` and come back shuffled.
   - `POST /api/v1/conversations/{id}/messages` — appends a `user` message. In this spec it only stores;
     the follow-up spec makes it trigger a round.
   - `POST /api/v1/conversations/{id}/documents` — multipart upload, stored as a `document` message.
   - `GET|POST /api/v1/ai-provider-configs`, `PATCH|DELETE /api/v1/ai-provider-configs/{id}`.
     **Activation is exclusive**: setting `is_active=true` clears it on every other row in the same transaction,
     so `get_provider` can never see two active rows.
     The read schema returns `api_key_preview` (last 4 chars), **never the key** — CLAUDE.md §7.

7. **Document ingest** — `.txt` and `.md` only, decided by extension *and* a UTF-8 decode that must succeed;
   rejected with `422` otherwise. Capped at `DOCUMENT_MAX_BYTES` (default 256 KiB) read from `Settings`.
   The file is **never written to disk** — it is decoded in memory and stored as message text, so the untrusted
   filename can never act as a path. `source_name` is kept for display only.

8. **Config** — `Settings` gains `ai_config_encryption_key: str` (**no default**, matching how `DB_*` fails loudly
   rather than starting misconfigured) and `document_max_bytes: int = 262144`. `.env.example` documents both with
   blank / default values and the one-liner that generates a Fernet key.

9. **`requirements.txt`** — `cryptography` (Fernet) and `python-multipart` (FastAPI's `UploadFile` requires it).
   **No provider SDK is added in this spec** — nothing calls a provider yet.

10. **`app/main.py`** — register the new routers.

11. **`CLAUDE.md` in both repos** — move the four settled decisions out of "Decisions NOT yet made" into the
    product description, and record the cast so the FE session does not re-invent names or colours.

## Security notes

- **Uploaded documents are untrusted input under CLAUDE.md §6.1.** Their text flows persona → ticket body →
  eventually an agent run with a shell. This spec does not try to filter that (§6.1 is explicit that filtering
  does not work); it keeps the text strictly as **data**: stored, displayed, never interpolated into a command,
  a path, or a git argument. The control that matters lands where runs are executed, not here.
- The `ai_provider_configs` row is the **app's** credential, not the runner's. CLAUDE.md §6.3 item 2 keeps those
  two sets separate — this table must never be mounted into or readable from an agent run.
- Persona system prompts are not exposed by any endpoint.

## Deliberately out of scope — the follow-up spec

Everything that spends tokens, planned as `2026-08-…-discussion-round-and-verdict.md` once this lands:

- `app/services/ai/base.py` + `provider.py` — the ABC and the vendor adapters; provider SDKs in `requirements.txt`.
- The orchestrator: `Architect → Researcher → Challenger` as one automatic round, each seeing the room's history.
- **The Arbiter's cadence** — the `N` in "after N rounds", as a setting plus a per-conversation override column.
- The Arbiter's verdict: its own table, scored options with percentages the FE renders as the graph, and creation of
  the winning ticket **in `Backlog`** — which respects the §0 invariant, since only the user's drag moves a
  ticket into In Progress.
- The SSE endpoint streaming the room live.
- A history/token budget per request (Nara's `_window` solves this; it will be adapted, not copied blindly).

Also out of scope, unchanged from prior specs: auth, and DB-backed tests (still no test-database strategy).

## Verification

- `alembic upgrade head` applies against PG18 on **5433**; `alembic downgrade -1` then `upgrade head` round-trips,
  proving both enum types are dropped properly.
- The four personas are present and correctly ordered via `GET /api/v1/personas`.
- Full round trip over HTTP: create a conversation → post a user message → upload a `.md` → list messages and
  confirm ordering, `author_kind`, and `source_name` → delete the conversation and confirm the messages cascade.
- Ingest rejections checked: a `.pdf`, an oversized file, and an invalid-UTF-8 `.txt` each return `422`.
- Provider config: create two, activate the second, confirm the first was deactivated in the same write; confirm
  `api_key` never appears in any response body; confirm a stored key decrypts back to what was sent.
- `pytest` passes.

## Risks / Trade-offs

- **A `personas` table for four rows that never change** is arguably more than the moment needs — the alternative
  is a code-only cast with `messages.persona_role` as a plain enum and no table at all. The table is proposed
  because messages need a durable author reference and the FE needs an endpoint for names, avatars, and colours
  rather than hardcoding them into a second repo. Say so before approval if you would rather have the leaner
  version; it is cheap now and a migration later.
- **`round_index` on `messages` is forward-looking** — nothing in this spec increments it past 0. It is included
  because the user chose a round-structured flow, which makes the round part of a message's identity rather than
  a hypothetical feature; leaving it out means an `ALTER` in the very next spec.
- **`AI_CONFIG_ENCRYPTION_KEY` has no default, so the app will not start without it.** Deliberate and consistent
  with `DB_*`, but it does mean a stale `.env` breaks startup after this lands — `.env.example` will say so.
- **Rotating that key orphans every stored API key** (they become undecryptable and must be re-entered). Nara has
  the same property. Worth knowing before it happens rather than after.
- **Two native enums** means adding a persona role or a message kind is a migration. Same trade the board columns
  made, and for the same reason.
- This spec fixes the FE's chat contract. The FE's `routes/Chat.tsx` is still a placeholder blocked on exactly
  this decision, so the shape chosen here is what it will be built against.

## Files That Will Change

- `app/core/enums.py` — add `PersonaRole`, `MessageAuthorKind`
- `app/core/personas.py` — new, the cast + system prompts
- `app/core/security.py` — new, Fernet encrypt/decrypt
- `app/core/config.py` — `ai_config_encryption_key`, `document_max_bytes`
- `app/models/persona.py` — new
- `app/models/conversation.py` — new
- `app/models/message.py` — new
- `app/models/ai_provider_config.py` — new
- `app/models/__init__.py` — import all four
- `app/schemas/persona.py` — new
- `app/schemas/conversation.py` — new
- `app/schemas/message.py` — new
- `app/schemas/ai_provider_config.py` — new
- `app/api/personas.py` — new
- `app/api/conversations.py` — new (conversations + their messages + document upload)
- `app/api/ai_provider_configs.py` — new
- `app/main.py` — register the new routers
- `alembic/versions/<hash>_create_personas_conversations_messages.py` — new, generated then reviewed
- `requirements.txt` — `cryptography`, `python-multipart`
- `.env.example` — document the two new vars
- `tests/test_personas.py` — new, cast completeness and uniqueness
- `tests/test_document_ingest.py` — new, extension/size/decode rules
- `tests/test_ai_provider_config_schemas.py` — new, key is previewed and never echoed
- `CLAUDE.md` (this repo) — record the four settled decisions and the cast
- `../bantu-coding-fe/CLAUDE.md` — record the same, for the chat UI

---

## Progress

- [x] `app/core/enums.py` — `PersonaRole`, `MessageAuthorKind`
- [x] `app/core/personas.py` — cast + system prompts
- [x] `app/core/security.py` — Fernet encrypt/decrypt
- [x] `app/core/config.py` + `.env.example` + local `.env` — new settings
- [x] `requirements.txt` — `cryptography==50.0.1`, `python-multipart==0.0.32`, installed into `.venv`
- [x] Four models + `app/models/__init__.py`
- [x] Four schema modules
- [x] `app/services/documents.py` — text extraction
- [x] Three routers + `app/main.py` registration (16 endpoints confirmed in the OpenAPI schema)
- [x] Migration written by hand — **not yet applied**
- [x] `pytest` green — 33 passed
- [x] `CLAUDE.md` updated in both repos

**BLOCKED — needs the user:**

- [ ] `alembic upgrade head` / `downgrade` round-trip
- [ ] HTTP round trip against the running app

`DB_USER`, `DB_PASSWORD` and `DB_NAME` are all **blank** in the local `.env`, so nothing can reach Postgres
(`fe_sendauth: no password supplied` on port 5433). They held real values when the ticket spec ran — that spec's
Results record `ef720fa92c78` applied and `alembic current` at head — so the credentials were cleared or the
file was overwritten from `.env.example` some time after. They cannot be recovered from the repo; §7 keeps them
out of every committed file by design.

Autogenerate was therefore impossible, and the migration `f52211af4ab5_create_discussion_room_tables.py` was
written by hand against the model definitions. **It has never been executed** — it is the one part of this spec
carrying no verification at all, and it is exactly the kind of file the ticket spec found autogenerate getting
wrong twice.

---

## Results & Execution Notes

Built as planned. **33 tests pass, all 16 endpoints appear in the generated OpenAPI schema — but nothing in
this spec has touched a database.** Read the "Not verified" block below before trusting the migration.

### Deviations from the approved plan

1. **`app/services/documents.py` was added** — not in the plan's file list. The plan implied the ingest rules
   lived in the route, but decode/size/extension validation had to be a pure function to be testable without a
   database or a running app. It raises `ValueError`; the route maps that to `422`. No new exception class for a
   single call site.
2. **Encryption round-trip tests were folded into `tests/test_ai_provider_config_schemas.py`** rather than a
   separate `tests/test_security.py`. Three tests: round-trip, ciphertext does not contain the plaintext, and a
   rotated key produces a legible `EncryptionError`.
3. **`api_key_preview` returns `"(unreadable)"` instead of raising** when a row cannot be decrypted. Without
   this, one row written under a rotated key makes `GET /api/v1/ai-provider-configs` return `500` for the whole
   list — which is the exact screen a user needs in order to re-key or delete that row. Key rotation was already
   listed as a known risk, so this is a real path, not defensive padding.
4. **The cast was renamed mid-execution.** First drafted with personal names (Arka, Bayu, Citra, Damar); the user
   asked for role names instead. `name` now mirrors `role`, the column kept separate because `name` is display
   text and `role` is what code branches on. Prompts rewritten to address each other by role.

### Corrected mid-flight

The spec originally claimed, as a finding, that `nara-persona-api` had a defect letting two provider configs be
active at once. **That was wrong** — its `app/api/ai_provider_configs.py` calls `_deactivate_others` on both
create and patch. Corrected in the Context section before implementation; this repo enforces exclusivity the
same way, in the route layer.

### NOT VERIFIED — the migration has never run

`DB_USER`, `DB_PASSWORD` and `DB_NAME` are **blank** in the local `.env`, so Postgres was unreachable for the
whole of this task (`fe_sendauth: no password supplied`, port 5433). The ticket spec's Results record
`ef720fa92c78` applied and `alembic current` at head, so those credentials existed and were later cleared or
the file was overwritten from `.env.example`. Section 7 keeps them out of every committed file, so they cannot
be recovered from the repo.

Consequences, all of which the next session inherits:

- `alembic revision --autogenerate` was impossible. `f52211af4ab5_create_discussion_room_tables.py` was
  **hand-written against the model definitions** and has never been executed. The ticket spec caught
  autogenerate producing a broken migration twice; a hand-written one gets no more trust than that.
- The `upgrade` → `downgrade -1` → `upgrade` round-trip that proves both enum types drop cleanly has **not**
  been run. That round-trip is the only thing that catches the `drop_table`-leaves-the-TYPE-behind trap, and
  this migration creates *two* native enums.
- No endpoint has been exercised over HTTP. Ordering, cascade delete, `422` ingest rejections and exclusive
  activation are all argued from the code, not observed.
- `bulk_insert` of the four personas into a native-enum column is the single most likely thing to fail on first
  run. If it does, the fix is a `postgresql.ENUM(name='persona_role', create_type=False)` on the seed table.

**First action once `.env` is filled:** `alembic upgrade head`, then `downgrade -1`, then `upgrade head`, then
the HTTP round trip listed under Verification. Until that passes, treat this schema as a proposal.

### What was verified

- `pytest` — 33 passed. Cast completeness, ingest rules (including an oversized file, invalid UTF-8, a `.pdf`,
  and a traversal-shaped filename), schema shapes, and Fernet round-trip.
- All 16 routes present in `app.openapi()`, and the document upload's multipart field is named `file`.
- `AiProviderConfigRead.model_fields` contains no `api_key` — the no-secret-in-responses guarantee is
  structural, asserted by a test rather than by review.
- Dependency versions pinned to what actually installed (`cryptography==50.0.1`, `python-multipart==0.0.32`),
  not to the guesses written first.

### Contract handed to the FE

`../bantu-coding-fe/CLAUDE.md` section 1 now carries the persona/conversation/message/provider-config tables and
their TypeScript types, **plus an explicit warning that these routes return 500 until the migration runs.** Its
stale "Current status: SCAFFOLDED, NO FEATURES" block was also corrected — the board, `src/api/`, `src/state/`,
`src/types/` and nine components have existed since five earlier specs.

### Still open

- `../bantu-coding-be/CLAUDE.md` lines 61–71 still say **"Current status: THE REPO IS EMPTY"** and name a
  `/health` endpoint as the first milestone — both false, and `/health` was explicitly rejected by the user in
  the scaffolding spec. Reported, left unfixed: outside this spec's scope.
- The follow-up spec (providers, round orchestration, the Arbiter's verdict, SSE, ticket creation) is unwritten.

## Recall Hints

discussion-room, persona-cast, four-personas, architect-researcher-challenger-arbiter, role-names-not-personal-names,
provider-agnostic, nara-persona-api-reference, AIProvider-ABC, ai_provider_configs, runtime-provider-switch,
fernet-encrypted-api-key, AI_CONFIG_ENCRYPTION_KEY, api_key_preview-never-the-key, unreadable-preview-after-rotation,
exclusive-activation-route-layer, no-partial-unique-index-autoflush-ordering, nara-defect-claim-was-wrong,
persona_role-native-enum, message_author_kind-native-enum, round_index-forward-looking, source_name-display-only,
document-ingest-txt-md-only, utf8-decode-required, 256KiB-cap, read-max_bytes-plus-one, filename-never-a-path,
untrusted-document-6.1-laundering, messages-ordered-by-id-not-created_at, cascade-delete-conversation,
migration-hand-written-never-applied, blank-db-credentials-blocked-verification, fe_sendauth-no-password-supplied,
bulk_insert-native-enum-risk, postgresql-ENUM-create_type-False-fallback, python-multipart-required-for-UploadFile,
services-documents-pure-function, claude-md-repo-is-empty-still-stale, fe-claude-md-status-was-stale
