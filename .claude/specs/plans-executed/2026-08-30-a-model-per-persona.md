---
date: 2026-08-30
title: Each persona speaks through its own model
status: done
tags: [persona, ai-provider, migration, round, fe-contract]
commits: [19a7060]
---

# Each persona speaks through its own model

## Context

User request, from the frontend repo: *"tambahkan setting tiap persona akan menggunakan model yang mana.
jadi tiap persona bisa memilih modelnya masing-masing yang berbeda."* — each persona should be settable to
its own AI model, so the four can run on different ones.

**This spec is written from `bantu-coding-fe` because that is where the request landed, and the frontend
cannot do any of it.** The FE side is blocked until this ships; its counterpart spec is
`../bantu-coding-fe/.claude/specs/plans/2026-08-30-a-model-per-persona-in-the-fe.md`.

### Why the frontend cannot do this alone

Three things are missing, verified against this repo's source rather than assumed:

| Needed | Today |
|---|---|
| A link from a persona to a config | `app/models/persona.py` has `id, role, name, avatar, accent_color, tagline, display_order` and nothing else |
| That link on the wire | `app/schemas/persona.py` — `PersonaRead` does not carry it |
| A way to set it | `app/api/personas.py` has **only** `GET ""`. No write route of any kind |
| A per-persona provider at round time | `app/services/ai/provider.py:133` — `get_provider(db)` takes no persona |

The last row is the substantial one, and it is why this is not a two-line change. Today
`app/api/conversations.py:161` resolves **one** provider and passes that single object down:

```python
provider = get_provider(db)                                  # once, per stream
async for event in run_round(db, conversation, provider):    # discussion.py:92
    ...
verdict, spoken = await run_verdict(db, conversation, provider, round_index)   # arbiter.py:162
```

`run_round` then loops the three personas (`discussion.py:113`) and calls `provider.chat(...)` on that same
object for each of them. **One model per round is an architectural property of the current code, not a gap in
the API surface.** Making it per-persona means moving provider resolution from the caller into the loop.

Grepped INDEX.md — related:

- [`2026-08-30-projects-scope-chats-and-tickets`](../plans-executed/2026-08-30-projects-scope-chats-and-tickets.md)
  — the most recent migration, and the current head this one chains from.
- The AI provider config CRUD and the `is_active` exclusivity rule this spec deliberately keeps.

## Goal

Each of the four personas can be pointed at its own `ai_provider_config`, and the round uses each persona's
own model when it speaks. A persona with nothing set keeps today's behaviour exactly: it speaks through
whichever config is active.

## Approach

### 1. The column

`app/models/persona.py`:

```python
# Null means "use whichever config is_active" — which is what every persona did
# before this column existed, so an unset persona keeps today's behaviour.
ai_provider_config_id: Mapped[int | None] = mapped_column(
    ForeignKey("ai_provider_configs.id", ondelete="SET NULL"), default=None
)
```

**`ON DELETE SET NULL`, never CASCADE.** Deleting a model configuration must not delete the persona — there
are exactly four and they are seeded. The persona falls back to the active config instead, which is the same
state it starts in.

Nullable is doing real work here: it is the difference between "this persona has a preference" and "this
persona follows the global setting", and it keeps the existing rows valid without a data migration.

### 2. The migration

One new revision, `down_revision` = `db5519dc8798` (the current head — confirm with `alembic history` before
writing, do not trust this line). It adds one nullable column and one FK constraint. **No data migration and
no table rewrite**: existing personas get `NULL` and behave exactly as they do now.

Unlike the projects migration, this one must **not** delete any rows.

### 3. The schema and the write route

`app/schemas/persona.py`:

```python
class PersonaRead(BaseModel):
    ...
    ai_provider_config_id: int | None

class PersonaUpdate(BaseModel):
    # The only mutable field. Name, avatar, colour and role are seeded identity,
    # not user settings — see CLAUDE.md on the personas table.
    ai_provider_config_id: int | None = None
```

`app/api/personas.py` gains:

| Method | Path | Body | Returns |
|---|---|---|---|
| `PATCH` | `/api/v1/personas/{id}` | `{ai_provider_config_id: int \| null}` | `PersonaRead`, `404` |

Rules:

- Unknown persona id → `404`.
- An `ai_provider_config_id` that does not exist → `404` with a message naming the config, not the persona.
  Mirror `_require_project` in `app/api/tickets.py` rather than inventing a new shape.
- Explicit `null` **clears** the preference. This must use `model_dump(exclude_unset=True)` so that "not
  sent" and "sent as null" stay distinguishable — the same trap `update_project` already handles.
- Do **not** add any other writable field. The personas are seeded identity.

### 4. Resolution at round time — the part that needs care

`app/services/ai/provider.py`:

```python
def get_provider(db: Session, persona: Persona | None = None) -> AIProvider:
    """The persona's own config if it has one, otherwise whichever is active."""
```

Keep the existing "no active config" error for the fallback path. Add a distinct, `safe_to_display` error for
the case where a persona points at a config that has since become unusable, so the room can say *which*
persona is misconfigured rather than failing anonymously.

Then move resolution into the loop:

- `app/api/conversations.py` — stop resolving a provider and stop passing one down.
- `app/services/discussion.py:92` — `run_round(db, conversation)` resolves `get_provider(db, persona)`
  inside the per-persona loop, just before `provider.chat(...)`.
- `app/services/arbiter.py:162` — `run_verdict(db, conversation, round_index)` resolves
  `get_provider(db, arbiter)`.

**Resolve per persona, not once per round.** Resolving up front and caching a dict would reintroduce the
same coupling in a new shape, and a config edited mid-round should take effect on the next speaker.

**Do not decrypt more keys than needed.** `get_provider` already decrypts on each call; keep that, and do not
build a "decrypt all configs once" helper — the key material should live as briefly as possible
(CLAUDE.md 6.3).

### 5. What must not change

- **`is_active` stays, and stays exclusive.** It is the fallback for every unset persona and the only setting
  for a fresh install. This spec adds an override, it does not replace the global setting.
- Deleting a config that personas point at must leave those personas working, via `SET NULL` plus fallback.
  Worth a test: it is the one path where the new column can strand a round.
- No change to the SSE event shapes. The FE renders which model a persona uses from `PersonaRead`, not from
  the stream.

### 6. Tests

- `PATCH` sets, and `null` clears.
- Unknown persona → 404; unknown config → 404.
- A persona with a config set speaks through it; a persona with none falls back to the active one.
- **Deleting a config nulls the personas pointing at it, and a round still runs.**
- No active config and a persona with none set → the existing safe error.

### 7. FE Handoff

Write this section before the FE touches anything. It must state: the new `PersonaRead` field, the `PATCH`
route with its two 404s and the explicit-null semantics, that unset means "follow the active config", and
that deleting a config silently nulls the personas that referenced it — so the FE must refetch personas after
deleting a model, or it will show a selection the server no longer holds.

## Risks / Trade-offs

- **Cost is now per persona.** Four personas on four different models means four different bills and four
  different rate limits, and one misconfigured persona fails a round the other three would have survived.
  The error must name the persona.
- **A round can now be heterogeneous.** The transcript will mix models without saying so. Consider whether
  the FE should show which model spoke each line; that is a display question, not a reason to hold this back.
- **`get_provider` gains a fallback path**, which is a branch that will be wrong silently if the persona's
  config was deleted and `SET NULL` did not fire. The test above is what catches that.

## Files That Will Change

- `app/models/persona.py` — the nullable FK.
- `alembic/versions/<new>.py` — one nullable column, no data migration.
- `app/schemas/persona.py` — `PersonaRead` field, new `PersonaUpdate`.
- `app/api/personas.py` — the `PATCH` route.
- `app/services/ai/provider.py` — `get_provider(db, persona=None)`.
- `app/services/discussion.py`, `app/services/arbiter.py` — resolve inside the loop.
- `app/api/conversations.py` — stop resolving and passing a single provider.
- `tests/` — the cases above.
- `CLAUDE.md` — the personas contract table and the endpoint list.

---

<!-- Filled in when status = in-progress -->
## Progress

- [x] Nullable FK on `personas`, `ON DELETE SET NULL`
- [x] Migration `a3f1c27b5e04`, chained from `db5519dc8798`, applied
- [x] `PersonaRead.ai_provider_config_id`, `PersonaUpdate`
- [x] `PATCH /api/v1/personas/{id}`
- [x] `get_provider(db, persona=None)`
- [x] Resolution moved into the loops in `discussion.py` and `arbiter.py`
- [x] `conversations.py` no longer resolves or passes a provider
- [x] Tests, `CLAUDE.md`, `README.md`

---

<!-- Filled in when status = done / reverted / cancelled -->
## Results & Execution Notes

Executed as planned; no deviation from the Approach. Written and run from the `bantu-coding-fe` session on
the user's instruction, after they chose "BE then FE" over doing the backend separately.

Confirmed before writing the migration that `db5519dc8798` really was head, by parsing every revision's
`down_revision` rather than trusting the spec's own line.

### FE Handoff

The contract, as shipped:

```ts
type Persona = {
  id: number
  role: PersonaRole
  name: string
  avatar: string
  accent_color: string
  tagline: string
  display_order: number
  ai_provider_config_id: number | null   // NEW
}
```

| Method | Path | Body | Returns |
|---|---|---|---|
| `PATCH` | `/api/v1/personas/{id}` | `{ai_provider_config_id: number \| null}` | `Persona`, or `404` |

- **`null` means "follow whichever config is `is_active`"** — the behaviour every persona had before this
  column existed. `is_active` is still the global setting; this is an override on top of it, not a
  replacement.
- **Two different 404s.** An unknown persona id returns `detail: "Persona not found"`; an
  `ai_provider_config_id` that does not exist returns `detail: "AI provider config not found"`. The second is
  the one a stale FE list will hit.
- **Omitted vs explicit null are different**, per the repo's PATCH convention. Omitting the field leaves the
  choice untouched; sending `null` clears it. The FE must send an explicit `null` to mean "follow the active
  model".
- **`ai_provider_config_id` is the only writable field.** Sending name, avatar or role changes nothing.
- **Deleting an `ai_provider_config` silently nulls every persona pointing at it**, in the database via
  `ON DELETE SET NULL` — no event, no notification. **The FE must refetch personas after deleting a model**,
  or it will keep showing a selection the server no longer holds. Verified over HTTP: a persona pointed at a
  config came back `null` after that config was deleted.
- No SSE event shape changed. Which model a persona uses is read from `GET /api/v1/personas`, not from the
  stream.
- A persona pointed at a config that has vanished anyway produces an `error` event whose `detail` names the
  persona — e.g. "Challenger is set to an AI model that no longer exists" — and is `safe_to_display`.

### Verified

`pytest`: 84 passed, including seven new cases in `tests/test_persona_model_choice.py` — fallback when
unset, override when set, two personas resolving to two different models, the dangling-config error naming
the persona, the pre-existing no-active-config error unchanged, and that `PersonaUpdate` keeps absent and
explicit-null distinguishable.

Over HTTP against the running server:

| Check | Result |
|---|---|
| `PATCH` sets the choice | `ai_provider_config_id: 1` |
| Explicit `null` clears it | back to `null` |
| Omitted field leaves it alone | unchanged |
| Unknown persona | `404` |
| Unknown config | `404 "AI provider config not found"` |
| Delete a config a persona used | persona back to `null`, not dangling |

The database was left as it was found: all four personas `null`, and the user's single active `gemini`
config untouched. The throwaway config used for the delete test was created with `is_active: false`
deliberately, so it could not displace the active one.

### Not done

- **No "which model spoke this line" indicator.** Rounds can now be heterogeneous and the transcript does not
  say so. Raised in Risks as a display question; it needs its own decision and is not part of this request.
- Cost and rate limits are now per persona. Four personas on four vendors is four bills, and one
  misconfigured persona fails a round the other three would have survived — mitigated only by the error
  naming the persona.

## Recall Hints

persona model choice, ai_provider_config_id, per-persona model, PATCH personas, PersonaUpdate, exclude_unset,
explicit null clears, ON DELETE SET NULL, nullable FK, get_provider persona, provider per speaker, resolve in
loop, run_round signature, run_verdict signature, heterogeneous round, is_active fallback, dangling config
names the persona, safe_to_display, migration a3f1c27b5e04, head db5519dc8798, FE handoff, refetch personas
after delete
