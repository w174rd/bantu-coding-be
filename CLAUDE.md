# CLAUDE.md — Working Rules for Claude Code

Behavioral rules for Claude working on the **Bantu Coding (Backend)** project.
For work plans and task history (lifecycle: plans → in-progress → plans-executed), see `.claude/specs/`.
No architecture spec exists yet — the first one gets written when the `app/` scaffolding is built.

**Language:** all project documentation (this file, specs, INDEX) is written and maintained in **English**. Keep it that way.

---

## 0. About the Project

`bantu-coding-be` is the backend for a collaborative coding-assistant app. The product flow:

1. **Multi-persona chat** — the user talks with several AI personas that have distinct personalities. Slack-style UI/UX, built in the separate `bantu-coding-fe` repo.
2. **Backlog tickets** — out of those discussions, the AI can create backlog tickets.
3. **Drag to In Progress** — the user drags a ticket into the "In Progress" column. **Only the user may move a ticket *into* In Progress** — never the AI, never an automatic rule. This is the product's primary control gate: it is the only thing standing between an AI-written ticket and an AI-executed code change on a real repo. Treat it as an invariant.
   *(Moving a ticket **out** of In Progress once a run finishes is a separate question — see "Decisions NOT yet made". The gate guards entry, not every transition.)*
4. **Automatic execution** — that move triggers Claude Code (via the **Claude Agent SDK**) to implement the task in the target repo.
5. **Auto commit & push** — the agent's work is committed and pushed automatically to the target GitHub repo.

### Core concepts (shared vocabulary)

These names are shared with `bantu-coding-fe`. Use them in models, schemas, routes, and types so the two repos do not drift apart:

| Term | Meaning |
|---|---|
| **Persona** | One AI personality the user can talk to. |
| **Conversation** / **Message** | A chat thread and its entries. |
| **Ticket** | A backlog item created out of a conversation. The unit of work. |
| **Agent run** | One Claude Agent SDK execution against a ticket, carrying status and progress. |
| **Target repo** | The external GitHub repo an agent run reads and pushes to — never this repo. |

Where one of these is not yet modeled, that is a gap to fill — not a licence to invent a different name for it.

### The board's columns (settled)

`Backlog → In Progress → In Review → Done`, defined once as `TicketStatus` in `app/core/enums.py` and shared by the model and the schemas.

**In Review** is where a ticket waits while the agent's pull request is open. That state exists because section 6.3 requires a run to open a PR rather than push to a default branch — without the column there is nowhere for "the agent finished but you have not accepted it" to live.

The database column is a **native Postgres enum**, so adding a status is a migration and a product decision, never a config tweak.

**A successful run auto-advances the ticket** from In Progress to In Review. This does not violate the gate in point 3 — that gate guards *entry* into In Progress, not every transition (section 6.2).

### The discussion room (settled)

Stage 1 of the product flow is **one shared Slack-style channel** — not a thread per persona. Four fixed AI
characters and the human all speak in the same room. The cast is not user-configurable, and adding a fifth is a
migration (`PersonaRole` is a native Postgres enum), not a config change.

| Role (`PersonaRole`) | Name | Avatar | Accent | What they do |
|---|---|---|---|---|
| `ARCHITECT` | Architect | 🏗️ | `#6366f1` | Proposes the solution |
| `RESEARCHER` | Researcher | 📚 | `#14b8a6` | Supplies facts, constraints, prior art |
| `CHALLENGER` | Challenger | 🧨 | `#f43f5e` | Antithesis — attacks the proposal |
| `ARBITER` | Arbiter | ⚖️ | `#f59e0b` | Scores the options and writes the ticket |

The personas are named for their function, not given personal names. `name` therefore mirrors `role` — it is
still a separate column because it is display text the FE renders, while `role` is the enum that code branches on.

Identity and display data live in the `personas` table, seeded by migration. **System prompts live in
`app/core/personas.py`, keyed by role, and are never returned by any endpoint.** Personas reply in whatever
language the user writes in.

**Flow:** a round runs `Architect → Researcher → Challenger` automatically; **the Arbiter steps in on its own
after N rounds**, scores the options as percentages, and creates the winning ticket. That ticket lands in
**Backlog** — which is why it does not violate the drag gate in point 3. Only the user moves anything into
In Progress.

**The AI layer is provider-agnostic**, modelled on the sibling project `../nara-persona-api`: an `AIProvider`
ABC with one `chat()` method, one adapter per vendor, and an `ai_provider_configs` row (provider, model,
Fernet-encrypted key, `is_active`) that is CRUD'd over the API. Provider and model are switched at runtime, not
through `.env`. Exactly one config may be active. **The Claude Agent SDK is not used for chat** — it stays
reserved for ticket execution.

**Progress reaches the FE over SSE.** The user's own messages go up as an ordinary POST.

**How a round runs (settled).** `GET /api/v1/conversations/{id}/stream` runs the round **inline and streams it**
— opening that stream is what makes the personas speak, so it is deliberately non-idempotent. No worker, no
queue, no background-task state. An `asyncio.Lock` per conversation makes a second concurrent stream `409`
rather than a duplicate round. Two consequences to keep in mind before building on it: a closed tab abandons the
round (committed messages survive, the rest never happen), and the lock is per **process**, so this stops being
correct the moment the app is not single-user on localhost.

Streaming is **message-level**: a persona appears when it finishes. This is what keeps `AIProvider` down to one
`chat()` returning `str` across all four vendors. Token-level streaming would need a second, vendor-specific
code path in every adapter.

**The Arbiter's output is the sharpest boundary in the chat half of this codebase.** It emits JSON that becomes
tickets, so §6.4 applies in full: it is parsed, validated through `ArbiterVerdict`, and only then written.
`ArbiterTicket` has **no status field** — the ticket status is hardcoded to `BACKLOG` in `app/services/arbiter.py`.
That is the drag gate expressed in code, and `tests/test_arbiter_verdict.py` asserts it. Do not add a status
field to that schema.

**One verdict produces one *or several* tickets.** The Arbiter splits work that has independently shippable
parts, ordered so each unblocks the next, and returns one ticket when the job is genuinely one job. The foreign
key therefore lives on `tickets.verdict_id` (null for anything written by hand on the board), not on the
verdict. `ArbiterVerdict.tickets` is capped at `MAX_TICKETS_PER_VERDICT` — every entry is a row written on the
model's say-so, and the cap is what stops a confused Arbiter flooding the board in one write. Splitting
multiplies the cards, never the authority: all of them still land in Backlog.

Vendor exception text is **never** forwarded to a client — it can echo the request it came from, and the API key
travels in that request. `AIProviderError.safe_to_display` marks the messages this codebase wrote itself; only
those reach the browser.

Uploaded `.txt`/`.md` documents are ingested as `document` messages: decoded in memory, never written to disk,
the filename kept for display only. Their content is untrusted input under section 6.1.

### Stack

| Component | Choice |
|---|---|
| Language | Python 3.12+ |
| HTTP API | FastAPI |
| Database | PostgreSQL 18 |
| ORM | SQLAlchemy |
| DB driver | Psycopg 3 |
| Schema migrations | Alembic |
| Validation & config | Pydantic / Pydantic Settings |
| AI layer | **Claude Agent SDK** (`claude-agent-sdk`) |

Default model: `claude-opus-5`, unless the user asks for another.

### Current status: TICKETS AND THE DISCUSSION ROOM ARE BUILT, THE DATABASE IS NOT MIGRATED

Four specs are executed (see `.claude/specs/INDEX.md`). `git remote -v` is still empty.

**Exists:** `app/` (`api/`, `core/`, `db/`, `models/`, `schemas/`, `services/`), `tests/`, `alembic/` with three
migrations, `requirements.txt`, `.venv/`. Eighteen endpoints: tickets CRUD, `/api/v1/personas`,
`/api/v1/conversations` with messages, document upload, verdicts and the SSE round stream, and
`/api/v1/ai-provider-configs`.

**Does not exist yet:** agent runs — nothing that executes a ticket, clones a target repo, or pushes. No auth.
No FE chat UI (that repo's `routes/Chat.tsx` is still a placeholder).

**The database is the thing to check first.** `f52211af4ab5` and `b7c4e0d51a93` are hand-written and have
**never been applied**, because `DB_USER`, `DB_PASSWORD` and `DB_NAME` are blank in the local `.env`. Until
they are filled and `alembic upgrade head` succeeds, every endpoint except the tickets ones returns a `500`,
and the persona/conversation/verdict schema is unproven. Run `alembic current` before believing anything here.

Do not assume beyond this. Check first (`ls`, Grep) before editing or referencing a file — this block goes
stale faster than anything else in this document.

### Next milestone

Restore the `DB_*` credentials, apply both migrations, and verify a real discussion round end to end. The FE
chat UI follows. Agent execution comes after that, and needs its isolation decision settled first (section 6.3).

There is **no `/health` endpoint** and none is wanted — it was proposed in the scaffolding spec and rejected as
ceremony. Do not add one back.

Local dev: Windows PC. Production: not decided yet.

### Decisions NOT yet made

Do not invent answers for any of the following — if a task touches one, **ask the user first**:

- Execution isolation — **that** runs are isolated is settled and required (section 6.3). **How** is open: Docker, a VM, or a dedicated unprivileged user. Pick the mechanism, not whether.
- Auth — none yet. Single-user is the current assumption, and the app stays bound to localhost until that changes (section 6.3, item 6).
- How target repos get registered and cloned. The credential *shape* is settled (per-repo scoped, separate from the app's — section 6.3, item 2); where the record lives is not.

---

## 1. Git Rules — TWO DIFFERENT CONTEXTS, DO NOT CONFLATE THEM

This project has an auto-commit & auto-push feature. That is a **product feature**, not a permission granted to Claude. Keep the two strictly apart:

### 1a. THIS repo (`bantu-coding-be`) — Claude as a developer

The safe defaults below apply. The GitHub remote is **not set up yet** and the branch/PR strategy **will be decided by the user later** — do not guess a remote URL or a branching strategy.

- **Push nothing** without an explicit instruction from the user at that moment.
- **Do not change remote configuration** (`git remote add/remove/set-url`) without an explicit instruction.
- **Never force-push** to any branch unless the user explicitly asks.
- **Do not commit automatically** unless the user asks.
- When an implementation is finished, **do not immediately offer to commit** — report "implementation complete", let the user test, and wait for them to ask.
- Always create a new commit, never `--amend`, unless the user asks for an amend.
- Do not use `--no-verify` to skip git hooks.
- Never commit files containing secrets (see section 7).

**The moment the user gives instructions about remote/branch/PR, update this section immediately** — do not wait to be asked again.

### 1b. TARGET repos (the repos the agent works on) — auto-commit as a feature

Auto-commit and auto-push to a target repo is **intended behavior**, executed by application code — not by Claude while writing this codebase.

- The rules in 1a do **not** constrain this feature.
- Conversely, this feature does **not** grant Claude permission to push the `bantu-coding-be` repo.
- Code that pushes to a target repo must be explicit about which repo, which branch, and which credentials it uses. Never derive the target from `cwd` or from global state.

---

## 2. Anti-Hallucination

- **Read before changing.** Read every file you are about to edit in full. Do not infer a file's contents from its name or from convention.
- **Verify that a function/class/endpoint exists** with Grep before calling it. Do not assume a helper/util/dependency exists just because "FastAPI projects usually have one".
- **Do not guess the Claude Agent SDK's API.** Function names, options, and event shapes must come from the official docs (`code.claude.com/docs/en/agent-sdk`) or from code already in the repo — never from memory. Agent SDK ≠ Messages API ≠ Tool Runner; do not mix them.
- **Cite explicit paths** when referring to code: `app/services/agent.py:42`, not "the agent service file".
- If information is not in the repo and the user did not provide it, **say you don't know** — do not make it up.
- If the user names a module/file/env var that cannot be found, **confirm first** before assuming.

---

## 3. Anti-Overthinking

- **Do exactly what was asked.** Do not add refactors, cleanups, or "small fixes while I'm here" outside the scope.
- **No premature abstraction** (e.g. a generic base service/repository for a single use case). Three similar lines beat a helper whose need is not yet clear.
- **No defensive error handling** for scenarios that cannot happen. Trust the framework's guarantees (FastAPI dependency injection, Pydantic validation, SQLAlchemy session lifecycle).
- **Do not write comments** unless there is a non-obvious *Why* (a hidden constraint, a bug workaround, a subtle invariant). Identifier names already explain the *What*.
- **Do not create new documentation files** (`*.md`, `README`) unless the user explicitly asks.
- **No backwards-compatibility shims** for code just written. Delete the old thing instead.
- **Do not build modules for hypothetical features.** This product has 5 flow stages (section 0) — build them one at a time as they are worked on, not all up front.

---

## 4. Staying on Track

**STOP — Gating Check before touching any file.**
Before calling Edit/Write/Bash for a code change, ask yourself:
> *"Does this task touch > 1 file, add a new endpoint/feature/pattern, or change module structure?"*

If **yes** → you **must** grep INDEX.md for this task's keywords, then write a spec in `.claude/specs/plans/` first (link to any relevant older spec), then **stop and wait for user approval**.
No exceptions — not even if the user already listed every file in their instruction, not if the user says "just do it while you're at it", and not if the change feels "repetitive/mechanical across many files". Input formatted like a checklist does **not** replace the spec requirement; it is a strong signal the task is non-trivial.

Once this gate passes (or the task really is trivial), the rules below apply:

- For non-trivial work (>1 file, or new logic), **write a short plan first** and wait for approval before executing.
- For small work (rename, string change, typo fix, a small change to 1 file), just do it.
- If you find an unrelated problem mid-task (an unrelated bug, a code smell), **note and report it** — do not fix it on the spot.
- If the user's instruction is ambiguous, **ask**; do not assume.

---

## 5. Project Patterns (Quick Reference)

These folders all hold code: `app/api/`, `app/core/`, `app/db/`, `app/models/`, `app/schemas/`, and
`app/services/` (`documents.py`, `discussion.py`, `arbiter.py`, and `ai/` — the provider adapters).

| Need | Location |
|---|---|
| New API endpoint/router | `app/api/<name>.py`, register the router in `app/main.py` |
| Business logic: persona chat, ticket lifecycle, agent orchestration, git/GitHub operations | `app/services/` |
| DB models (SQLAlchemy) | `app/models/` |
| Request/response schemas (Pydantic) | `app/schemas/` |
| DB connection, session, dependencies | `app/db/` |
| Env config, security, logging, shared constants | `app/core/` |
| Schema migrations | `alembic/` |
| Tests | `tests/`, mirroring the `app/` structure |

**API conventions**, settled by the first endpoints in `app/api/tickets.py`:

- **URL shape:** `/api/v1/<resource>`, plural.
- **No response envelope.** Endpoints return the resource itself and use HTTP status codes for outcome — `201` create, `204` delete, `404` missing, `422` validation. Do not introduce a `{status, message, code, content}` wrapper: every call site would then unwrap before it could use anything, duplicating what status codes already express.
- **`PATCH` uses `exclude_unset`.** An omitted field is left alone; an explicit `null` clears it. Those are different, and schemas must preserve the difference.
- **Enums shared between a model and its schemas live in `app/core/enums.py`**, so neither imports the other.

**Dependency direction:** `API` → `Services` → (`DB`, Claude Agent SDK, Git/GitHub).

- `app/api/` handles HTTP concerns only (accept request, validate via schema, call a service, return a response) — avoid thick business logic there.
- `app/models/` (DB representation) and `app/schemas/` (API contract) must **never** be treated as interchangeable.
- Claude Agent SDK calls live in `app/services/`, **not** `app/api/`. An endpoint must never block waiting for an agent run to finish.
- Do not create new folders (`app/agents/`, `app/workers/`, etc.) until the feature that needs them is actually being built.

---

## 6. Agent Execution Security

The sharpest surface in this project. The backend runs Claude Code with Bash, Write, and Edit against a real repository, holding real credentials, and pushes the result to GitHub. **Read this section before writing any code that touches an agent run.**

### 6.1 The threat model, stated plainly

Ticket text is untrusted input that becomes instructions for a process with shell access:

```
chat content → AI writes a ticket → user drags → agent runs (Bash/Write/Edit) → push to GitHub
```

Everything upstream of that chain is attacker-reachable in ordinary use: a pasted error log, a stack trace copied off a forum, a quoted web page, a dependency's README, an issue body. The agent also **reads the target repo**, so that repository's own contents — comments, fixtures, docs, config files — are untrusted input as well.

Treat every string that reaches an agent run as potentially adversarial, including strings the AI itself wrote. An instruction injected into a persona's context can be laundered into a ticket that the persona authors in good faith.

**Do not try to solve this by filtering.** There is no regex, keyword list, or "sanitize the prompt" step that makes untrusted text safe to hand a shell-capable agent. Every control below works by limiting what a compromised run can *reach* — not by trying to recognize a malicious ticket.

### 6.2 What the drag gate does and does not do

Section 0, point 3 makes the user's drag the only trigger for execution. That is real and necessary, but be precise about its scope:

- It gates **when** a run happens. It does **not** gate **what** the run does.
- The user approves by looking at a card. The agent receives the full ticket body and then reads an entire repository.
- It is a launch button, not a code review.

Never cite the drag gate as the reason some other control is unnecessary.

### 6.3 Non-negotiable controls

Requirements, not preferences. If a task appears to need one of these weakened, **stop and ask the user** — do not weaken it and mention it afterwards.

1. **Every agent run is isolated.** A container (or equivalent boundary) per run, with only the target repo mounted. No app `.env`, no app database, no other repos on the host, no SSH keys, no host home directory. **`cwd` is not a boundary** — passing a path does not stop `cd ..`; the mount does.
2. **The runner gets its own credentials.** An `ANTHROPIC_API_KEY` separate from the app's, so agent spend can be budgeted and revoked on its own. A GitHub credential scoped to the target repos only — a fine-grained PAT with `contents:write`, or a GitHub App. Never an account-wide classic token.
3. **Never push to a target repo's default branch.** A run pushes to its own branch and opens a PR. This restores the human review of the diff that step 5 of the product flow otherwise removes. Direct push to `main`/`master` is prohibited.
4. **Never bypass the Agent SDK permission model.** Do not enable a mode that auto-approves every tool call because it makes a task easier. If a run genuinely needs broader permission, that is the user's decision, recorded in a spec.
5. **Restrict network egress from the run** to what it needs. A run that can reach arbitrary hosts can exfiltrate anything it can read.
6. **The app binds to localhost and stays there until it has authentication.** An unauthenticated endpoint that triggers arbitrary code execution and a git push is the worst thing in this codebase to expose. CORS origins stay an explicit allowlist — never `*`.

### 6.4 Rules for code that drives a run

- **Nothing from a ticket's prose may choose a target.** Repo, branch, credential, and working directory come from the ticket's **record** — typed columns and foreign keys — never parsed out of its text, and never out of the agent's output.
- **Never interpolate ticket text** into a shell command, a path, or a git argument.
- **Never feed agent output into a privileged action** without a typed check. Model output is data, not a command.
- **Log metadata, not payloads.** Ticket id, repo, branch, duration, status, exit reason. Never prompt bodies, agent transcripts, diffs, or environment contents.
- **A failed or interrupted run must still tear down its workspace** and any credential material it was given. Cleanup belongs in a `finally`, not on the happy path.

### 6.5 Changing this section

How runs are isolated, credentialed, or pushed is an architectural decision. Any change to it needs its own spec and the user's approval (section 4) — never fold one into an unrelated task.

---

## 7. Configuration & Secrets

- Every secret (DB password, `ANTHROPIC_API_KEY`, GitHub token, etc.) comes from env vars (`.env`) — **never** hardcoded in source.
- **The app's secrets and the agent runner's secrets are two separate sets** (section 6.3, item 2). The app's `.env` must never be reachable from inside a run — not mounted, not inherited through the environment, not passed as arguments.
- Secrets never appear in source, logs, API responses, error messages returned to the client, or any prompt sent to a model.
- `.env` is **never** committed. `.env.example` may be committed.
- **Infrastructure identifiers are not published either — not just passwords.** Real database names, roles, hostnames, and bucket or repo names stay out of every committed file: `.env.example`, specs, tests, fixtures, and docs. `.env.example` documents the *shape* of configuration with blank values, never the actual ones. Tests use generic placeholders (`testuser`, `testdb`) so that committed code carries no real identifier.
- `.venv/` is never committed.
- `.gitignore` already exists at the root. When adding tooling that produces new artifacts, add its patterns there.

---

## 8. Build & Run

### First-time setup

```powershell
# Bare `python` on this machine is a 32-bit Python 3.10 — below the 3.12+ this
# project requires. Always name the interpreter explicitly.
py -3.12 -m venv .venv

.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env
```

Then fill `DB_USER`, `DB_PASSWORD`, and `DB_NAME` in `.env`. They are blank in the example on purpose (section 7), so choose your own.

The role and database must already exist on **PostgreSQL 18, which listens on port 5433**. Port 5432 belongs to PostgreSQL 17 on this machine, and 5434 to PostgreSQL 14 — pointing at 5432 silently connects to the wrong server. `psql` on PATH is 17.2, so use `psql -p 5433` to reach 18.

```powershell
alembic upgrade head
```

### Day to day

```powershell
.\.venv\Scripts\Activate.ps1

uvicorn app.main:app --reload    # http://127.0.0.1:8000, docs at /docs
pytest
```

**The app will not start without a `.env`.** `Settings` gives the `DB_*` fields no defaults, deliberately: missing configuration fails loudly instead of quietly connecting somewhere unintended.

Add a dependency to `requirements.txt` only when a concrete feature needs it — avoid dependencies that are not needed yet.

---

## 9. Specs — Plan-Driven Workflow (REQUIRED for non-trivial tasks)

`.claude/specs/` uses a three-stage lifecycle:
- `plans/` — specs written but not yet approved for execution.
- `in-progress/` — specs being worked on. **This folder is the active state across sessions/devices.**
- `plans-executed/` — permanent archive: why this code exists, gotchas, execution results.

Full conventions are in `.claude/specs/README.md`. **Read that file** before writing your first spec.

**When starting a session (on any device) — REQUIRED, in order:**
1. **Check `.claude/specs/in-progress/`** first — that is unfinished work from a previous session (possibly on another device). Continue from there.
2. **Read `.claude/specs/INDEX.md`** — skim it to internalize existing task history. Required every new session, without the user asking.
3. If the user says "before", "yesterday", "we once", or names a topic that may have been touched → grep INDEX.md first (fast), then open the full spec in `plans-executed/` if you need detail.

**When receiving a new non-trivial task:**
1. **Grep INDEX.md** for this task's keywords — check whether an older spec covers a similar aspect or touches the same files/modules.
   - If one exists: open it, read its "Results & Execution Notes" and "Recall Hints" sections, then link it in the new spec's "Context" section.
2. Write the spec first at `.claude/specs/plans/YYYY-MM-DD-<slug>.md` (template in the specs README).
3. Wait for user approval before executing.
4. Once approved, `git mv` the file to `.claude/specs/in-progress/`, change `status: in-progress`, and fill in the progress checklist.
5. Implementation done → report to the user, and **do not offer to commit** — wait until the user has finished testing and explicitly asks.
6. When **the user asks to commit**: `git mv` the spec to `.claude/specs/plans-executed/`, change `status: done`, fill in "Results & Execution Notes", then add one line to **INDEX.md**. Only then run the code commit + the journal commit (two separate commits — see section 1a).

**Exception — trivial tasks** (typos, simple renames, a string change, reformatting): just do them, no spec needed. Full definition in the specs README.

**Moving between folders:** use `git mv`, not a manual move, so the file's git history stays intact as a rename. (Note: `git mv` fails for a file never `git add`-ed; for new files a plain `mv` followed by `git add` is fine.)

---

## 10. Continuity Across Sessions/Devices

- This `CLAUDE.md` is committed to git → it syncs automatically via `git pull` once a remote exists.
- `.claude/settings.json` (project level) **may** be committed.
- `.claude/settings.local.json` is **never** committed (per-device; already in `.gitignore`).
- Before starting a new session: check `.claude/specs/in-progress/` first (see section 9).
- Before switching device/session: commit all changes (pushing awaits remote instructions — see section 1a).
- Companion repo: `bantu-coding-fe` (frontend, separate repo). If a backend change alters the API contract, record it in the spec so the FE session can follow.
