---
date: 2026-08-29
title: Ticket model, first migration, and CRUD API
status: done
tags: [ticket, model, alembic, migration, api, crud, board]
commits: []
---

# Ticket model, first migration, and CRUD API

## Context

Task 4 of the starting sequence. Both scaffolds are done: BE at `d465ded`, FE at `e20a7ea`.

Grepped `INDEX.md` for `ticket|model|alembic|migration|api`: one prior spec, [initial-scaffolding](../plans-executed/2026-08-29-initial-scaffolding.md). Relevant carry-overs from its Results: Alembic is wired to `Settings` and `Base.metadata` but has **no migration yet**, `alembic/env.py` reads the URL directly rather than through `set_main_option()`, and `alembic current` has never successfully run because no database exists.

This is the first slice of the product spine. The board UI on the FE depends on it — FE section 1 forbids inventing endpoints, so nothing can be built there until these exist.

### Decisions the user settled for this task

Both were open items in section 0 of both repos. They are now fixed:

- **Board columns: `Backlog → In Progress → In Review → Done`.** "In Review" exists because section 6.3 requires the agent to open a PR rather than push to a default branch — so there is a real state between "the agent finished" and "you accepted it". Without the column, that state has nowhere to live and the board misreports where work actually is.
- **A finished agent run auto-advances the ticket** out of In Progress. This does not violate the drag gate: section 6.2 established that the gate guards *entry* into In Progress, not every transition.

## Goal

A `Ticket` table, the repo's first Alembic migration, and CRUD endpoints good enough for the FE to build a real board against. No agent execution, no chat, no personas.

## Approach

1. **`app/models/ticket.py`** — `Ticket(Base)`: `id` (PK), `title`, `body` (Text), `status`, `created_at`, `updated_at`. `status` is a native Postgres enum with the four values above, defaulting to `backlog`.
2. **`app/models/__init__.py`** — import `Ticket` so `Base.metadata` is populated before autogenerate runs. Without this, `alembic revision --autogenerate` sees an empty schema and emits a migration that drops everything; `alembic/env.py` already carries a comment warning about exactly this.
3. **`app/schemas/ticket.py`** — `TicketCreate` (title required, body optional), `TicketUpdate` (all optional, `exclude_unset` semantics), `TicketRead`. `TicketStatus` as a shared `Enum` reused by both model and schemas so the two cannot drift.
4. **`app/api/tickets.py`** — `GET /api/v1/tickets`, `POST /api/v1/tickets`, `GET /api/v1/tickets/{id}`, `PATCH /api/v1/tickets/{id}`, `DELETE /api/v1/tickets/{id}`. Router registered in `app/main.py` — the first route this app has ever had.
5. **First migration** — `alembic revision --autogenerate -m "create tickets"`, reviewed by hand before applying. Autogenerate output is a draft, not a result.
6. **Update both `CLAUDE.md` files** — move the two settled decisions out of "Decisions NOT yet made" and into the product description, in the BE and the FE, so the next session does not re-ask.

### Proposed: no response envelope

The API returns resources directly and uses HTTP status codes for outcomes — `201` on create, `404` on missing, `204` on delete. **This is a decision, not a default.** An older project of yours wrapped everything in `{status, message, code, content}`, and the FE `INDEX.md` still lists "envelope unwrapping" as an expected area, which presumes that pattern carries over.

Recommending plain resources: FastAPI, its generated OpenAPI, and the browser all already model errors through status codes, so an envelope duplicates that and forces every FE call site to unwrap before it can use anything. If you want the envelope instead, say so now — it is cheap to establish here and expensive to retrofit across every future endpoint.

Whichever way this goes, the FE `INDEX.md` line needs correcting to match.

## Deliberately out of scope

- **Triggering an agent run** when a ticket enters In Progress. That needs the isolation mechanism and job execution model, both still open. For now `PATCH` simply records the status.
- **`target_repo` on the ticket.** How target repos get registered is still an open decision; a ticket does not need one until agent runs exist.
- **Auth.** Still single-user, still localhost.
- **Database-backed tests.** Would require choosing a test-database strategy — a decision worth making on its own rather than by accident here. This spec adds schema-level tests only.

## Verification

- `alembic upgrade head` applies cleanly against PG18 on 5433, and `alembic current` finally reports a revision — closing the item left open by the scaffolding spec.
- The generated migration is read line by line before it is applied.
- `alembic downgrade -1` then `upgrade head` round-trips, proving the migration is reversible.
- Full CRUD exercised over HTTP against the running app: create → list → get → patch through all four statuses → delete → confirm 404.
- `pytest` passes.

## Risks / Trade-offs

- **A native Postgres enum makes adding a status later a migration**, not a code change. That is the point: the four columns are a product decision and should not be silently extendable. If you would rather they be cheap to change, a `varchar` with validation in Pydantic is the alternative — say so before this is approved.
- **Autogenerate is unreliable on a first migration.** It will be reviewed by hand, not trusted.
- **`updated_at` needs a server-side default and an onupdate**, or it silently stops tracking. Easy to get wrong and invisible when wrong.
- This is the first spec to add real routes, so it also fixes the API's URL shape (`/api/v1/...`) for everything that follows.

## Files That Will Change

- `app/models/ticket.py` — new
- `app/models/__init__.py` — import `Ticket`
- `app/schemas/ticket.py` — new
- `app/api/tickets.py` — new
- `app/main.py` — register the router
- `alembic/versions/<hash>_create_tickets.py` — new, generated then reviewed
- `tests/test_ticket_schemas.py` — new
- `CLAUDE.md` (this repo) — record the two settled decisions
- `../bantu-coding-fe/CLAUDE.md` — record the same two, and the resulting column list
- `../bantu-coding-fe/.claude/specs/INDEX.md` — correct the "envelope unwrapping" line to match the envelope decision

## Blocked on

**The database still does not exist.** No migration can be generated or applied until it does. On PG18 (port 5433), create a role and a database owned by it, then `cp .env.example .env` and fill `DB_USER`, `DB_PASSWORD`, `DB_NAME`. Per `CLAUDE.md` section 7 those values stay out of the repo, so choose them yourself; I will not create roles or databases.

Everything else in this spec can be written without the database — only the migration and the HTTP verification are gated.

---

<!-- Filled in when status = in-progress -->
## Progress
- [x] Database and role exist; `.env` filled
- [x] `TicketStatus` enum shared by model and schemas
- [x] `Ticket` model, imported in `app/models/__init__.py`
- [x] Schemas: `TicketCreate`, `TicketUpdate`, `TicketRead`
- [x] `app/api/tickets.py` with five routes, registered in `main.py`
- [x] Migration autogenerated and reviewed by hand
- [x] `alembic upgrade head` applies; `alembic current` reports a revision
- [x] `downgrade -1` / `upgrade head` round-trips
- [x] CRUD exercised over HTTP through all four statuses
- [x] `pytest` passes
- [x] Both `CLAUDE.md` files updated with the settled decisions

---

<!-- Filled in when status = done / reverted / cancelled -->
## Results & Execution Notes

Built and verified end to end. PostgreSQL 18.4 on port 5433, migration `ef720fa92c78` applied, `alembic current` reports head.

**Autogenerate produced a broken migration twice, in different ways. Both were caught by reviewing it rather than trusting it.**

1. **The first run emitted an empty migration** — `pass` in both directions. `alembic/env.py` imported `Base` but nothing ever imported `app.models`, so `Base.metadata` was empty when autogenerate compared it against the database. It would have "succeeded" and created no table. Fixed by adding `import app.models` to `env.py`; the regenerated migration then detected the table. Writing the import into `app/models/__init__.py` was not enough — something has to import the *package*.
2. **The generated downgrade would have poisoned the database.** `op.drop_table('tickets')` does not drop the enum TYPE, so a downgrade left `ticket_status` behind and the next upgrade failed with "type already exists". Added `sa.Enum(name='ticket_status').drop(op.get_bind())` by hand. The downgrade/upgrade round-trip in the verification is what proves it.

### Verified

- `alembic upgrade head` → `downgrade -1` → `upgrade head` round-trips cleanly.
- Schema in Postgres: `status` is a real `USER-DEFINED` type with `enum_range` = `{backlog,in_progress,in_review,done}`, timestamps are `timestamp with time zone`.
- CRUD over HTTP: `201` create, `200` list/get/patch, `204` delete, `404` after delete, `422` on empty title and on an out-of-range status.
- All four statuses round-trip through `PATCH`, and a title-only `PATCH` leaves `status` untouched — confirming `exclude_unset`.
- **`updated_at` advances on every PATCH while `created_at` holds.** Flagged in Risks as easy to get silently wrong; the `onupdate` is genuinely wired.
- 9 tests pass. Test rows cleaned up; table left empty.

### Other notes

- `values_callable` on the SQLAlchemy `Enum` is what stores lowercase `in_progress`; without it SQLAlchemy persists member *names* (`IN_PROGRESS`) and every schema and the FE would mismatch.
- No response envelope, per the decision recorded in `CLAUDE.md` section 5 along with the `/api/v1/<resource>` URL shape.
- The database and role were created by the user's superuser credential, used once and never written to disk. The app's own password exists only in the gitignored `.env`.
- FE `CLAUDE.md` section 1 was rewritten from "the contract does not exist" to the real endpoint table plus TypeScript types; its INDEX line presuming an envelope was corrected.

## Recall Hints
ticket-model, ticket-crud, first-migration, alembic-autogenerate-empty-migration, env-py-must-import-app-models, models-init-import-not-enough, drop_table-leaves-enum-type-behind, sa-Enum-drop-op-get-bind, downgrade-upgrade-roundtrip-proves-enum-drop, values_callable-lowercase-enum-values, native-postgres-enum-ticket_status, no-response-envelope-decision, api-v1-resource-url-shape, exclude_unset-patch-semantics, updated_at-onupdate-verified, pg18-4-port-5433, board-columns-backlog-in_progress-in_review-done, in_review-exists-because-PR-not-push, auto-advance-does-not-violate-drag-gate
