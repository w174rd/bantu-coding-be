---
date: 2026-08-30
title: Projects scope every chat and ticket
status: in-progress
tags: [project, model, migration, api, target-repo, breaking-change]
commits: []
---

# Projects scope every chat and ticket

## Context

User request: *"before group chat and ticket, user must input project name. the chat and ticket are
related with project."*

Today a `Conversation` and a `Ticket` float free — nothing groups them, and nothing says which body of work
either belongs to. This adds the missing top-level container: a **Project**. A project is created first;
every discussion room and every ticket then belongs to exactly one.

Three decisions were taken by the user before this spec was written:

1. **A project carries the target repo, not just a name.** This settles an item CLAUDE.md section 0 lists
   under *Decisions NOT yet made* — "how target repos get registered and cloned … where the record lives is
   not [settled]". It now lives on `projects`. Section 6.5 requires that to be its own spec with the user's
   approval; this is that spec.
2. **Existing rows are deleted, not backfilled.** The 8 tickets, 2 conversations, 9 messages and 1 verdict
   currently in the local database are test data from earlier specs and are not worth carrying.
3. **Nested list routes.** `GET /api/v1/projects/{id}/tickets` and `.../conversations`; single-resource
   routes stay flat.

Related specs (grepped from INDEX.md — no earlier spec covers projects):

- [`2026-08-29-ticket-model-and-crud`](../plans-executed/2026-08-29-ticket-model-and-crud.md) — the
  `Ticket` model, the no-envelope API conventions, and the native-enum + `values_callable` migration
  pattern this migration follows.
- [`2026-08-29-discussion-room-data-layer`](../plans-executed/2026-08-29-discussion-room-data-layer.md) —
  the `Conversation` model, the cascade-delete rule for messages, and the Fernet-encrypted `api_key`
  pattern on `ai_provider_configs` that the repo credential question below refers to.
- [`2026-08-30-arbiter-splits-complex-work`](../plans-executed/2026-08-30-arbiter-splits-complex-work.md) —
  the Arbiter writes tickets in `app/services/arbiter.py`; those tickets must now inherit a project.

## Goal

A `Project` is the entry point of the product: the user names one before anything else exists. Every
conversation and every ticket carries a non-null `project_id`, enforced by the database, and a project
records which GitHub repo its agent runs will eventually target.

## Approach

### 1. The model — `app/models/project.py`

```
projects
  id             int      PK
  name           str(200) NOT NULL, UNIQUE
  description    text     NULL
  repo_url       str(500) NULL
  default_branch str(100) NULL
  created_at / updated_at
```

- `name` is **unique**: two projects with the same name are indistinguishable on a board, and the
  constraint is cheaper than the confusion.
- `repo_url` and `default_branch` are **nullable**. A project is created from a name alone (that is the
  request); the repo is filled in later, before it can ever be executed against. The agent-run spec is
  what makes them required at the point of use — not this schema.
- `default_branch` is the **PR base**, never a push target. Section 6.3 item 3 stands: a run pushes to its
  own branch and opens a PR against this.
- Registered in `app/models/__init__.py` — autogenerate omits any model not imported there.

**Open sub-decision, for you to settle at approval — the GitHub credential.**
The option you picked previewed a `credential_ref`. My recommendation is to **leave it out of this spec**
and add it in the agent-execution spec, because:

- Nothing reads it yet. A live `contents:write` PAT sitting in a table that no code consumes is exposure
  with no benefit — and this app still has no auth (section 6.3 item 6).
- Section 6.3 item 2 wants a credential *scoped to the target repos*. Whether that is one fine-grained PAT
  per project, one shared across projects, or a GitHub App installation changes the column shape, and that
  choice belongs with the code that uses it.
- The pattern is already proven when we do want it: Fernet-encrypted at rest via `app/core/security.py`,
  never returned by a read schema — exactly how `ai_provider_configs.api_key` works.

Say the word and I will add `github_token` (encrypted, nullable, never in `ProjectRead`) to this spec
before execution.

### 2. Foreign keys on the two existing tables

- `app/models/ticket.py` — `project_id: Mapped[int]`, `ForeignKey("projects.id", ondelete="CASCADE")`,
  NOT NULL, plus a `project` relationship. `verdict_id` is untouched.
- `app/models/conversation.py` — the same.
- **CASCADE on both**: deleting a project deletes its rooms and its board. `messages` and `verdicts`
  already cascade from `conversations`, so the chain holds. This is destructive and deliberate — a project
  is the container; deleting it and leaving its tickets behind would orphan them under a NOT NULL column.
  Flagged under Risks.

### 3. The migration

One revision on top of `22b059f01724`:

```
upgrade():
    DELETE FROM messages
    DELETE FROM verdict_options / verdicts
    DELETE FROM tickets
    DELETE FROM conversations
    CREATE TABLE projects
    ADD COLUMN tickets.project_id       -> FK, NOT NULL, ON DELETE CASCADE
    ADD COLUMN conversations.project_id -> FK, NOT NULL, ON DELETE CASCADE
```

The deletes come **first** so the NOT NULL columns can be added directly, with no nullable-then-alter
dance. `personas` and `ai_provider_configs` are untouched — the cast and the active provider config
survive.

`downgrade()` drops the two columns and the table. It does **not** restore the deleted rows; that is
recorded here rather than pretended away.

### 4. Schemas

- `app/schemas/project.py` — `ProjectCreate` (name required, min 1 / max 200; description, repo_url,
  default_branch optional), `ProjectUpdate` (all optional, `exclude_unset` semantics), `ProjectRead`.
- `repo_url` is validated as an **`https://` URL** on the way in. Not cosmetic: section 6.4 requires the
  repo to come from a typed column, and a column that accepts `file:///…` or an `ssh://` host is not the
  typed guarantee it looks like. Rejecting anything else at the schema is where that guarantee is made.
- `TicketCreate` gains a required `project_id`; `TicketRead` and `ConversationRead` expose it.
  `ConversationCreate` gains a required `project_id`.
- `TicketUpdate` does **not** get `project_id` — moving a ticket between projects is a different feature
  and is not being asked for.

### 5. Routes — `app/api/projects.py`

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/projects` | list, ordered by id |
| `POST` | `/api/v1/projects` | `201`; duplicate name → `409` |
| `GET` | `/api/v1/projects/{id}` | `404` if missing |
| `PATCH` | `/api/v1/projects/{id}` | `exclude_unset` |
| `DELETE` | `/api/v1/projects/{id}` | `204`; cascades |
| `GET` | `/api/v1/projects/{id}/tickets` | the project's board |
| `GET` | `/api/v1/projects/{id}/conversations` | the project's rooms |

Registered in `app/main.py`. Existing routes change as follows:

- `GET /api/v1/tickets` and `GET /api/v1/conversations` — **kept**, unfiltered, as the all-projects view.
  (Say if you would rather they be removed; nested lists cover the product flow on their own.)
- `POST /api/v1/tickets` and `POST /api/v1/conversations` — now require `project_id` in the body, and
  `404` if that project does not exist.
- Everything else is unchanged.

### 6. The Arbiter

`app/services/arbiter.py` writes tickets from a verdict. Each one takes `project_id` **from its
conversation's record** — `conversation.project_id`, a typed column — never from the model's output.
Section 6.4: model output is data, not a target selector. `ArbiterTicket` gains no new field, exactly as it
gained no status field.

### 7. Tests

- `tests/test_project_schemas.py` — name required and length-bounded; `repo_url` rejects non-https and
  accepts a plain https URL; `ProjectUpdate` round-trips `exclude_unset`.
- `tests/test_ticket_schemas.py` — `TicketCreate` now requires `project_id`; `TicketUpdate` still refuses
  to carry one.
- `tests/test_arbiter_verdict.py` — extend the existing assertion: tickets from a verdict land in
  `BACKLOG` **and** inherit the conversation's project.

Tests stay pure-Python, no database, as the suite already is.

### 8. Documentation

- `README.md` — §1 (Project added to core concepts), §3 (migration chain), §5 (the new tables and the
  changed create bodies), §9 (status). Required by CLAUDE.md section 11.
- `CLAUDE.md` — add **Project** to the core-concepts table in section 0, and rewrite the
  "How target repos get registered and cloned" bullet under *Decisions NOT yet made*: the record now lives
  on `projects`; what stays open is the credential and the clone mechanism.

## Risks / Trade-offs

- **Data loss is the point, and it is irreversible.** 8 tickets, 2 conversations, 9 messages, 1 verdict go.
  `downgrade()` will not bring them back. Confirm you have nothing there you want.
- **Breaking API change for `bantu-coding-fe`.** `POST /tickets` and `POST /conversations` will `422`
  without a `project_id`. The FE has no project concept and no project picker yet; its chat UI is still a
  placeholder, so the blast radius is the board. Recorded here so the FE session can follow
  (CLAUDE.md section 10).
- **Deleting a project deletes its board and its rooms.** No soft delete, no confirmation at the API — the
  `204` is immediate.
- **This settles an architectural decision** (section 6.5). Once `projects.repo_url` exists, "where does
  the target repo record live" is answered, and un-answering it later means another migration.
- A unique `name` means the FE must handle `409` on create.

## Files That Will Change

- `app/models/project.py` — **new**. The `Project` model.
- `app/models/__init__.py` — import and export `Project`.
- `app/models/ticket.py` — `project_id` FK, NOT NULL, cascade; `project` relationship.
- `app/models/conversation.py` — same.
- `app/schemas/project.py` — **new**. Create / Update / Read, with https validation on `repo_url`.
- `app/schemas/ticket.py` — `project_id` required on create, exposed on read.
- `app/schemas/conversation.py` — same.
- `app/api/projects.py` — **new**. Seven routes.
- `app/api/tickets.py` — validate `project_id` on create (`404` if unknown).
- `app/api/conversations.py` — same.
- `app/main.py` — register the projects router.
- `app/services/arbiter.py` — tickets inherit `conversation.project_id`.
- `alembic/versions/<rev>_add_projects.py` — **new**. Delete, create, two FK columns.
- `tests/test_project_schemas.py` — **new**.
- `tests/test_ticket_schemas.py` — updated for the required `project_id`.
- `tests/test_arbiter_verdict.py` — assert the inherited project.
- `README.md` — §1, §3, §5, §9.
- `CLAUDE.md` — section 0 core concepts and the target-repo decision bullet.

---

<!-- Filled in when status = in-progress -->
## Progress

- [ ] `Project` model + registry
- [ ] `project_id` on `Ticket` and `Conversation`
- [ ] Migration (delete → create → FKs), `upgrade` and `downgrade` round-trip verified
- [ ] Schemas
- [ ] `app/api/projects.py` + router registration
- [ ] `project_id` validation on the two create routes
- [ ] Arbiter inherits the project
- [ ] Tests green
- [ ] `README.md` and `CLAUDE.md` updated

---

<!-- Filled in when status = done / reverted / cancelled -->
## Results & Execution Notes

## Recall Hints
