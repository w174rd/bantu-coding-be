# Specs Index

Central index of every executed spec, grouped by feature area.

> **For Claude:** Read this file at the start of every session. Grep it before writing a new spec.
> **Updating:** Add a new entry when the user asks to commit (at the same time as archiving the spec into `plans-executed/`).

Entry format:
```
- `YYYY-MM-DD` [**slug**](plans-executed/...) — Title | hints: keyword1, keyword2, ...
```

---

## Project Setup & Structure
> grep keywords: scaffolding, structure, venv, requirements, alembic, config, session, database, port, python-version, identifiers

- `2026-08-29` [**initial-scaffolding**](plans-executed/2026-08-29-initial-scaffolding.md) — BE scaffolding: `app/` layout, Pydantic Settings, SQLAlchemy session, Alembic wiring. No endpoints — `/health` rejected by user as ceremony | hints: initial-scaffolding, fastapi-scaffolding, no-health-endpoint-by-user-decision, alembic-env-py-no-set_main_option, configparser-percent-interpolation-password, quote_plus-database-url, cors_origins-str-not-list-pydantic-settings-json-parse, python-dotenv-transitive-not-direct, docs-openapi-public-no-auth, pg18-port-5433-not-5432, pg17-owns-default-5432, psql-on-path-is-17.2, bare-python-32bit-3.10, py-3.12-venv-required, alembic-current-auth-failure-proves-wiring, DeclarativeBase-sqlalchemy-2.0, pool_pre_ping, no-ticket-model-board-columns-undecided, infrastructure-identifiers-not-published, testuser-testdb-generic-fixtures

## Tickets & Board
> grep keywords: ticket, status, enum, migration, alembic, autogenerate, crud, api, envelope, board, columns

- `2026-08-29` [**ticket-model-and-crud**](plans-executed/2026-08-29-ticket-model-and-crud.md) — `Ticket` model, the repo's first migration, and five CRUD routes at `/api/v1/tickets`. Board columns and no-envelope conventions settled here | hints: ticket-model, ticket-crud, first-migration, alembic-autogenerate-empty-migration, env-py-must-import-app-models, models-init-import-not-enough, drop_table-leaves-enum-type-behind, sa-Enum-drop-op-get-bind, downgrade-upgrade-roundtrip-proves-enum-drop, values_callable-lowercase-enum-values, native-postgres-enum-ticket_status, no-response-envelope-decision, api-v1-resource-url-shape, exclude_unset-patch-semantics, updated_at-onupdate-verified, pg18-4-port-5433, board-columns-backlog-in_progress-in_review-done, in_review-exists-because-PR-not-push, auto-advance-does-not-violate-drag-gate

## Multi-Persona Chat
> grep keywords: persona, cast, conversation, message, discussion, room, document, upload, provider, agnostic, encryption, sse

- `2026-08-29` [**discussion-room-data-layer**](plans-executed/2026-08-29-discussion-room-data-layer.md) — Four-persona cast, conversation/message tables, `.txt`/`.md` ingest, and a provider-agnostic `ai_provider_configs` table modelled on `nara-persona-api`. **Migration written but never applied — DB credentials were blank** | hints: discussion-room, persona-cast, four-personas, architect-researcher-challenger-arbiter, role-names-not-personal-names, provider-agnostic, nara-persona-api-reference, AIProvider-ABC, ai_provider_configs, runtime-provider-switch, fernet-encrypted-api-key, AI_CONFIG_ENCRYPTION_KEY, api_key_preview-never-the-key, unreadable-preview-after-rotation, exclusive-activation-route-layer, no-partial-unique-index-autoflush-ordering, nara-defect-claim-was-wrong, persona_role-native-enum, message_author_kind-native-enum, round_index-forward-looking, source_name-display-only, document-ingest-txt-md-only, utf8-decode-required, 256KiB-cap, read-max_bytes-plus-one, filename-never-a-path, untrusted-document-6.1-laundering, messages-ordered-by-id-not-created_at, cascade-delete-conversation, migration-hand-written-never-applied, blank-db-credentials-blocked-verification, fe_sendauth-no-password-supplied, bulk_insert-native-enum-risk, postgresql-ENUM-create_type-False-fallback, python-multipart-required-for-UploadFile, services-documents-pure-function, claude-md-repo-is-empty-still-stale, fe-claude-md-status-was-stale

- `2026-08-29` [**discussion-round-and-verdict**](plans-executed/2026-08-29-discussion-round-and-verdict.md) — Four provider adapters, the `Architect → Researcher → Challenger` round streamed over SSE, and the Arbiter's scored verdict writing a Backlog ticket. Settles the job model. **Neither migration applied; the FakeProvider round tests were not written** | hints: discussion-round, sse, text-event-stream, EventSource, stream-starts-the-round, non-idempotent-get, asyncio-lock-per-conversation, 409-concurrent-round, round-order-architect-researcher-challenger, arbiter-cadence, arbiter_every_n_rounds, per-conversation-override, verdict, verdict_options, percentages, percentage-normalisation-tolerance-5, arbiter-json-parsing, json-in-code-fence, ArbiterVerdict-typed-gate, no-status-field-on-ArbiterTicket, backlog-only-ticket, drag-gate-in-code, model-output-is-data, AIProviderError-safe_to_display, vendor-error-never-forwarded, api-key-in-request-context, provider-adapters-four, anthropic-1.2.0-vs-nara-0.122.0, sdk-major-version-verified-not-copied, no-output_config-effort-user-chosen-model, NOT_GIVEN-avoided, _OpenAICompatibleProvider-shared-base, groq-openrouter-same-shape, openrouter-base-url, gemini-aio-generate_content, room-to-two-role-mapping, speaker-labels, consecutive-user-merge, leading-assistant-dropped, chat_history_char_budget, persona_max_tokens, stream-owns-its-session, SessionLocal-not-get_db, streamingresponse-dependency-teardown, arbiter-speaks-in-room, run_verdict-returns-tuple, migration-b7c4e0d51a93-never-applied, two-migrations-stacked-unapplied, no-db-backed-tests-by-design, fakeprovider-test-not-written, test-database-strategy-still-undecided

- `2026-08-30` [**arbiter-splits-complex-work**](plans-executed/2026-08-30-arbiter-splits-complex-work.md) — One verdict can now produce several tickets; the FK inverts to `tickets.verdict_id`. **First spec verified against the real database** | hints: arbiter-splits-tickets, one-verdict-many-tickets, tickets-verdict_id, fk-inversion, drop-verdicts-ticket_id, data-migration-carry-link-before-drop, lossy-downgrade-min-ticket-id, MAX_TICKETS_PER_VERDICT, cap-8, flood-the-board, ArbiterVerdict-tickets-list, no-status-field-still, backlog-only-still, drag-gate-in-code, split-instruction-independently-shippable, dependency-order-by-id, one-ticket-when-one-job, db-flush-before-child-tickets, TYPE_CHECKING-circular-import-ticket-verdict, ticket_ids-model-property, VerdictRead-ticket_ids, TicketRead-verdict_id, fe-VerdictCard-ticket_ids, first-spec-verified-against-real-db, verdict-1-ticket-12-live-data


- `2026-08-30` [**a-model-per-persona**](plans-executed/2026-08-30-a-model-per-persona.md) — each persona may run on its own `ai_provider_config`; provider resolution moves from once-per-round to once-per-speaker | hints: per-persona-model, personas-ai_provider_config_id, nullable-fk, ON-DELETE-SET-NULL-not-cascade, null-means-follow-is_active, is_active-still-global-fallback, PATCH-personas-only-writable-field, PersonaUpdate, exclude_unset-null-vs-absent, two-different-404s, config-not-found-detail, get_provider-persona-arg, resolve-per-speaker-not-per-round, run_round-signature-dropped-provider, run_verdict-signature-dropped-provider, conversations-no-longer-resolves, heterogeneous-round, dangling-config-names-the-persona, safe_to_display, migration-a3f1c27b5e04, no-data-deleted, head-verified-by-parsing-down_revision, FakeSession-monkeypatch-decrypt, 84-tests, fe-must-refetch-personas-after-delete, written-from-the-fe-session, no-which-model-spoke-indicator

## Projects & Target Repos
> grep keywords: project, container, scope, project_id, repo_url, default_branch, target repo, cascade, credential

- `2026-08-30` [**projects-scope-chats-and-tickets**](plans-executed/2026-08-30-projects-scope-chats-and-tickets.md) — `Project` becomes the container every conversation and ticket belongs to, and where the target repo is recorded. **Breaking API change for the FE; the migration deleted every pre-project row** | hints: projects, project-container, project_id-not-null, cascade-delete-project, unique-project-name, 409-duplicate-name, repo_url-https-only, urlparse-scheme-check, typed-column-not-prose-6.4, default_branch-is-pr-base, no-credential-column-yet, target-repo-record-lives-on-projects, settled-open-decision, migration-db5519dc8798, migration-deletes-data, delete-before-not-null, downgrade-does-not-restore, alembic-check-index-drift, index-true-on-fk-columns, ix_tickets_verdict_id-preexisting-drift, nested-list-routes, arbiter-inherits-conversation-project, _FakeSession-record-test, TicketUpdate-no-project_id, fe-breaking-change, fe-project-picker-required, claude-md-status-block-rewritten, 26-endpoints-15-paths

---

Areas expected as the product grows — create each section when its first entry exists:
- **Tickets & Board** — backlog, columns, drag-to-progress
- **Agent Execution** — Claude Agent SDK, job lifecycle, progress streaming
- **Git & GitHub Integration** — cloning target repos, auto commit, PR flow, credentials

Specs in flight (written but not yet approved/executed) live in `.claude/specs/plans/` — check that folder directly, not this index.
