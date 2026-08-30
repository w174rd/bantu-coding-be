---
date: 2026-08-30
title: A ticket can point at another ticket
status: draft
tags: [ticket, relation, enum, migration, arbiter, fe-contract]
commits: []
---

# A ticket can point at another ticket

## Context

User request: *"for ticket. add a field that can relation with another tickets. it's usefull for feedback or
issue based on ones ticket."*

Work produces work. A ticket gets built, the user tries it, and what comes back is a bug report or a piece of
feedback that only makes sense next to the ticket it came from. Today the board has no way to say that —
`#19` and `#12` are two unrelated cards, and the connection lives only in someone's memory.

Three decisions taken by the user before this spec was written:

1. **One link plus a kind**, not a links table. A ticket points at one other ticket and says why.
2. **Same project only.** A link whose target lives in another project is rejected.
3. **The Arbiter may link the tickets it splits** — see "The Arbiter's new field", which is the part of this
   spec that needs the most care.

Grepped INDEX.md: nothing covers ticket-to-ticket links. Related:

- [`2026-08-30-projects-scope-chats-and-tickets`](../plans-executed/2026-08-30-projects-scope-chats-and-tickets.md)
  — `project_id` is what "same project only" is checked against, and its cascade is why a deleted project
  takes both ends of a link with it.
- [`2026-08-30-arbiter-splits-complex-work`](../plans-executed/2026-08-30-arbiter-splits-complex-work.md) —
  the Arbiter already writes several tickets in dependency order, expressed only as ascending ids. This spec
  makes that order explicit, and re-opens the question that spec settled about what model output may write.
- [`2026-08-29-ticket-model-and-crud`](../plans-executed/2026-08-29-ticket-model-and-crud.md) — the native
  enum + `values_callable` pattern the new enum follows.

## Goal

A ticket can record that it is feedback on, an issue in, a follow-up to, or a dependant of exactly one other
ticket in the same project — set through the API by the user, and by the Arbiter for the tickets it splits.

## Approach

### 1. The enum — `app/core/enums.py`

```python
class TicketRelation(str, Enum):
    FEEDBACK = "feedback"      # a reaction to the work: it does the job, but...
    ISSUE = "issue"            # something is wrong with the work
    FOLLOW_UP = "follow_up"    # work that comes after, optional
    DEPENDS_ON = "depends_on"  # cannot start until the other is done
```

A native Postgres enum, like `TicketStatus` and `PersonaRole`, so a fifth kind is a migration and a product
decision. `relates_to` is deliberately absent: it is the value people pick when they cannot decide, and it
carries no information the link itself does not already carry.

`FOLLOW_UP` is the one I would cut if you want this narrower — `FEEDBACK` and `ISSUE` are what you asked for,
`DEPENDS_ON` is what the Arbiter needs. Say so at approval and it goes.

### 2. The columns — `app/models/ticket.py`

```
tickets
  related_ticket_id  int  NULL  FK -> tickets.id  ON DELETE SET NULL, indexed
  relation_kind      enum NULL  ticket_relation
```

Both nullable, and set together — a ticket with no relation has both null. The pairing is enforced in the
schema and in the delete route (below), **not** by a database CHECK constraint: `ON DELETE SET NULL` nulls
the id without touching the kind, so a CHECK requiring them to agree would make deleting a linked-to ticket
fail at the constraint. Recorded here because it looks like an oversight otherwise.

`ON DELETE SET NULL` follows `verdict_id`'s precedent: losing the thing that was linked to must not delete
the work that pointed at it. Feedback on a deleted ticket survives as an ordinary card.

The self-referential relationship needs `remote_side` on the SQLAlchemy side; `related_ticket` is the target,
and no back-reference collection is added — nothing needs "everything pointing at me" yet, and a lazy
collection on every ticket read is not free.

### 3. Validation

Written through `POST /api/v1/tickets` and `PATCH /api/v1/tickets/{id}`:

| Rule | Response |
|---|---|
| `related_ticket_id` and `relation_kind` must be set together | `422` |
| Target must exist | `404` |
| Target must be in the same project as the ticket | `422` |
| A ticket may not point at itself | `422` |

`PATCH` keeps `exclude_unset`: sending `{"related_ticket_id": null, "relation_kind": null}` clears the link;
omitting them leaves it alone. Clearing one but not the other is the `422` above.

**No cycle detection beyond self-reference.** `A → B → A` is possible through two separate writes. The graph
is display-only — nothing traverses it — so a two-cycle costs a confusing card, not a hang. If the FE ever
walks the chain, that is when this needs revisiting, and it says so here.

### 4. Deleting a ticket — `app/api/tickets.py`

Before deleting, clear both columns on every ticket pointing at it:

```
UPDATE tickets SET related_ticket_id = NULL, relation_kind = NULL WHERE related_ticket_id = <id>
```

The FK's `ON DELETE SET NULL` is the backstop for any other path (a project cascade, a direct SQL delete);
this statement is what stops a dangling `relation_kind` sitting on a row whose id was nulled underneath it.

### 5. The Arbiter's new field — the part to read carefully

`ArbiterTicket` gains **`depends_on: int | None`** — an **index into the verdict's own ticket list**, not a
ticket id.

```json
{"tickets": [
  {"title": "Add the job queue table",  "body": "..."},
  {"title": "Wire the worker to it",    "body": "...", "depends_on": 0}
]}
```

This is the whole safety argument, and it is why the field is an index:

- **The model can never name an arbitrary ticket.** A `ticket_id` field would let one line of model output
  attach itself to any row in the database. An index can only reach tickets **this same verdict just
  created**, in this same conversation, in this same project. The blast radius of a confused or injected
  Arbiter is confined to rows it was already authorised to write.
- **It is validated before it is used** (CLAUDE.md section 6.4: model output is data, never a command).
  `ArbiterVerdict` rejects a `depends_on` that is out of range, equal to its own index, or **not strictly
  less than its own index**. That last rule kills cycles by construction: dependencies must appear earlier in
  the list, which is the order the Arbiter is already instructed to write in.
- **It writes one enum value only — `DEPENDS_ON`.** The Arbiter cannot mark something as `FEEDBACK` or
  `ISSUE`; those are judgements about work that exists, and they stay the user's to make.
- **What this does not touch:** `ArbiterTicket` still has no `status` field, every ticket is still hardcoded
  to `BACKLOG`, and it still cannot choose a project. The drag gate is untouched. This adds an edge between
  two Backlog cards; it does not add authority.

In `app/services/arbiter.py`, `_record` writes the tickets, `db.flush()`es to get their ids, then a second
pass maps index → id and sets `related_ticket_id` / `relation_kind`. The prompt gains a sentence describing
the field; without it the model has no idea the field exists.

### 6. Schemas — `app/schemas/ticket.py`

`TicketCreate` and `TicketUpdate` gain both fields; `TicketRead` exposes both. A model validator enforces the
set-together rule in one place rather than in each route.

### 7. Migration

One revision on top of `db5519dc8798`: create the `ticket_relation` type, add both columns (nullable, so no
backfill), the FK with `ON DELETE SET NULL`, and the index. `downgrade()` drops the columns and the type —
and must drop the type explicitly with `op.get_bind()`, the gotcha recorded in the tickets spec: dropping a
column does not drop the enum type behind it.

### 8. Tests

- `tests/test_ticket_schemas.py` — set-together validation both ways; clearing via explicit nulls;
  `relation_kind` rejects a value outside the enum.
- `tests/test_arbiter_verdict.py` — `depends_on` out of range, pointing at itself, and pointing forward are
  all rejected; a valid one resolves to the right ticket through `_record` and the existing `_FakeSession`;
  a verdict with no `depends_on` still writes unlinked tickets.
- The same-project and target-exists rules are route-level (they need a database) and are checked in the live
  smoke run, as the project rules were.

### 9. Documentation

- `README.md` — §1 (the relation and what it is for), §3 (migration chain), §5 (the changed ticket bodies).
- The FE contract change is recorded in the FE Handoff section below.

## Risks / Trade-offs

- **The Arbiter now writes a foreign key on its own say-so.** Bounded by index-validation to rows from the
  same verdict, but it is a real widening of what model output produces, and it belongs in the record as one.
- **A dangling `relation_kind` is possible** through paths that bypass the delete route (raw SQL). Harmless
  for display; noted so it is not mistaken for corruption.
- **Two-cycles are possible** and undetected. Display-only, as argued above.
- **Breaking-ish for the FE:** additive only — both fields are nullable and no existing request body changes.
  The FE keeps working untouched; it just cannot show or set a relation until it adds the fields.
- A fifth relation kind later is a migration, by design.

## Files That Will Change

- `app/core/enums.py` — `TicketRelation`.
- `app/models/ticket.py` — both columns, the self-referential relationship.
- `app/schemas/ticket.py` — both fields on create/update/read, the set-together validator.
- `app/schemas/verdict.py` — `ArbiterTicket.depends_on` and its validation.
- `app/services/arbiter.py` — resolve indices to ids after flush; prompt gains the field.
- `app/api/tickets.py` — target exists / same project / not self; clear referencing rows before delete.
- `alembic/versions/<rev>_add_ticket_relations.py` — new.
- `tests/test_ticket_schemas.py`, `tests/test_arbiter_verdict.py`.
- `README.md` — §1, §3, §5.

---

## FE Handoff — `bantu-coding-fe`

**Additive.** Nothing the FE sends today stops working; both fields are nullable.

`Ticket` gains:

```ts
related_ticket_id: number | null
relation_kind: 'feedback' | 'issue' | 'follow_up' | 'depends_on' | null
```

`TicketCreate` and `TicketUpdate` accept both. They must be sent together or not at all (`422` otherwise),
the target must exist (`404`), and it must be in the same project (`422`).

Worth showing on the card: `↳ issue on #12`. Worth knowing: a ticket the Arbiter split may arrive already
linked with `depends_on`, so the board shows dependency order rather than leaving it implicit in the ids.

This lands after `2026-08-30-projects-in-the-fe.md`, which is still a draft in that repo.

---

<!-- Filled in when status = in-progress -->
## Progress

- [ ] `TicketRelation` enum
- [ ] Columns + self-referential relationship
- [ ] Schemas and the set-together validator
- [ ] Route validation (exists / same project / not self) and the pre-delete clear
- [ ] `ArbiterTicket.depends_on`, its index validation, and resolution after flush
- [ ] Arbiter prompt describes the field
- [ ] Migration, `upgrade`/`downgrade` round trip (including the enum type drop)
- [ ] Tests green
- [ ] Live smoke run of the route-level rules
- [ ] `README.md`

---

<!-- Filled in when status = done / reverted / cancelled -->
## Results & Execution Notes

## Recall Hints
