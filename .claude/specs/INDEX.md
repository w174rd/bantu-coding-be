# Specs Index

Central index of every executed spec, grouped by feature area.

> **For Claude:** Read this file at the start of every session. Grep it before writing a new spec.
> **Updating:** Add a new entry when the user asks to commit (at the same time as archiving the spec into `plans-executed/`).

Entry format:
```
- `YYYY-MM-DD` [**slug**](plans-executed/...) — Title | hints: keyword1, keyword2, ...
```

---

## (empty)

No specs have been executed yet. This repo was just initialized — see `CLAUDE.md` section 0 for project status.

When the first spec is archived, create a section for its feature area. The areas expected to appear, following the product flow:

- **Project Setup & Structure** — scaffolding, requirements, gitignore, env, alembic init
- **FastAPI Foundation** — health endpoint, config, DB connection, response envelope
- **Multi-Persona Chat** — personas, conversations, messages
- **Tickets & Board** — backlog, columns, drag-to-progress
- **Agent Execution** — Claude Agent SDK, job lifecycle, progress streaming
- **Git & GitHub Integration** — cloning target repos, auto commit, auto push, credentials

Do not create empty sections up front — add one when its first entry exists.

---

Specs in flight (written but not yet approved/executed) live in `.claude/specs/plans/` — check that folder directly, not this index.
