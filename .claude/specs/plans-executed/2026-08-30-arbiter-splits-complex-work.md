---
date: 2026-08-30
title: The Arbiter splits complex work into several tickets
status: done
tags: [arbiter, verdict, ticket, split, migration, schema, fe-contract]
commits: []
---

# The Arbiter splits complex work into several tickets

## Context

The first real discussion produced verdict `#1` and ticket `#12` — a 2026-character plan covering five
separable jobs (engine, input presets, visual customisation, logo safety, performance and export). It was split
into `#14`–`#18` **by hand, through the API**. The code learned nothing from that: run another round and you get
one long ticket again.

Grepped `INDEX.md` for `arbiter|verdict|ticket|split`: one prior spec,
[discussion-round-and-verdict](../plans-executed/2026-08-29-discussion-round-and-verdict.md). This changes the
schema it introduced, so read its Results first — particularly the note that `ArbiterTicket` deliberately has no
`status` field.

### The user's decision

The **Arbiter decides the split automatically**. The safety net is that the board already has add and edit, so a
bad split is correctable by hand rather than something the model has to get perfect.

### What is singular today

- `ArbiterVerdict.ticket: ArbiterTicket` — one object.
- `app/services/arbiter.py:86` builds exactly one `Ticket`.
- `verdicts.ticket_id` — a single nullable FK.
- The prompt: *"The ticket describes the winning option."*

## Goal

One verdict can produce several tickets, ordered so that earlier ones unblock later ones, each self-contained
and each landing in Backlog. A genuinely single job still produces exactly one ticket.

## Approach

### 1. The relationship inverts

One verdict now has many tickets, so the foreign key moves to the side that is now the "many":

- **Add `tickets.verdict_id`** — nullable FK to `verdicts.id`, `ON DELETE SET NULL`. Nullable because tickets
  created by hand (the board's own New Ticket button) have no verdict, and that is the normal case.
- **Drop `verdicts.ticket_id`.**
- **The migration must carry the existing link across before dropping it.** There is one live row —
  verdict `1` → ticket `12` — and a naive `drop_column` would silently discard it. `UPDATE tickets SET
  verdict_id = v.id FROM verdicts v WHERE tickets.id = v.ticket_id` runs first.
- `downgrade` re-adds `verdicts.ticket_id` and copies back the *first* ticket per verdict, which is lossy by
  nature — a verdict that produced five tickets cannot round-trip into a single-FK column. Say so in the
  migration docstring rather than pretending it is reversible.

No new enum type, so neither of the previous enum traps applies.

### 2. The schema gate widens, but does not weaken

`ArbiterVerdict.tickets: list[ArbiterTicket]` with `min_length=1, max_length=8`.

The cap is the point. Without it a confused model can emit forty tickets and flood the board in one write, and
every one of them is a row this code creates on the model's say-so. Eight is enough for any plan a four-persona
discussion produces, and a verdict exceeding it is rejected as malformed like any other validation failure.

**`ArbiterTicket` still has no `status` field.** That is unchanged and non-negotiable — splitting multiplies the
cards, never the authority. Every ticket is written with `TicketStatus.BACKLOG` hardcoded, and the existing test
asserting a `status: "in_progress"` in the model's JSON cannot reach the database stays exactly as it is.

Ordering comes from list order: tickets are created in sequence, so their ids ascend in dependency order and the
board reads correctly with no extra column.

### 3. The prompt has to define *when* to split

"Split if complex" is too vague to act on and produces arbitrary fragmentation. The instruction becomes
concrete:

- One ticket per **independently shippable** step — something a developer could pick up and finish on its own.
- If the work is genuinely one job, return **one** ticket. Splitting a small task is as wrong as not splitting a
  large one.
- Order them so anything a ticket depends on comes earlier in the list.
- Each ticket carries its own `## Context`, `## Goal`, `## Approach`, `## Risks / Trade-offs`, and **names what
  it depends on** — a card that cannot be read alone is not a split, it is a fragment.
- Keep the constraint with the work it constrains, not summarised into a separate "risks" ticket.

The hand-split `#14`–`#18` are the worked example this wording is derived from.

### 4. Everything downstream of one ticket

- `_record` loops, creating each ticket and attaching `verdict_id`.
- The Arbiter's spoken message lists what it created instead of naming one ticket.
- `VerdictRead` gains **`ticket_ids: list[int]`** in place of `ticket_id`, derived from the relationship so the
  FE gets one array rather than having to join client-side.
- `TicketRead` gains `verdict_id: int | null`, so a card can show where it came from.

### 5. The FE breaks, and it is already written

`../bantu-coding-fe/src/components/VerdictCard.tsx:38` reads `verdict.ticket_id` and renders "Ticket #N was
created from this verdict". That code exists and is **uncommitted** in the FE working tree. This change makes
that field disappear, so the card must move to `ticket_ids` and render a list.

That FE work was built from a spec I wrote but did not execute, so I have not reviewed it. Updating it is in
scope here only as far as the contract change requires — `VerdictCard.tsx` and `types/api.ts`. Anything else in
that tree stays untouched.

## Verification

- `FakeProvider`-free, as before: `parse_verdict` is pure and takes the JSON directly.
  - A verdict with three tickets parses and keeps their order.
  - A verdict with one ticket still parses — the common case must not regress.
  - Zero tickets is rejected; nine tickets is rejected.
  - A `status: "in_progress"` inside a ticket object still cannot reach the database.
- Migration: `upgrade` then check verdict `1` still resolves to ticket `12` through the new column;
  `downgrade` then `upgrade` round-trips.
- Against the running app: a real round on a deliberately multi-part problem produces several Backlog tickets,
  and `GET /api/v1/conversations/{id}/verdicts` returns their ids.
- A deliberately simple problem produces exactly one ticket.
- `pytest` green.

## Risks / Trade-offs

- **The model decides how work is divided.** A bad split is now written straight to the board. The mitigation is
  the user's — add and edit already exist — and that is the trade the user accepted. It is worth stating plainly
  rather than burying: this widens what model output writes into the database.
- **The cap is arbitrary.** Eight is a judgement, not a measurement. Too low truncates a genuinely large plan
  into a rejected verdict; too high lets a confused model flood the board.
- **The downgrade is lossy** and cannot be otherwise. A multi-ticket verdict has no single-FK representation.
- **Splitting costs nothing extra per round** — it is the same one Arbiter call, producing a longer JSON. But a
  longer required output makes malformed JSON more likely, and the Arbiter is already the most failure-prone
  part of the round.
- **Ordering by id is implicit.** It works because tickets are inserted in list order, and it will keep working
  as long as nobody reorders that loop. An explicit `position` column would be sturdier; it is not added because
  nothing yet reads an order other than the board's own.
- The existing verdict `#1` and its ticket `#12` are live data in your database, not fixtures. The data
  migration is the only thing standing between them and a broken link.

## Deliberately out of scope

- A "split this ticket" action for hand-written tickets — the user chose the automatic route.
- Dependency edges as data (a real graph between tickets). The dependency lives in the body text, as it does in
  the hand-split example.
- Any change to the drag gate, ticket execution, or agent runs.

## Files That Will Change

- `app/schemas/verdict.py` — `tickets: list[ArbiterTicket]`, `VerdictRead.ticket_ids`
- `app/schemas/ticket.py` — `TicketRead.verdict_id`
- `app/services/arbiter.py` — the prompt, the loop in `_record`, the spoken message
- `app/models/verdict.py` — drop `ticket_id`, add the `tickets` relationship
- `app/models/ticket.py` — `verdict_id`
- `alembic/versions/<hash>_verdict_can_have_many_tickets.py` — new, with the data migration
- `tests/test_arbiter_verdict.py` — multi-ticket cases, the cap, single-ticket regression
- `CLAUDE.md` — the Arbiter section: one verdict, many tickets, still all Backlog
- `../bantu-coding-fe/src/types/api.ts`, `src/components/VerdictCard.tsx` — `ticket_ids`
- `../bantu-coding-fe/CLAUDE.md` — the changed verdict shape

---

## Progress

- [x] `app/models/verdict.py` — `ticket_id` dropped, `tickets` relationship, `ticket_ids` property
- [x] `app/models/ticket.py` — `verdict_id` FK, `verdict` relationship
- [x] `app/schemas/verdict.py` — `tickets: list[...]` capped at 8, `VerdictRead.ticket_ids`
- [x] `app/schemas/ticket.py` — `TicketRead.verdict_id`
- [x] `app/services/arbiter.py` — split instruction in the prompt, write loop, spoken message lists them
- [x] Migration `22b059f01724` with the data carry-across
- [x] `pytest` — 61 passed
- [x] Migration applied, verdict 1 → ticket 12 preserved; `downgrade`/`upgrade` round-trip verified
- [x] API confirmed on a fresh process: `ticket_ids: [12]`, no `ticket_id`, `verdict_id` on tickets
- [x] FE `types/api.ts` and `VerdictCard.tsx` updated; `tsc --noEmit` clean
- [x] `CLAUDE.md` updated in both repos

---

## Results & Execution Notes

Built as specified and — for the first time in this feature's history — **verified against the real database**,
because the credentials were restored partway through. 61 tests pass (was 56).

### Verified, not argued

- Migration `22b059f01724` applied to the live database. The existing link survived the FK inversion:
  verdict `1` still resolves to ticket `12`, now through `tickets.verdict_id`. The seven hand-made tickets
  correctly carry `null`.
- `downgrade -1` then `upgrade head` round-trips, and the link is restored in both directions.
- On a fresh process: `GET /api/v1/conversations/1/verdicts` returns `ticket_ids: [12]` with **no** `ticket_id`
  key, and `GET /api/v1/tickets` carries `verdict_id` on every row.
- `tsc --noEmit` clean in `bantu-coding-fe` after the contract change.

### Two things that had to be got right in a specific order

1. **`db.flush()` between the verdict and its tickets.** The tickets need `record.id`, which does not exist
   until the verdict is flushed. Adding them in one `db.add` batch without the flush would have failed on a
   null FK.
2. **`TYPE_CHECKING` imports on both sides.** `Ticket` and `Verdict` now reference each other, so both use a
   quoted annotation plus a `TYPE_CHECKING` import. A plain import either way is a circular import at startup.

### Deviations from the approved plan

- **`MAX_TICKETS_PER_VERDICT` is a named constant** in `app/schemas/verdict.py`, imported by both the schema
  and the prompt, so the number the Arbiter is told and the number enforced cannot drift. The plan just said
  "cap at 8".
- **`ticket_ids` is a property on the `Verdict` model**, not a computed field on the schema. `from_attributes`
  picks it up, so `VerdictRead` stays a plain declaration.
- The Arbiter's spoken message now lists the titles it created and switches between "Ticket created" and
  "N tickets created". Not in the plan, but the old wording named a single ticket that may no longer exist.

### The lossy downgrade, stated where it will be found

A verdict that produced several tickets has no representation in a single-FK column. The downgrade keeps only
the lowest-id ticket per verdict; the rest survive as ordinary board tickets with no verdict of record. This is
in the migration's own docstring, not only here, because that is where someone will be standing when it matters.

### What this widens

Model output now writes **several** rows per verdict instead of one. The controls that bound it are unchanged
and were re-tested: `ArbiterTicket` still has no `status` field, every ticket is hardcoded to `BACKLOG`, and the
test feeding `status: "in_progress"` through the parser still proves it cannot reach the database. The new
control is the cap — nine tickets is rejected, exactly eight accepted, both tested. The user accepted the
remaining risk (a bad split is now five wrong cards, not one) on the grounds that the board's add and edit are
the correction path.

### Still open

- The five hand-split tickets `#14`–`#18` remain, alongside `#12` (the verdict's original single ticket) and
  `#13` (a raw transcript dump from the FE's "create ticket from discussion" button). The user has not said
  whether to delete `#12`/`#13`.
- `#13` suggests that button assembles the wrong thing — 8424 characters of chat log is a record, not a work
  item. Worth revisiting on the FE side.
- The narrower endpoint checks written during the previous spec (422 upload rejections, exclusive provider
  activation, conversation cascade delete) were never run; the script exists but was overtaken.

## Recall Hints

arbiter-splits-tickets, one-verdict-many-tickets, tickets-verdict_id, fk-inversion, drop-verdicts-ticket_id,
data-migration-carry-link-before-drop, lossy-downgrade-min-ticket-id, MAX_TICKETS_PER_VERDICT, cap-8,
flood-the-board, ArbiterVerdict-tickets-list, no-status-field-still, backlog-only-still, drag-gate-in-code,
split-instruction-independently-shippable, dependency-order-by-id, one-ticket-when-one-job,
db-flush-before-child-tickets, TYPE_CHECKING-circular-import-ticket-verdict, ticket_ids-model-property,
VerdictRead-ticket_ids, TicketRead-verdict_id, fe-VerdictCard-ticket_ids, first-spec-verified-against-real-db,
verdict-1-ticket-12-live-data
