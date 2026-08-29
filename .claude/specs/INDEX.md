# Specs Index

Central index of every executed spec, grouped by feature area.

> **For Claude:** Read this file at the start of every session. Grep it before writing a new spec.
> **Updating:** Add a new entry when the user asks to commit (at the same time as archiving the spec into `plans-executed/`).

Entry format:
```
- `YYYY-MM-DD` [**slug**](plans-executed/...) — Title | hints: keyword1, keyword2, ...
```

---

## Project Setup & Structure
> grep keywords: scaffolding, structure, venv, requirements, alembic, config, session, database, port, python-version, identifiers

- `2026-08-29` [**initial-scaffolding**](plans-executed/2026-08-29-initial-scaffolding.md) — BE scaffolding: `app/` layout, Pydantic Settings, SQLAlchemy session, Alembic wiring. No endpoints — `/health` rejected by user as ceremony | hints: initial-scaffolding, fastapi-scaffolding, no-health-endpoint-by-user-decision, alembic-env-py-no-set_main_option, configparser-percent-interpolation-password, quote_plus-database-url, cors_origins-str-not-list-pydantic-settings-json-parse, python-dotenv-transitive-not-direct, docs-openapi-public-no-auth, pg18-port-5433-not-5432, pg17-owns-default-5432, psql-on-path-is-17.2, bare-python-32bit-3.10, py-3.12-venv-required, alembic-current-auth-failure-proves-wiring, DeclarativeBase-sqlalchemy-2.0, pool_pre_ping, no-ticket-model-board-columns-undecided, infrastructure-identifiers-not-published, testuser-testdb-generic-fixtures

---

Areas expected as the product grows — create each section when its first entry exists:

- **FastAPI Foundation** — first real endpoint, response envelope
- **Multi-Persona Chat** — personas, conversations, messages
- **Tickets & Board** — backlog, columns, drag-to-progress
- **Agent Execution** — Claude Agent SDK, job lifecycle, progress streaming
- **Git & GitHub Integration** — cloning target repos, auto commit, PR flow, credentials

Specs in flight (written but not yet approved/executed) live in `.claude/specs/plans/` — check that folder directly, not this index.
