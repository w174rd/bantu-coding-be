# Specs — Plan-Driven Workflow

This folder holds **specs** (work plans) for non-trivial tasks in the Bantu Coding (backend) project.
Each spec is a single Markdown file that **moves between folders** as it progresses through its lifecycle.

Purpose: anti-hallucination (plan before coding), staying on track (an approved spec is the blueprint), and clear handoff across devices (`in-progress/` = the active state).

---

## Lifecycle

```
plans/            →    in-progress/        →    plans-executed/
(draft, not yet        (being worked on,          (finished, archive:
 user-approved)         active marker across       WHY this code exists)
                        devices)
```

**Transitions:**
1. Claude writes a new spec in `plans/<file>.md` when starting a non-trivial task.
2. User reviews → if approved, the file is **moved** to `in-progress/<file>.md`. Frontmatter `status` becomes `in-progress`.
3. When the work is done (code correct and committed), the file is **moved** to `plans-executed/<file>.md`. The "Results & Execution Notes" section is filled in and status becomes `done`.
4. If a task is reverted or skipped, the file still moves to `plans-executed/` with status `reverted` / `cancelled` plus the reason in the Results section.

**Move rule:** use `git mv` so the file's history stays intact and reads as a rename rather than delete+create.

---

## File Naming Convention

```
YYYY-MM-DD-<kebab-slug>.md
```

Examples:
- `2026-08-29-initial-structure.md`
- `2026-08-30-health-endpoint.md`
- `2026-09-02-ticket-model.md`

The date in the filename is the date the spec was **first created** in `plans/`. Do not change it when moving the file to a later folder.

---

## Single Template (follows the file through its whole lifecycle)

Sections are filled in progressively. While the spec is still in `plans/`, the lower sections stay empty.

```markdown
---
date: YYYY-MM-DD
title: <short title>
status: draft          # draft | in-progress | done | reverted | cancelled
tags: [tag1, tag2]
commits: []
---

# <task title>

## Context
<why this task came up; the trigger; the user request>

## Goal
<the outcome you want, in 1–3 sentences>

## Approach
<concrete steps; name the files/modules you will touch>

## Risks / Trade-offs
<optional — what the user should know before approving>

## Files That Will Change
- `app/path/to/file.py` — <short description of the change>

---

<!-- Filled in when status = in-progress -->
## Progress
- [ ] step 1
- [ ] step 2

---

<!-- Filled in when status = done / reverted / cancelled -->
## Results & Execution Notes
<what was ACTUALLY done; deviations from the plan; gotchas; subtle bugs found>

## Recall Hints
<comma-separated keywords, for grepping later>
```

---

## Rules for Claude

### When a spec is REQUIRED

**Non-trivial** tasks:
- Changes across > 1 file.
- A new feature (new API endpoint, new service, new DB model, a new Claude Agent SDK integration point, etc.).
- Refactors / architectural decisions (e.g. changing the `app/` structure, changing the dependency injection pattern).
- Bug fixes that require analysis (not typos).
- Database migrations (Alembic) that change the schema.
- Investigations that produce findings even without changing code → write straight into `plans-executed/` with status `done` and "investigation" as the approach.

### When a spec is NOT needed

**Trivial** tasks:
- Typo fixes.
- Simple variable renames.
- Changing one small string/constant.
- Reformatting code.
- Adding one clearly-needed dependency to `requirements.txt`.
- Answering a question without changing code.

### When starting a session (on any device)

1. **Check `in-progress/`** first — that is unfinished work from a previous session (possibly on another device).
2. **Glob `plans-executed/*.md`** for a history overview.
3. **Grep `plans-executed/`** if the user says "before", "yesterday", "we once", or names a topic that may have been touched.

### Updating an entry

An entry **may and should** be updated when:
- The approach changed during execution → update the "Approach" section and record the deviation under "Results".
- A new commit hash is available → update the `commits` field in frontmatter.
- The approach later turns out to cause problems → append an `## Update YYYY-MM-DD` section at the bottom; **do not delete** the old content.

---

## INDEX.md — The Central Index

`.claude/specs/INDEX.md` is a one-line-per-spec index: compact and grep-friendly.

**Format:**
```
YYYY-MM-DD | slug | Title | tags:... | hints:...
```

**Maintenance rules:**
- Every time a spec moves to `plans-executed/`, add a new line to INDEX.md immediately.
- Fill `hints:` from the spec's `## Recall Hints` section — if that section is empty, fill it with the main keywords manually.
- Never delete old lines — INDEX.md is append-only.

**Fast recall:**
```bash
# Find specs that touched tickets or the agent
grep -i "ticket\|agent" .claude/specs/INDEX.md

# Find specs tagged 'db'
grep "tags:.*db" .claude/specs/INDEX.md

# Find every spec about migrations
grep -i "migration" .claude/specs/INDEX.md
```

---

## How to Recall (for the user)

```powershell
# See what is currently active (across devices)
Get-ChildItem .claude\specs\in-progress\*.md

# The 10 most recently finished specs
Get-ChildItem .claude\specs\plans-executed\*.md | Sort-Object Name -Descending | Select-Object -First 10

# Search by keyword — via INDEX.md (faster)
Select-String -Path .claude\specs\INDEX.md -Pattern "ticket|agent"

# Or grep every file directly (for detail)
Select-String -Path .claude\specs\plans-executed\*.md -Pattern "ticket|agent"
```
