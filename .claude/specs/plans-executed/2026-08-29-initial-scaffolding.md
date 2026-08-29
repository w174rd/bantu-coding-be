---
date: 2026-08-29
title: BE scaffolding — app layout, config, DB session, Alembic
status: done
tags: [scaffolding, structure, config, database, alembic, sqlalchemy]
commits: []
---

# BE scaffolding — app layout, config, DB session, Alembic

## Context

Task 2 of the recommended starting sequence. Task 1 (the agent execution spike) was terminated by the user and its spec deleted; the findings from it that bear on this task are re-recorded under "Established environment facts" below, since they no longer exist anywhere on disk.

`INDEX.md` is empty and `plans-executed/` holds no specs — this is the first spec in the repo. Nothing to link back to.

The repo currently contains only `CLAUDE.md`, `.claude/`, and `.gitignore` at commit `661e226`. No `app/`, no `requirements.txt`, no venv.

**No `/health` endpoint.** The user explicitly rejected it as ceremony. This spec therefore produces a FastAPI app with **no routes at all**, and proves the wiring a different way — see "Verification".

## Goal

A runnable FastAPI application with configuration, a database session, and Alembic wired to PostgreSQL 18 — and nothing else. No endpoints, no models, no schemas, no business logic. The next spec adds the first real feature on top.

## Established environment facts

Verified on this machine, not assumed:

- **Python.** Bare `python` on PATH resolves to a **32-bit Python 3.10.11** — below the 3.12+ `CLAUDE.md` requires. Python **3.12.10** and 3.14.7 are installed. The venv **must** be created with `py -3.12 -m venv .venv`; a plain `python -m venv` silently produces the wrong interpreter.
- **PostgreSQL — the important one.** Three servers are installed and all running:

  | Server | Port |
  |---|---|
  | PostgreSQL 14 | 5434 |
  | PostgreSQL 17 | **5432** (the default) |
  | **PostgreSQL 18** (required by `CLAUDE.md`) | **5433** |

  `DB_PORT=5433`. Anything that assumes the default 5432 connects to **PG17**, not 18, and will appear to work until a version-specific difference bites.
- **`psql` on PATH is 17.2.** A bare `psql` connects to PG17. Use `psql -p 5433` to reach PG18.

## Approach

1. **Virtualenv.** `py -3.12 -m venv .venv`.
2. **`requirements.txt`** — pinned to what actually resolves:
   `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `psycopg[binary]`, `pydantic-settings`, `alembic`, `pytest`.
   Deliberately **not** included: `claude-agent-sdk` (belongs to the agent layer, not scaffolding), `python-dotenv` (see step 4).
3. **Package layout** per `CLAUDE.md` section 5 — `app/{api,core,db,models,schemas,services}/` and `tests/`, each with `__init__.py`. `api`, `models`, `schemas`, and `services` stay empty for now; they exist so the next spec has an obvious place to put things.
4. **`app/core/config.py`** — a `Settings` class on `pydantic-settings`, reading `APP_NAME`, `APP_ENV`, `LOG_LEVEL`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `CORS_ORIGINS`. `DATABASE_URL` is assembled as a computed property from the `DB_*` parts rather than stored as a raw string — this keeps `pydantic-settings` as the only config dependency and avoids `python-dotenv` variable expansion.
5. **`app/db/base.py`** — `Base(DeclarativeBase)`, SQLAlchemy 2.0 style. **`app/db/session.py`** — engine with `pool_pre_ping=True`, `SessionLocal`, and a `get_db` dependency that closes in a `finally`.
6. **`app/main.py`** — the `FastAPI()` instance and `CORSMiddleware` fed from `settings.cors_origins`. **No routers.** Per `CLAUDE.md` section 6.3 item 6 the origins are an explicit allowlist, never `*`; default `http://localhost:5173`.
7. **Alembic.** `alembic init alembic`, then wire `env.py` to read the URL from `Settings` and set `target_metadata = Base.metadata`. **No migration is generated** — there are no models yet.
8. **`.env.example`** — every variable named, no values, with `DB_PORT=5433` and a comment explaining why it is not 5432.
9. **`tests/test_config.py`** — one test asserting `Settings` loads and assembles the expected URL. This is the smallest thing that makes `tests/` real rather than an empty promise.

## Verification

Without endpoints, wiring is proven by:

- `.venv\Scripts\python --version` reports 3.12.x (not 3.10, not 32-bit).
- `uvicorn app.main:app` starts and serves (404 on `/` is the expected, correct result).
- **`alembic current` connects to PG18 and returns cleanly.** This exercises `.env` → `Settings` → assembled URL → engine → a real connection, which is the whole point of the task and does not need a route to demonstrate.
- `pytest` passes.

## Risks / Trade-offs

- **No HTTP-level verification.** A deliberate consequence of dropping `/health`. `alembic current` covers the database path, which is the part that can actually be misconfigured; a FastAPI instance with no routes has very little left to get wrong.
- **No `Ticket` model, deliberately.** The board's columns are still an open decision (`CLAUDE.md` section 0), so modelling a ticket now would mean guessing its states. Alembic is set up but generates its first migration in the next spec.
- **CORS is included before anything calls it.** Cheap, and section 6.3 already dictates its shape, so configuring it now costs nothing and avoids a scramble later.
- **`pytest` and `tests/test_config.py` are the softest part of this scope.** If you would rather decide testing separately, cut step 9 and drop `pytest` from step 2 — nothing else depends on them.
- The server binds to `127.0.0.1` by default and this spec does not change that (section 6.3 item 6).

## Files That Will Change

- `requirements.txt` — new
- `.env.example` — new
- `app/__init__.py`, `app/main.py` — new
- `app/core/__init__.py`, `app/core/config.py` — new
- `app/db/__init__.py`, `app/db/base.py`, `app/db/session.py` — new
- `app/api/__init__.py`, `app/models/__init__.py`, `app/schemas/__init__.py`, `app/services/__init__.py` — new, empty
- `tests/__init__.py`, `tests/test_config.py` — new
- `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/` — new, from `alembic init`
- `.gitignore` — already covers `.venv/`, `.env`, `__pycache__/`, `.pytest_cache/`; no change expected

**Also proposed, small and in scope:** update `CLAUDE.md` section 8 (Build & Run) to record `py -3.12 -m venv .venv` and the PG18 port, since this task is what creates the venv and the `.env`. Without it the next session repeats both mistakes.

## Blocked on (needed from user before execution)

1. **Confirm the target server is PostgreSQL 18 on port 5433** — not PG17 on the default 5432.
2. **Database name, role, and password.** Chosen by the user and **not recorded in this repo** — not here, not in `.env.example`, not in tests. They go only into `.env`, which is gitignored. The database and role must exist on PG18 before `alembic current` can succeed; I will provide the `psql -p 5433` statement shapes rather than creating databases or roles myself.

---

<!-- Filled in when status = in-progress -->
## Progress
- [x] `.venv` created with `py -3.12`, verified 3.12.x 64-bit
- [x] `requirements.txt` written and installed
- [x] `app/` package layout created
- [x] `Settings` loads and assembles `DATABASE_URL`
- [x] `Base`, engine, `SessionLocal`, `get_db` in place
- [x] `app/main.py` with CORS, no routers
- [x] Alembic initialized and wired to `Settings` + `Base.metadata`
- [x] `.env.example` written
- [x] `uvicorn app.main:app` starts
- [ ] `alembic current` connects to PG18 on 5433 — **BLOCKED**: reaches the server and fails at password auth; needs the role + database created
- [x] `pytest` passes

---

<!-- Filled in when status = done / reverted / cancelled -->
## Results & Execution Notes

Built as planned. Every file in "Files That Will Change" was created; nothing was added beyond that list.

**Verified working:** `.venv` on Python 3.12.10 64-bit; `pytest` 3 passed; `uvicorn app.main:app` serves (`/docs` 200, `/` 404 as expected with no routers); `Settings` assembles the URL and the engine builds.

**One verification left open.** `alembic current` reached PostgreSQL 18 on port 5433 and failed with `FATAL: password authentication failed` — not "connection refused". That proves the whole path (`.env` → `Settings` → assembled URL → engine → `alembic/env.py` → a live PG18 server) and leaves only the role and database, which the user creates. Archived as done because the implementation is complete; run `alembic current` once the database exists to close it.

### Deviations and gotchas

- **`alembic/env.py` deliberately does NOT use `config.set_main_option()`.** The URL is read from `Settings` in `_database_url()` and passed straight to `create_engine`. Alembic's config goes through ConfigParser, and a percent-encoded password contains `%`, which ConfigParser would try to interpolate. `alembic.ini`'s `sqlalchemy.url` is intentionally left blank. This would have crashed the first time a password contained `@` or `/`.
- **`DATABASE_URL` percent-encodes the password** via `quote_plus` in `app/core/config.py`, for the same class of reason.
- **`cors_origins` is a plain `str` split on commas**, not a `list[str]`. pydantic-settings tries JSON-parsing complex types from env, which makes a comma-separated list surprising; a string plus `cors_origin_list` is predictable.
- **`python-dotenv` is installed but is not a direct dependency** — it arrived transitively via `pydantic-settings`. Deliberately absent from `requirements.txt`.
- **`/docs` and `/openapi.json` are served publicly.** No auth exists, so the (empty) schema is readable by anything reaching the port. Fine while bound to localhost; revisit when auth lands.
- **PostgreSQL port trap.** Three servers run on this machine: PG14 on 5434, **PG17 on the default 5432**, and **PG18 on 5433**. `CLAUDE.md` requires 18, so anything defaulting to 5432 silently hits PG17. `psql` on PATH is 17.2; use `psql -p 5433` for 18.
- **Python interpreter trap.** Bare `python` is a 32-bit 3.10.11, below the required 3.12+. The venv must be made with `py -3.12`.
- **No real identifiers in the repo.** Mid-task the user required that the database name and role not be published — they are blank in `.env.example`, generic in tests (`testuser`/`testdb`), and absent from this spec. `CLAUDE.md` section 7 gained a rule covering infrastructure identifiers, not just secrets.
- Verified with inline env vars rather than a real `.env`, so no half-filled secrets file was left behind.

## Recall Hints
initial-scaffolding, fastapi-scaffolding, no-health-endpoint-by-user-decision, alembic-env-py-no-set_main_option, configparser-percent-interpolation-password, quote_plus-database-url, cors_origins-str-not-list-pydantic-settings-json-parse, python-dotenv-transitive-not-direct, docs-openapi-public-no-auth, pg18-port-5433-not-5432, pg17-owns-default-5432, psql-on-path-is-17.2, bare-python-32bit-3.10, py-3.12-venv-required, alembic-current-auth-failure-proves-wiring, DeclarativeBase-sqlalchemy-2.0, pool_pre_ping, get_db-finally-close, no-ticket-model-board-columns-undecided, infrastructure-identifiers-not-published, testuser-testdb-generic-fixtures
