---
date: 2026-08-30
title: Projects scope every chat and ticket
status: done
tags: [project, model, migration, api, target-repo, breaking-change]
commits: [ca1c596]
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

- [x] `Project` model + registry
- [x] `project_id` on `Ticket` and `Conversation`
- [x] Migration (delete → create → FKs), `upgrade` and `downgrade` round-trip verified
- [x] Schemas
- [x] `app/api/projects.py` + router registration
- [x] `project_id` validation on the two create routes
- [x] Arbiter inherits the project
- [x] Tests green
- [x] `README.md` and `CLAUDE.md` updated

---

<!-- Filled in when status = done / reverted / cancelled -->
## Results & Execution Notes

Built as planned. `projects` is the container; `tickets.project_id` and `conversations.project_id` are both
NOT NULL with `ON DELETE CASCADE`, so "every chat and ticket belongs to a project" is a database guarantee
rather than a convention. Seven routes in `app/api/projects.py`, registered in `app/main.py`.

### Deviations from the plan

- **`index=True` on both new FK columns.** Not planned. `alembic check` flagged the indexes the migration
  creates as absent from `Base.metadata`, so autogenerate would have emitted a migration dropping them. The
  models now declare what the migration builds.
- **The Arbiter test drives `_record` through a fake session.** The plan said "extend the existing
  assertion", but the invariant worth proving — a ticket takes its project from the conversation record, not
  from the model's JSON — lives in `_record`, not in `parse_verdict`. A 15-line `_FakeSession` (add / flush /
  commit / refresh) makes it testable without a database, keeping the suite DB-free as it has always been.
  Three tests: inheritance, a `project_id` planted in the model output being ignored, and a split verdict
  putting all its cards in one project.
- **No GitHub credential column.** The spec asked the user to settle this at approval; they approved without
  overriding the recommendation, so it stays out. A live `contents:write` token in a table nothing reads is
  exposure with no benefit while the app has no auth, and the column's shape (PAT per project vs. shared vs.
  GitHub App) belongs with the code that consumes it. Recorded in CLAUDE.md section 0 so it does not read as
  an oversight.
- **CLAUDE.md's status block and section 1a were rewritten too**, beyond the planned "core concepts + the
  decision bullet". They were already stale before this task (they claimed the database was unmigrated and
  `git remote -v` empty); this change made them wronger — three migrations became five, eighteen endpoints
  became 26 over 15 paths. Leaving them would have shipped a knowingly false document.

### Verification

- `pytest` — 77 passed, up from 61.
- `alembic upgrade head`, then `downgrade -1` → `upgrade head` again: clean round trip.
- A live `TestClient` run against the real database, since the suite deliberately has no DB coverage:
  create → `201`; duplicate name → `409`; `ssh://` `repo_url` → `422`; ticket with no `project_id` → `422`;
  unknown project → `404`; nested lists return the right rows; deleting the project cascaded the ticket and
  the room to `404`. Test rows removed afterwards.

### What was deleted

8 tickets, 2 conversations, 9 messages, 1 verdict — everything predating projects, on the user's
instruction. That included `#12` and `#13`, the rows the previous spec left open questions about, and the
five hand-split tickets `#14`–`#18`. `personas` (4 rows) and `ai_provider_configs` (1 row) survived.
`downgrade()` does not restore any of it.

### Still open

- **Pre-existing drift, not introduced here:** `alembic check` still reports `ix_tickets_verdict_id`.
  Migration `22b059f01724` created that index but `Ticket.verdict_id` never declared `index=True`, so
  autogenerate wants to drop it. One line in the model fixes it; left alone as out of scope (section 4).
- Whether `GET /tickets` and `GET /conversations` should survive as unfiltered all-project views. Kept for
  now; the user was asked and did not object.
- Moving a ticket between projects. `TicketUpdate` deliberately has no `project_id`, and a test asserts it.

---

## FE Handoff — `bantu-coding-fe`

**This is a breaking API change.** The FE has no project concept; until it has one, creating a ticket or a
conversation fails with `422`. Recorded here per CLAUDE.md section 10.

### What changed

| Endpoint | Change |
|---|---|
| `POST /api/v1/tickets` | `project_id: number` now **required** in the body. Unknown id → `404`. |
| `POST /api/v1/conversations` | Same. |
| `GET /api/v1/tickets` | Unchanged, but now returns tickets across **all** projects. |
| `GET /api/v1/conversations` | Same. |
| `TicketRead` / `ConversationRead` | Both gained `project_id: number`. |

New endpoints:

```
GET    /api/v1/projects                    -> Project[]
POST   /api/v1/projects                    -> Project        (409 on duplicate name)
GET    /api/v1/projects/{id}               -> Project
PATCH  /api/v1/projects/{id}               -> Project
DELETE /api/v1/projects/{id}               -> 204            (cascades: rooms and board go too)
GET    /api/v1/projects/{id}/tickets       -> Ticket[]
GET    /api/v1/projects/{id}/conversations -> Conversation[]
```

### The type

```ts
export type Project = {
  id: number
  name: string
  description: string | null
  repo_url: string | null       // https:// only -- the API rejects anything else with 422
  default_branch: string | null // the PR base, never a push target
  created_at: string
  updated_at: string
}

export type ProjectCreate = {
  name: string
  description?: string | null
  repo_url?: string | null
  default_branch?: string | null
}

export type ProjectUpdate = Partial<ProjectCreate>
```

### Files to touch

- `src/types/api.ts` — add `Project`, `ProjectCreate`, `ProjectUpdate`; add `project_id: number` to `Ticket`
  and `Conversation`; add `project_id: number` to `TicketCreate`. Leave `TicketUpdate` alone — the backend
  rejects a project change there by design.
- `src/api/projects.ts` — **new**, mirroring `src/api/tickets.ts`.
- `src/api/tickets.ts` — `listTickets()` should take a project id and call
  `/api/v1/projects/{id}/tickets`; `createTicket` sends `project_id`.
- `src/api/conversations.ts` — `listConversations()` likewise; `createConversation(projectId, title)`.
- `src/state/TicketsContext.tsx`, `src/state/ConversationContext.tsx` — both need the active project. A
  `ProjectContext` above them is the obvious shape: nothing below it can load without a project id.
- `src/routes/Board.tsx`, `src/routes/Chat.tsx` — need a project selected before they can render anything.
- `src/components/NewTicketForm.tsx` — pass the active project.
- A project picker, and a first-run "name your project" screen. With the database emptied there are now
  **zero** projects, so an empty state that can create the first one is not optional — without it the app
  has no reachable path to any content.

### Two behaviours worth designing for

- `409` on a duplicate project name. Show it on the name field; do not swallow it.
- `DELETE /projects/{id}` destroys the project's whole board and every room, immediately, with no
  confirmation server-side. `ConfirmDeleteDialog` already exists — this is a case that warrants naming what
  is about to be lost.

## Recall Hints

projects, project-model, project-container, projects-scope-chats-and-tickets, project_id-not-null,
cascade-delete-project, tickets-project_id, conversations-project_id, unique-project-name, 409-duplicate-name,
repo_url-https-only, urlparse-scheme-check, typed-column-not-prose-6.4, default_branch-is-pr-base,
no-credential-column-yet, credential-deferred-to-agent-spec, target-repo-record-lives-on-projects,
settled-open-decision, migration-db5519dc8798, migration-deletes-data, delete-before-not-null,
child-first-delete-order, downgrade-does-not-restore, alembic-check-index-drift, index-true-on-fk-columns,
ix_tickets_verdict_id-preexisting-drift, nested-list-routes, projects-id-tickets, projects-id-conversations,
arbiter-inherits-conversation-project, _FakeSession-record-test, db-free-suite-still, TicketUpdate-no-project_id,
no-ticket-reassignment, fe-breaking-change, fe-project-picker-required, fe-empty-database-after-migration,
claude-md-status-block-rewritten, remote-exists-now, 26-endpoints-15-paths
