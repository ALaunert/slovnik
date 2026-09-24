# Slovnik Product State

Last audited: 2026-09-24 (Compose setup verified: 2026-09-24; core runtime audit: 2026-08-27)

## Product Summary

Slovnik is a Serbian vocabulary trainer MVP for Russian-speaking learners. It has a FastAPI backend, Postgres persistence, Alembic migrations, and a Vue 3/Vite frontend. The app supports lightweight `userId` profile access, a shared vocabulary pool, per-user learning progress, daily new-word and review sessions, daily and weekly quizzes, weak-word tracking, a password-gated vocabulary editor with manual and AI-assisted fill, and Russian/Serbian UI copy.

This audit reflects the current product implementation, including AI vocabulary fill and
reveal-first active recall, built on the MVP delivered in PR #1, "Serbian vocabulary trainer MVP."

## Language Assistant Foundation

- On 2026-08-26, Domain Model v0.1 was approved for evolving Slovnik from separate vocabulary,
  review, and quiz modes into an adaptive language-learning assistant.
- The approved direction is a modular monolith with four bounded contexts: Language Catalog,
  Curriculum, Practice & History, and Learner Progress. The next-activity orchestrator combines
  curriculum constraints, learner evidence, and memory risk; it is not an AI chat agent.
- AI may later provide candidate exercises or evaluate ambiguous answers through replaceable ports.
  It cannot own curriculum progression, select learning truth, or update learner state directly.
- The backend foundation is implemented as a modular-monolith addition: typed contracts, four
  context-owned domain modules, reversible persistence, immutable evidence, replayable learner
  projections, curriculum publication/frontier services, and a deterministic next-activity selector.
- `VocabularyItem`, `UserWordProgress`, the existing review scheduler, quizzes, routes, responses,
  and frontend remain the authoritative public product behavior.
- Feature-flagged learning and quiz adapters can atomically shadow accepted legacy interactions into
  domain runs, activities, events, and learner projections. The flag is off by default.
- Shadow next-activity comparison is diagnostic only: it cannot change selection, learner state, or
  legacy responses. Daily new-word and review reads invoke it in an isolated read session using the
  first authoritative result (`NEW`, `DUE`, or `WEAK`) or `NONE`; failures remain isolated.
- Catalog bootstrap is creation-only. Each bootstrapped Form stores a canonical source fingerprint;
  shared learning/quiz mapping rejects missing, ambiguous, and stale content before evidence writes.
  `python -m app.catalog_audit` reports only affected legacy word IDs.
- Quiz shadow enrollment is per attempt. Attempts started while the flag was off remain legacy-only;
  answer/event drift abandons a linked run with the fixed `quiz_shadow_enrollment_gap` diagnostic
  and does not block legacy quiz behavior.
- Production shadow enablement is rejected unless both data-lifecycle and trusted-identity release
  gates are explicitly true. Those policies and real authentication remain deferred.
- The approved design and its explicit deferred log are in
  `docs/superpowers/specs/2026-08-26-domain-model-v0.1-design.md` and
  `docs/progress/domain-model-v0.1.md`.
- A formally accepted ADR and backend-only foundation SDD were added on 2026-08-26 and implemented
  through gates G1–G4 on 2026-08-27 using three context-owned workstreams plus one integrator.
  A strong implementation-level audit is recorded in `docs/progress/document-audit-2026-08-26.md`;
  initiative-wide status and mandatory follow-ups are tracked in `docs/progress/PROGRESS.md`.

## Implemented User-Facing Capabilities

- User entry screen creates or loads a profile by `userId`; the last `userId` and UI language are stored in browser localStorage.
- Dashboard lets a learner change CEFR level, daily new-word count, and UI language.
- Vocabulary list supports CEFR and theme filters, shows Serbian Cyrillic/Latin, Russian translation, level, and theme.
- Editor password unlocks add/edit controls; the editor can create and update vocabulary entries with optional register, stress, notes, examples, and example translations.
- After unlock, an editor can enter one Serbian word and apply a validated OpenAI or previously
  stored generation as a non-destructive patch. Existing vocabulary matches offer an explicit edit
  link, partial results highlight still-empty required fields, technical failures preserve the form,
  and the latest pre-fill form snapshot can be restored from frontend memory.
- Structured stress is rendered by emphasizing the full stressed syllable in both Serbian scripts
  in the vocabulary list and the shared new-word/review card. The legacy free-form stress marker
  remains metadata fallback when structured stress is absent.
- Daily new-word session selects unseen words at the learner's preferred level up to `daily_new_word_count`; completion records per-user progress.
- Review is productive Russian-to-Serbian recall: each due card initially exposes only the Russian
  cue, level, and theme; reveal shows the Serbian answer and details; and one Again, Hard, Good, or
  Easy rating must be saved before the learner advances.
- Daily and weekly quizzes use three question types: Serbian-to-Russian multiple choice, Russian-to-Serbian typing, and remembered/forgot self-check with answer reveal.
- Incorrect quiz answers mark words weak and can be repeated once per question. Quiz completion is blocked until required repeats are answered.
- Weekly quiz includes words touched this calendar week plus weak words; correct weekly answers clear weak status.
- Results page shows score, question count, weak-word count, and mistake details from `sessionStorage`.
- UI copy exists for Russian (`ru`) and Serbian (`sr`); the static HTML document language remains `ru`.

## Backend Architecture and API Areas

- FastAPI app assembly is in `backend/app/main.py`; CORS origins come from settings.
- Settings are in `backend/app/config.py`; placeholder `EDITOR_PASSWORD` values are allowed only for explicit local/test environments.
- SQLAlchemy session setup is in `backend/app/db.py`; Alembic uses app metadata and `DATABASE_URL`.
- Routers are thin wrappers over service modules:
  - `GET /api/health`
  - `POST /api/profiles`, `PATCH /api/profiles/{user_id}`
  - `GET /api/vocabulary`, `GET /api/vocabulary/themes`, `GET /api/vocabulary/{word_id}`, `POST /api/vocabulary`, `PUT /api/vocabulary/{word_id}`, `POST /api/vocabulary/editor/verify`, `POST /api/vocabulary/ai-fill`
  - `GET /api/learning/{user_id}/new-words`, `POST /api/learning/{user_id}/new-words/complete`, `GET /api/learning/{user_id}/review`, `GET /api/learning/{user_id}/review/status/{word_id}`, `POST /api/learning/{user_id}/review/answers`, `POST /api/learning/{user_id}/review/complete`
  - `POST /api/quizzes/{user_id}/start`, `POST /api/quizzes/{user_id}/{attempt_id}/answers`, `GET /api/quizzes/{user_id}/{attempt_id}/questions/{word_id}/{question_type}/answer`, `POST /api/quizzes/{user_id}/{attempt_id}/complete`
- Business logic lives in focused modules under `backend/app/services/`, including
  `ai_vocabulary_service.py` for duplicate/store/generation orchestration and
  `openai_vocabulary_client.py` for the Responses API adapter.
- Language-assistant services under `backend/app/services/` own catalog bootstrap, curriculum
  publication/frontier, immutable event recording, projection/replay, deterministic selection,
  shadow learning/quiz adapters, and non-authoritative comparison. Context persistence is under
  `backend/app/domain_models/` and `backend/app/repositories/`.
- Concurrent AI fills for the same normalized source are coalesced with an expiring database
  reservation. Lease timestamps come from the database clock, and acquisition lock/statement
  waits are bounded by a monotonic request deadline. The owner commits the lease before calling
  OpenAI, renews it through an independent heartbeat until validation, rechecks, fenced
  persistence, and release finish, and bounds heartbeat shutdown. Waiters reuse the stored result
  or receive a stable `503`; provider failures release the lease, stale leases can be reclaimed
  after a worker crash, and the request session holds no database transaction during the provider
  call.
- Manual vocabulary create/update accepts optional structured stress with non-empty, aligned
  Cyrillic/Latin syllable arrays, a valid zero-based stress index, and NFC-equivalent exact
  reconstruction of both Serbian spellings. The legacy `stress_marker` contract remains supported.
- `learning_service.py` owns the lightweight review scheduler and SQL due query. A singular rating
  locks the progress row with `SELECT ... FOR UPDATE`, rechecks due state while holding the lock,
  applies one transition, and commits it, so concurrent ratings cannot both apply to the same due
  state on PostgreSQL.
- `backend/app/seed.py` seeds three sample A1 words only.
- The backend has a tested, backend-only OpenAI adapter using strict nullable Structured Outputs,
  a configurable API key and timeout, and `gpt-5.6-luna` as the default model. Product errors use
  stable codes, while provider and semantic validation failures are logged with request metadata
  without logging the API key or raw source word in the adapter.

## Frontend Architecture and Routes/Views

- Vue app bootstraps in `frontend/src/main.ts`; routes are defined in `frontend/src/router.ts`.
- Routes: `/`, `/dashboard`, `/vocabulary`, `/new-words`, `/review`, `/quiz`, `/results`, `/editor`, `/editor/:id`.
- API calls are centralized in `frontend/src/api/client.ts`.
- Browser session state is centralized in `frontend/src/stores/session.ts`.
- Route-level views live in `frontend/src/views/`; reusable display components live in `frontend/src/components/`.
- `WordEditorView.vue` owns the AI request, partial-patch, duplicate, toast, and in-memory undo
  workflow; `StressEditor.vue` owns aligned syllable entry, selection, validation, and preview.
- `ReviewView.vue` owns initial loading/error/empty states, answer reveal, per-card saving, focus
  movement, completion, and lost-response reconciliation through the precise per-word status API.
- `frontend/src/i18n/messages.ts` contains Russian and Serbian UI strings.

## Data Model and Persistence

- Docker Compose starts PostgreSQL, FastAPI, and Vue/Vite for local development. It preserves Postgres data and frontend `node_modules` in named volumes, bind-mounts backend/frontend sources for reload, runs Alembic upgrades before Uvicorn, and leaves sample vocabulary seeding manual. Published PostgreSQL, API, and Vite ports bind to host `127.0.0.1`; the backend uses the internal `postgres:5432` address while the frontend receives only the browser-facing API URL and file-watcher setting. Tests override the DB with in-memory SQLite fixtures.
- Initial migration `20260702_0001_initial_schema.py` creates:
  - `vocabulary_items`: global word content, CEFR level, theme, optional notes/examples, timestamps.
  - `user_profiles`: `user_id`, preferred level, daily new-word count, UI language.
  - `user_word_progress`: per-user word status, seen/quizzed timestamps, correct/incorrect counts, weak status.
  - `quiz_attempts`: user-scoped quiz type, timestamps, score, total questions, serialized question plan.
  - `quiz_answers`: submitted answers per attempt/question.
- Migration `20260724_0002_ai_vocabulary_fill.py` adds nullable JSON `stress_pattern` to
  `vocabulary_items` while preserving the legacy `stress_marker`, and creates
  `ai_vocabulary_generations`. Generation records retain the source word, a unique normalized
  source key, generated JSON payload, missing required fields, model and prompt versions, and
  timestamps. Both generation JSON fields are required, and explicit Python `None` values are
  rejected.
- Migration `20260725_0003_ai_fill_reservations.py` creates
  `ai_vocabulary_generation_reservations` without rewriting the existing `0002` revision.
  Reservations use the normalized source as their primary key and retain an owner token and expiry
  for crash recovery.
- Migration `20260725_0004_active_recall_schedule.py` adds nullable `next_review_at`, non-null
  `review_interval_days` and `review_streak` counters defaulted to zero, and an index on
  `next_review_at` without backfilling legacy review dates.
- Migration `20260826_0005_domain_foundation.py` adds 11 domain tables for Language
  Catalog, Curriculum, Practice & History, and Learner Progress. It preserves all legacy rows and
  is reversible back to `20260725_0004`.
- Learning events are immutable and idempotent per learner/key. Learner target state is a replayable
  projection with explicit baseline, competence, memory-v1 and evidence cursor fields.
- A technical A1 curriculum pilot and deterministic selector exist internally. They are not a
  claim of curated A1 coverage and are not exposed by a public next-activity endpoint.
- New-word completion schedules the first review one day later. Review ratings update the current
  scheduling state as follows:
  - Again: ten minutes, stored interval `0`, streak reset, mark weak.
  - Hard: one day, streak reset, preserve weak state.
  - Good: two days initially, otherwise double the current interval up to 180 days; increment the
    streak and clear weak state.
  - Easy: four days initially, otherwise triple the current interval up to 365 days; increment the
    streak and clear weak state.
- Three consecutive Good/Easy ratings set status to `learned`; Again and Hard reset that streak and
  put the word in `reviewing`. An incorrect quiz answer marks the word weak and clears
  `next_review_at`, making it immediately eligible; a correct quiz answer does not alter its
  schedule.
- The review queue is filtered in SQL to `seen`, `reviewing`, or `learned` rows that are due.
  Explicit schedules are due at `next_review_at <= now`. Legacy null schedules are due when weak or
  when both first and last exposure are null or predate today. Results are capped at 20 and ordered
  by weak first, then due time (null first), last exposure (null first), and stable progress-row ID.
- `POST /api/learning/{user_id}/review/answers` rejects unknown, unseen, and future-due words with
  `400` and returns the updated progress row.
  `GET /api/learning/{user_id}/review/status/{word_id}` returns an uncapped precise `is_due` result
  for lost-response reconciliation. The compatibility batch
  `/api/learning/{user_id}/review/complete` endpoint remains; each accepted word is scheduled one
  day ahead, its recall streak is reset, and its prior weak-state and learned-state behavior is
  preserved.
- Clearing `VocabularyItem.stress_pattern` stores SQL `NULL`; JSON values are replaced wholesale
  rather than tracked for in-place mutation.
- Vocabulary content is global; profiles, progress, quiz attempts, answers, and weak-word state are scoped by `user_id`.

## Security/Access Model and Caveats

- `userId` access is not authentication. Anyone who knows a `userId` can load that profile.
- Vocabulary create/update and editor verification use the `X-Editor-Password` header compared directly with `EDITOR_PASSWORD`.
- AI fill uses the same header. `OPENAI_API_KEY` is read only by the backend and is never sent to
  or stored by the frontend.
- The editor password is a simple shared secret, not a user account or session system.
- Production startup rejects placeholder editor passwords unless `ENVIRONMENT` is explicitly local/test.
- `LANGUAGE_ASSISTANT_SHADOW_ENABLED` defaults to false. Non-local enablement also requires
  `LANGUAGE_ASSISTANT_SHADOW_DATA_LIFECYCLE_READY` and
  `LANGUAGE_ASSISTANT_SHADOW_TRUSTED_IDENTITY_READY`; configuration validation rejects unsafe enablement.
- There is no delete endpoint for vocabulary, no real auth, no roles, no rate limiting, and no CSRF/session hardening.

## Verification and Test Coverage

- Compose setup in `README.md` uses `docker compose up -d --build` after copying `.env.example` to `.env`; the existing host-run workflow remains available. Changing frontend npm dependencies requires `docker compose run --rm frontend npm ci` because its dependency volume persists. Compose configuration validation confirms all three published ports use host `127.0.0.1`.
- Verified on 2026-09-24 in a distinct disposable Compose project: configuration and frontend environment assertions passed; both images built; PostgreSQL became healthy; Alembic reached `20260826_0005 (head)` before Uvicorn started; the API health and Vite HTML endpoints responded; a temporary Vue edit appeared through Vite; vocabulary stayed at zero across a backend restart and became three only after manual seed; the container frontend build and all 83 unit tests passed.
- A separate 30-second PostgreSQL init-script smoke test reproduced premature readiness from a socket-only probe and an exhausted healthcheck retry budget. The Compose healthcheck now probes TCP on `127.0.0.1` with a 45-second startup grace period. On a fresh disposable volume, PostgreSQL stayed unready during initialization, then became healthy; backend migrations reached `20260826_0005 (head)` before Uvicorn, and `/api/health` returned OK.
- Backend verification documented in `README.md`: `cd backend && .venv/bin/ruff check .` and `.venv/bin/pytest -v`.
- Backend editable installation is verified with `.venv/bin/python -m pip install -e ".[dev]"`;
  setuptools discovers only `app*`, and the dev dependency remains on Ruff `0.6.x`.
- Frontend verification documented in `README.md`: `cd frontend && npm run test:unit`, `npm run build`, and `npm run test:e2e`.
- Database rebuild/seed verification is documented in `README.md` with `docker compose up -d postgres`, Alembic downgrade/upgrade, and `python -m app.seed`.
- Backend tests cover health, config validation, schema defaults, profiles, vocabulary, learning
  sessions, SQL due filtering/order/cap, every interval transition and cap, row-lock serialization,
  precise status reconciliation, quiz schedule reset, compatibility batch scheduling, quiz
  selection/submission/completion, weak-word behavior, repeat limits, and answer reveal.
- Language-assistant coverage includes frozen target/event/shadow wire contracts, all four context
  repositories, reversible migration constraints, event idempotency, replay and projection order,
  memory-v1 transitions, legacy baseline bootstrap, curriculum lifecycle/frontier, deterministic
  selector policies, shadow learning/quiz atomicity and concurrency, diagnostic isolation, and
  privacy-safe bounded payloads, catalog freshness, rollout flag transitions, deterministic partial
  evidence, persisted activity provenance, and runtime comparison wiring.
- OpenAI adapter tests cover strict response-schema requirements, configured SDK request arguments,
  prompt constraints, request-id retention, typed provider failures, and secret/source-word log
  redaction without real network calls.
- AI service and endpoint tests cover source normalization and validation, duplicate priority and
  edit exclusion, persistent store hits, partial patches, controlled fields and limits, structured
  stress validation, provider error translation, concurrent request coalescing, reservation
  failure/stale recovery, insertion races, and stable response bodies.
- Migration tests default to temporary SQLite databases and cover upgrade/downgrade data
  preservation, the upgrade path from the existing `0002` revision, JSON schema, and
  normalized-source uniqueness. Setting
  `SLOVNIK_TEST_POSTGRES_ADMIN_URL` enables the same round trip in a newly created disposable
  PostgreSQL database plus a synchronized two-session expired-reservation contention check that
  keeps the provider active beyond the initial lease; the normal `DATABASE_URL` is never migrated
  or dropped by that target. Supplied PostgreSQL configuration, connection, and privilege errors
  fail instead of skipping.
- Frontend unit tests cover app shell localization, session persistence, dashboard
  settings/localization, vocabulary API helpers, quiz repeat/self-check behavior, AI fill and undo,
  route/password request races, duplicate navigation, partial-field highlighting, localized
  feedback, accessibility, manual structured-stress editing, and the active-recall API/view,
  including initial loading, reveal-first hiding, save gating, precise status reconciliation,
  focus movement, completion, localization, and long-content constraints.
- Structured-stress coverage includes manual API create/update persistence and validation,
  canonical-equivalent Unicode reconstruction, legacy marker compatibility, full-syllable
  rendering, script-specific syllable arrays, invalid-pattern fallback, and HTML-safe text output.
- Playwright e2e covers the basic user-id-to-dashboard path, a mocked AI editor flow, and a mocked
  active-recall journey at 1280x900 and 390x844. Recall coverage proves answer details stay absent
  before reveal, all four ratings appear afterward, the next cue waits for the singular POST
  response, JSON payloads are exact, loading/focus/completion states work, and maximum bounded
  unbroken content creates no mobile horizontal overflow. No e2e scenario calls a real backend or
  OpenAI.
- Verified on 2026-08-27 after review remediation: full backend passed with `674 passed, 16 skipped`;
  targeted catalog/quiz/curriculum/selection/schema regressions, Ruff, whitespace, fresh migration
  upgrade, the explicit ORM/migration domain-schema parity regression, and the read-only catalog
  audit passed. PostgreSQL-only tests remain environment-gated by
  `SLOVNIK_TEST_POSTGRES_ADMIN_URL`.
- Verified on 2026-07-25: PostgreSQL-enabled backend tests passed with `221 passed`;
  frontend unit tests passed with `83 passed`; the production build passed; and all six Playwright
  tests passed.
- Manual MVP flow is in `docs/testing/mvp-manual-test.md`.

## Known Limitations / Deferred Scope

- Real authentication and authorization are deferred.
- Native mobile apps, audio pronunciation, bulk import, social features, and payments are not implemented.
- The legacy scheduler remains authoritative. Shadow mode can retain mapped review/quiz evidence,
  but production retention/export/delete policy, review-history analytics, desired-retention
  controls, FSRS fitting, and workload forecasting remain deferred.
- Catalog semantic versioning and automatic reconciliation remain deferred. Stale mappings are
  reported and rejected rather than silently rewritten.
- `alembic check` still reports five pre-existing legacy nullable mismatches on quiz/profile/
  vocabulary timestamps; the new domain tables have an explicit ORM/migration parity regression.
- AI fill v1 supports one Serbian word per request and strict normalized equality only. It has no
  batch input, regenerate action, Russian-to-Serbian card creation, morphology/fuzzy matching,
  generation review queue, or generation-store administration UI.
- Weekly quiz still uses calendar-week selection plus weak words rather than the review scheduler.
- Seed data is intentionally tiny and not a production vocabulary corpus.
- Results are stored client-side in `sessionStorage`; historical quiz analytics UI is not implemented.
- Vocabulary deletion, duplicate detection, import/export, and advanced content governance are not implemented.
- The frontend's `lang` attribute is hard-coded to `ru` even when Serbian UI copy is selected.

## Important Source Files and Docs

- `README.md`: setup, verification, and MVP access caveat.
- `.env.example`: local environment variables.
- `docker-compose.yml`: local PostgreSQL, migration-gated FastAPI, and Vue/Vite services, with source mounts and persistent data/dependency volumes.
- `backend/Dockerfile` and `backend/.dockerignore`: backend development image and context exclusions.
- `frontend/Dockerfile` and `frontend/.dockerignore`: lockfile-based Vite development image and context exclusions.
- `backend/app/models.py`: SQLAlchemy models.
- `backend/app/schemas.py`: Pydantic API contracts.
- `backend/app/routers/`: FastAPI endpoints.
- `backend/app/services/`: product rules for profiles, vocabulary, learning, and quizzes.
- `backend/alembic/versions/20260702_0001_initial_schema.py`: initial database schema.
- `backend/alembic/versions/20260724_0002_ai_vocabulary_fill.py`: structured stress and persistent
  AI generation schema.
- `backend/alembic/versions/20260725_0003_ai_fill_reservations.py`: concurrent generation
  reservation schema.
- `backend/alembic/versions/20260725_0004_active_recall_schedule.py`: persisted review scheduling
  state and due-time index.
- `backend/alembic/versions/20260826_0005_domain_foundation.py`: reversible domain
  foundation schema.
- `backend/app/services/learning_service.py`: due query, interval transitions, row locking, and
  compatibility review completion plus guarded shadow learning evidence.
- `backend/app/services/quiz_service.py`: quiz behavior plus guarded shadow quiz evidence.
- `backend/app/services/next_activity_service.py`: deterministic internal selector and optional
  non-authoritative comparison seam.
- `backend/app/services/shadow_selection_runtime.py`: persistence-backed isolated runtime
  composition for diagnostic selection comparison.
- `backend/app/services/catalog_mapping_service.py`: source fingerprint, fresh mapping resolver,
  and read-only mapping audit.
- `frontend/src/router.ts`: frontend route map.
- `frontend/src/api/client.ts`: typed frontend API wrapper.
- `frontend/src/views/ReviewView.vue`: reveal-first review, rating persistence, focus, and
  reconciliation.
- `frontend/tests/e2e/active-recall.spec.ts`: desktop/mobile active-recall journey and layout checks.
- `frontend/src/i18n/messages.ts`: UI copy.
- `docs/superpowers/plans/2026-07-02-serbian-vocabulary-trainer-mvp.md`: implementation plan.
- `docs/superpowers/specs/2026-08-26-parallel-sdd-execution-design.md`: ownership, waves and merge
  gates for parallel foundation development.
- `docs/progress/parallel-sdd-readiness-2026-08-26.md`: self-review evidence and residual delivery
  risks for the parallel SDD.
- `docs/testing/mvp-manual-test.md`: manual test script.

## Maintenance Instructions for Future Agents

- Read this file, `README.md`, and any task-relevant docs before planning or coding.
- Treat this file as the canonical current-state audit, but verify facts against code when changing behavior.
- Update this file in the same PR/commit when product behavior, architecture, setup, caveats, verification, or deferred scope changes.
- Keep this file factual and concise. Summarize durable product facts; do not turn it into a verbose changelog.
- Before claiming completion on a product-state change, run relevant tests or sanity checks and document what was verified.
