---
date: 2026-08-29
title: The discussion round, the Arbiter's verdict, and SSE
status: done
tags: [persona, discussion, round, orchestration, sse, streaming, arbiter, verdict, provider, anthropic, ticket]
commits: []
---

# The discussion round, the Arbiter's verdict, and SSE

## Context

Follow-up to [discussion-room-data-layer](../plans-executed/2026-08-29-discussion-room-data-layer.md), which was
deliberately split so the storage layer could be built without spending a token. That half is committed
(`2d3a277`): personas, conversations, messages, document ingest, and the `ai_provider_configs` table all exist.

Grepped `INDEX.md` for `persona|discussion|round|sse|stream|provider|verdict|arbiter`: one entry, the spec above.
Its "Deliberately out of scope" section is the seed of this one.

**What is missing is the entire point of the feature.** Nothing calls a model. `POST /conversations/{id}/messages`
writes the user's row and returns it; no persona ever answers. The room is silent.

The frontend is waiting on this by the user's decision — building a chat UI against a backend that cannot hold a
discussion would mean guessing the message contract and then chasing it. This spec settles that contract.

### Carry-over that blocks verification

**Migration `f52211af4ab5` has never been applied.** `DB_USER`, `DB_PASSWORD` and `DB_NAME` are blank in the local
`.env`, so Postgres has been unreachable since the previous spec. This spec adds a *second* migration that stacks
on that one. Until the credentials are restored, neither can run and nothing below can be verified against a real
database — same caveat, now compounding.

### Decisions the user settled for this task

1. **The job model** — closes the last relevant §0 open item. **The SSE request drives the round**: the streaming
   endpoint runs the personas inline, persisting and emitting each message as it lands. No worker, no queue, no
   background task state.
2. **Message-level streaming**, not token-level. A persona appears when it finishes. This keeps `AIProvider` to a
   single `chat()` returning `str`, identical across all four vendors.
3. **All four providers implemented** — Anthropic, Gemini, Groq, OpenRouter — matching the `Provider` literal the
   previous spec already committed. A config that saves must actually work.

## Goal

The personas speak. A round runs `Architect → Researcher → Challenger` and streams to the browser over SSE; the
Arbiter steps in after N rounds, scores the proposed options as percentages, and creates a **Backlog** ticket
from the winner.

## Approach

### 1. The provider layer — `app/services/ai/`

- **`base.py`** — `AIProvider` ABC with `async chat(messages, system) -> str`, plus `AIProviderError`. Copied in
  shape from `../nara-persona-api`, which the user named as the reference.
- **`provider.py`** — `AnthropicProvider`, `GeminiProvider`, `GroqProvider`, `OpenRouterProvider`, a
  `_PROVIDER_CLASSES` registry, and `get_provider(db)` that loads the single active `AiProviderConfig`, decrypts
  its key, and instantiates the adapter. No active config → `AIProviderError`.
- `requirements.txt` gains `anthropic`, `google-genai`, `groq`, `openai` (the last serves OpenRouter through its
  OpenAI-compatible endpoint). Versions pinned to whatever actually installs, not guessed.

### 2. Speaking as one voice in a four-way room

Provider APIs model a two-party exchange (`user` / `assistant`). The room has five participants. The mapping,
applied per persona at call time:

- Messages **this** persona wrote → `assistant`.
- Everything else — the human, documents, the other three personas → `user`, each prefixed with its speaker
  (`Challenger:`, `You:`, `Document (crash.md):`) so the model can tell who said what.
- Consecutive `user` messages are merged, since some providers reject two in a row.
- `system` = `ROOM_CONTEXT` + that persona's `system_prompt` from `app/core/personas.py`.

History is trimmed to `CHAT_HISTORY_CHAR_BUDGET` characters, oldest first, adapting Nara's `_window`. Characters
rather than tokens, so no per-vendor tokenizer is needed.

### 3. The orchestrator — `app/services/discussion.py`

`run_round(db, conversation)` as an **async generator** yielding typed events, so the SSE route only has to
serialise what it is handed and owns no orchestration logic of its own.

- Computes the next `round_index` as `max(round_index) + 1`.
- For each role in order — architect, researcher, challenger — yields `persona_thinking`, calls the provider,
  persists the `Message` with `author_kind=persona`, `persona_id`, and `round_index`, then yields `message`.
- **Each message is committed as it completes.** A round that dies halfway leaves the messages that did land,
  because they are real contributions, not a partial write.
- After the third persona, if `round_index % arbiter_every_n_rounds == 0`, runs the verdict (step 4).

### 4. The Arbiter's verdict — `app/services/arbiter.py`

The Arbiter is prompted to answer as JSON: a headline, the options with `label` / `percentage` / `rationale`, and
the ticket to write. Structured output is done by instruction and parsing rather than vendor-specific JSON modes,
because those differ across the four providers and the ABC deliberately does not expose them.

**Model output is data, not a command** (CLAUDE.md §6.4). Every field crosses into the database only through a
Pydantic model:

- The JSON is extracted, parsed, and validated into `ArbiterVerdict`. Malformed output raises and surfaces as an
  `error` event — it never half-writes.
- `percentage` is coerced to `0..100`; if the options sum to between 95 and 105 they are normalised to exactly
  100, otherwise the verdict is rejected as malformed.
- The ticket is built through `TicketCreate` — title clamped to 1–200 characters, body free text.
- **`status` is never read from model output.** It is hardcoded to `TicketStatus.BACKLOG`. A test asserts this
  directly: the Arbiter must not be able to place a ticket in In Progress, which is the drag gate expressed in
  code rather than in prose.

### 5. Schema additions and migration

- `conversations.arbiter_every_n_rounds` — nullable integer, a per-room override of the global setting.
- **`verdicts`** — `id`, `conversation_id` (FK, cascade), `round_index`, `headline` (Text), `ticket_id`
  (FK → `tickets.id`, nullable, `ON DELETE SET NULL` so deleting a ticket does not erase the reasoning),
  `created_at`.
- **`verdict_options`** — `id`, `verdict_id` (FK, cascade), `label`, `percentage`, `rationale`, `display_order`.

No new enum type, so this migration avoids the trap the last two hit.

### 6. The SSE endpoint

`GET /api/v1/conversations/{id}/stream`, a `StreamingResponse` of `text/event-stream` with `Cache-Control:
no-cache` and `X-Accel-Buffering: no`.

Event types, each a typed Pydantic model so the FE contract is generated rather than described:
`round_started`, `persona_thinking`, `message`, `verdict`, `round_completed`, `error`.

**A per-conversation `asyncio.Lock` guards the round.** Two open tabs must not run overlapping rounds against the
same room; the second request gets `409`.

### 7. Reload has to work

`GET /api/v1/conversations/{id}/verdicts` returns past verdicts with their options. Without it, refreshing the
page loses every percentage chart ever produced — SSE only carries what is happening now.

### 8. Errors must not leak the key

A provider error is logged server-side with provider, model and status, and returned to the client as a generic
failure. Raw vendor exception text is never forwarded: it can echo request context, and the API key is in that
request. Logging stays metadata-only per §6.4 — conversation id, round index, persona role, duration, provider,
model. Never prompts, never transcripts.

## Verification

- `FakeProvider` implementing `AIProvider` drives every orchestration test — no network, no spend, deterministic.
- Round order is architect → researcher → challenger, each persisted with the right `persona_id` and `round_index`.
- The per-persona message mapping puts the persona's own lines in `assistant` and everyone else's in `user`,
  correctly prefixed and merged.
- History windowing drops oldest-first and never emits a leading non-`user` message.
- Arbiter parsing: clean JSON, JSON wrapped in prose, malformed JSON, percentages summing to 97 (normalised),
  percentages summing to 40 (rejected).
- **A verdict whose JSON asks for `status: "in_progress"` still produces a `backlog` ticket.**
- Cadence: with `arbiter_every_n_rounds=2`, no verdict on round 1, a verdict on round 2.
- A second concurrent stream on the same conversation gets `409`.
- Then, against a real database and one real provider call: one full round end to end, and `curl -N` showing
  events arriving incrementally rather than in one flush.
- `pytest` green.

## Risks / Trade-offs

- **`GET` with a side effect.** Opening the stream mutates the conversation. It is the price of the job model
  chosen; the lock stops concurrent duplication and the endpoint is documented as non-idempotent. If this becomes
  uncomfortable, `POST /conversations/{id}/rounds` returning the stream is the alternative — but the browser's
  `EventSource` only issues `GET`, so the FE would need a manual `fetch` reader.
- **A closed tab abandons the round.** Messages already committed survive; the remaining personas never speak,
  and nothing resumes them. Acceptable for single-user localhost, wrong for anything shared.
- **Four SDKs is a real dependency bump** (`anthropic`, `google-genai`, `groq`, `openai`) for what will usually be
  one active provider. It is what keeps the committed `Provider` literal honest.
- **Every round costs three provider calls, four when the Arbiter speaks.** The cadence setting is the only
  throttle; there is no spend cap.
- **Models do not reliably emit clean JSON.** The Arbiter is the one place this design depends on structure, and
  it is the most likely thing to fail in practice. It fails loudly rather than writing a partial verdict.
- **Nothing here can be verified against a database yet** — `f52211af4ab5` is still unapplied and this migration
  stacks on it. Both must apply before any of the above is more than an argument.
- The percentages are the model's own confidence, not a measurement. The FE renders them as a chart, which lends
  them an air of precision they have not earned — worth a caveat in the UI.

## Deliberately out of scope

- Token-level streaming (settled: message-level).
- Agent runs, target repos, and anything that executes a ticket.
- Auth, and multi-user correctness — the round lock is per-process.
- A spend cap or budget guard.
- The FE chat UI, which follows this.

## Files That Will Change

- `app/services/ai/__init__.py`, `base.py`, `provider.py` — new
- `app/services/discussion.py` — new, the round orchestrator
- `app/services/arbiter.py` — new, verdict prompting, parsing, validation, ticket creation
- `app/models/verdict.py` — new, `Verdict` and `VerdictOption`
- `app/models/conversation.py` — `arbiter_every_n_rounds` column
- `app/models/__init__.py` — register the new models
- `app/schemas/verdict.py` — new
- `app/schemas/events.py` — new, the SSE event models
- `app/api/conversations.py` — the stream endpoint and the verdicts endpoint
- `app/core/config.py` — `chat_history_char_budget`, `arbiter_every_n_rounds`
- `alembic/versions/<hash>_add_verdicts.py` — new
- `requirements.txt` — four provider SDKs
- `.env.example` — the two new settings
- `tests/test_discussion_round.py`, `tests/test_arbiter_verdict.py`, `tests/test_message_mapping.py` — new
- `CLAUDE.md` — record the settled job model and remove it from §0
- `../bantu-coding-fe/CLAUDE.md` — the SSE contract and the verdict shapes

---

## Progress

- [x] `app/services/ai/base.py` — `AIProvider` ABC, `AIProviderError` with `safe_to_display`
- [x] `app/services/ai/provider.py` — four adapters + `get_provider(db)`
- [x] `app/services/discussion.py` — round orchestrator, room→provider message mapping, history window
- [x] `app/services/arbiter.py` — verdict prompt, JSON extraction, typed validation, ticket + verdict write
- [x] `app/models/verdict.py`, `conversations.arbiter_every_n_rounds`, `app/models/__init__.py`
- [x] `app/schemas/verdict.py` (incl. `ArbiterVerdict`), `app/schemas/events.py`
- [x] `app/api/conversations.py` — `GET .../stream` and `GET .../verdicts`
- [x] `app/core/config.py` + `.env.example` — three new settings
- [x] `requirements.txt` — `anthropic==1.2.0`, `google-genai==2.20.0`, `groq==1.7.0`, `openai==3.6.0`
- [x] Migration `b7c4e0d51a93` written by hand — **not applied**
- [x] `pytest` — 56 passed
- [x] 18 endpoints confirmed in the OpenAPI schema; SSE wire format checked by hand
- [x] `CLAUDE.md` updated in both repos

**BLOCKED — unchanged from the previous spec:**

- [ ] `alembic upgrade head` (both `f52211af4ab5` and `b7c4e0d51a93`) and the downgrade round-trip
- [ ] One real round end to end against a live provider
- [ ] `curl -N` confirming events arrive incrementally rather than in one flush
- [ ] Round order, cadence, and the Backlog-only ticket verified **against a database** rather than as pure functions

`DB_USER`, `DB_PASSWORD` and `DB_NAME` are still blank in `.env`.

---

## Results & Execution Notes

Built as planned. 56 tests pass, 18 endpoints in the OpenAPI schema, SSE wire format checked by hand.
**Still nothing has touched a database** — see "Not verified" below before trusting any of it.

### The Anthropic SDK was a major version ahead of the reference

`nara-persona-api` pins `anthropic==0.122.0`; this repo resolved `anthropic==1.2.0`. Copying Nara's call shape
would have been guessing across a major version, so every symbol was verified against the installed packages
before any adapter was written (`AsyncAnthropic`, the `messages.create` parameter set, the exception classes,
and the same for `google-genai==2.20.0`, `groq==1.7.0`, `openai==3.6.0`).

Two things Nara does were deliberately not carried over:

- **`output_config={"effort": "low"}`** — the model is user-chosen free text, and `effort` is rejected by some
  models the `Provider` literal accepts. A persona writing three paragraphs does not need it.
- **`anthropic.NOT_GIVEN`** — avoided entirely by building the kwargs dict conditionally, so the adapter does
  not depend on a sentinel whose availability across 0.x/1.x was not worth verifying.

### Two defects introduced and caught before finishing

1. **The error path leaked vendor exception text** while the comment directly above it said it must not. A
   provider SDK's message can echo the request that produced it, and the API key travels in that request.
   Fixed with `AIProviderError.safe_to_display`: errors this codebase writes are marked safe and reach the
   browser; anything wrapped from a vendor stays in the log. **This flag is not in the approved spec** — the
   spec said "return a generic failure", which would also have hidden useful messages like "No active AI
   provider is configured".
2. **The stream used the request-scoped session.** The generator runs while the response streams, so its
   correctness would have depended on when FastAPI tears down a `yield` dependency relative to a
   `StreamingResponse` body. It now opens its own `SessionLocal()` and closes it in `finally`.

### Deviations from the approved plan

- **`_OpenAICompatibleProvider` base class.** Groq and OpenRouter differ only in client class and base URL, so
  request building and response unwrapping are written once. The plan implied four independent adapters.
- **The Arbiter now also posts a message in the room.** Not in the plan. Without it the percentage chart
  appears with no turn in the transcript explaining it, and the discussion reads as though it simply stopped.
  `run_verdict` therefore returns `(Verdict, Message)`.
- **`persona_max_tokens` setting added** — the plan listed only the history budget and the cadence.

### Not verified, and the gap is wider than last time

The credentials are still blank, so **two** hand-written migrations are now stacked and unapplied:
`f52211af4ab5` (personas/conversations/messages) and `b7c4e0d51a93` (verdicts). Neither has ever run.

More importantly, **the verification plan in this spec was not met.** It promised a `FakeProvider` driving
`run_round` to prove round order, cadence, and the Backlog-only ticket *against a database*. That needs a test
database, and choosing one is a decision the ticket spec deliberately deferred rather than made by accident —
introducing SQLite here would have made it by accident. So those three claims are argued from the code and
covered only as pure functions:

- Round order is asserted on the `ROUND_ORDER` constant, not on rows written.
- Cadence is asserted on `cadence()` arithmetic, not on a verdict actually firing after round 2.
- The Backlog-only guarantee is asserted structurally — `ArbiterTicket` has no `status` field, so there is no
  channel for a status to arrive through — but no ticket has been written and read back.

What *is* genuinely covered: the room→provider message mapping (own lines as `assistant`, others labelled and
merged, leading assistant turn dropped), history windowing, and Arbiter JSON parsing across clean JSON,
fenced JSON, malformed JSON, missing fields, an over-long title, rounding drift at 97, and a 40 that is rejected.

**First actions once `.env` is filled:** `alembic upgrade head`, `downgrade -1`, `upgrade head`; then a real
round with one provider key; then `curl -N` to confirm events arrive incrementally rather than in one flush.
Until then this feature is unproven end to end.

### Contract handed to the FE

`../bantu-coding-fe/CLAUDE.md` gained the stream and verdicts endpoints, the six `RoundEvent` shapes, `Verdict`
and `VerdictOption` types, and three rules that are easy to get wrong: opening the stream **starts a round** so
it must never be called from a `useEffect` that can re-fire; past verdicts come from `GET .../verdicts` because
SSE only carries the live round; and the percentages are the model's confidence, not a measurement, so the
chart needs labelling as judgement.

### Still open

- `CLAUDE.md` lines 61–71 in this repo still claim **"THE REPO IS EMPTY"** and name `/health` as the milestone.
  Reported three times now, still out of scope of an unrelated spec.
- FE `CLAUDE.md` section 6 opens with "None of the folders below exist yet", untrue for five specs.
- No spend cap. Each round is three provider calls, four when the Arbiter speaks.

## Recall Hints

discussion-round, sse, text-event-stream, EventSource, stream-starts-the-round, non-idempotent-get,
asyncio-lock-per-conversation, 409-concurrent-round, round-order-architect-researcher-challenger,
arbiter-cadence, arbiter_every_n_rounds, per-conversation-override, verdict, verdict_options, percentages,
percentage-normalisation-tolerance-5, arbiter-json-parsing, json-in-code-fence, ArbiterVerdict-typed-gate,
no-status-field-on-ArbiterTicket, backlog-only-ticket, drag-gate-in-code, model-output-is-data,
AIProviderError-safe_to_display, vendor-error-never-forwarded, api-key-in-request-context,
provider-adapters-four, anthropic-1.2.0-vs-nara-0.122.0, sdk-major-version-verified-not-copied,
no-output_config-effort-user-chosen-model, NOT_GIVEN-avoided, _OpenAICompatibleProvider-shared-base,
groq-openrouter-same-shape, openrouter-base-url, gemini-aio-generate_content,
room-to-two-role-mapping, speaker-labels, consecutive-user-merge, leading-assistant-dropped,
chat_history_char_budget, persona_max_tokens, stream-owns-its-session, SessionLocal-not-get_db,
streamingresponse-dependency-teardown, arbiter-speaks-in-room, run_verdict-returns-tuple,
migration-b7c4e0d51a93-never-applied, two-migrations-stacked-unapplied, no-db-backed-tests-by-design,
fakeprovider-test-not-written, test-database-strategy-still-undecided
