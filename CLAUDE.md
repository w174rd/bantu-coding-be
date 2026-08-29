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
3. **Drag to In Progress** — the user drags a ticket into the "In Progress" column. **Only the user may drag**, never the AI. This is the product's primary control gate — treat it as an invariant and never build a path that lets the AI move a ticket itself.
4. **Automatic execution** — that move triggers Claude Code (via the **Claude Agent SDK**) to implement the task in the target repo.
5. **Auto commit & push** — the agent's work is committed and pushed automatically to the target GitHub repo.

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

### Current status: THE REPO IS EMPTY

This repo has **no commits at all** (`git log` empty, `git remote -v` empty). All that exists is this `CLAUDE.md`, `.claude/`, and `.gitignore`.

**Does not exist yet:** `app/`, `tests/`, `requirements.txt`, `.venv/`, `alembic/`, any database, endpoint, model, schema, or code of any kind.

Do not assume anything beyond that. Check first (`ls`, Grep) before editing or referencing a file.

### First milestone

FastAPI app + a `/health` endpoint + a working PostgreSQL connection. Persona chat, tickets, the board, and agent execution come **after** that foundation stands. Do not build modules for features that are not yet a real requirement.

Local dev: Windows PC. Production: not decided yet.

### Decisions NOT yet made

Do not invent answers for any of the following — if a task touches one, **ask the user first**:

- Does persona chat also use the Claude Agent SDK, or just the plain Messages API (`anthropic`)? What *is* decided: the Agent SDK for **ticket execution**.
- How do long-running jobs run — FastAPI `BackgroundTasks`, a separate worker, or a queue?
- How does agent progress stream to the FE — SSE, WebSocket, or polling?
- Execution isolation for the agent (container/sandbox/VM) — not decided at all.
- Auth and multi-user — none yet. The current assumption is single-user (the user themselves).
- How target repos get registered, cloned, and where their credentials live.

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

**None of the folders below exist yet.** This table is the placement plan, to be used when scaffolding is built.

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

**Dependency direction:** `API` → `Services` → (`DB`, Claude Agent SDK, Git/GitHub).

- `app/api/` handles HTTP concerns only (accept request, validate via schema, call a service, return a response) — avoid thick business logic there.
- `app/models/` (DB representation) and `app/schemas/` (API contract) must **never** be treated as interchangeable.
- Claude Agent SDK calls live in `app/services/`, **not** `app/api/`. An endpoint must never block waiting for an agent run to finish.
- Do not create new folders (`app/agents/`, `app/workers/`, etc.) until the feature that needs them is actually being built.

---

## 6. Agent Execution Security

This backend runs Claude Code with Bash/Write/Edit tools on a real machine, then pushes to GitHub. It is the most sensitive surface in the project — treat it seriously:

- **Do not loosen the Agent SDK permission mode** (e.g. a mode that bypasses all confirmations) without discussing it explicitly with the user. If a task seems to need it, raise it as a decision rather than quietly wiring it in.
- **A ticket is only executed when the user moved it** (section 0, point 3). Never add an automatic path that triggers execution without a user action.
- **The target repo must be explicit.** Never run the agent with a working directory derived from implicit state — always the path recorded for that ticket.
- **GitHub credentials come from env vars**, and never appear in source, logs, API responses, or prompts sent to the model.
- **Do not log prompt/response bodies that may contain secrets.** Log metadata (ticket id, repo, duration, status), not raw payloads.

---

## 7. Configuration & Secrets

- Every secret (DB password, `ANTHROPIC_API_KEY`, GitHub token, etc.) comes from env vars (`.env`) — **never** hardcoded in source.
- `.env` is **never** committed. `.env.example` (without real values) may be committed.
- `.venv/` is never committed.
- `.gitignore` already exists at the root. When adding tooling that produces new artifacts, add its patterns there.

---

## 8. Build & Run

Applies **after** the `app/` scaffolding exists (see section 0 — it does not yet):

```powershell
# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run the dev server (auto-reload)
uvicorn app.main:app --reload

# Run tests
pytest
```

Python 3.12+, PostgreSQL 18. Add a dependency to `requirements.txt` only when a concrete feature needs it — avoid dependencies that are not needed yet.

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
