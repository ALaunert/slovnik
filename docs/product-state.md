# Slovnik Product State

Last audited: 2026-08-26 (runtime implementation last verified: 2026-07-25)

## Product Summary

Slovnik is a Serbian vocabulary trainer MVP for Russian-speaking learners. It has a FastAPI backend, Postgres persistence, Alembic migrations, and a Vue 3/Vite frontend. The app supports lightweight `userId` profile access, a shared vocabulary pool, per-user learning progress, daily new-word and review sessions, daily and weekly quizzes, weak-word tracking, a password-gated vocabulary editor with manual and AI-assisted fill, and Russian/Serbian UI copy.

This audit reflects the current product implementation, including AI vocabulary fill and
reveal-first active recall, built on the MVP delivered in PR #1, "Serbian vocabulary trainer MVP."

## Approved Design Direction (Not Implemented)

- On 2026-08-26, Domain Model v0.1 was approved for evolving Slovnik from separate vocabulary,
  review, and quiz modes into an adaptive language-learning assistant.
- The approved direction is a modular monolith with four bounded contexts: Language Catalog,
  Curriculum, Practice & History, and Learner Progress. The next-activity orchestrator combines
  curriculum constraints, learner evidence, and memory risk; it is not an AI chat agent.
- AI may later provide candidate exercises or evaluate ambiguous answers through replaceable ports.
  It cannot own curriculum progression, select learning truth, or update learner state directly.
- The runtime implementation described below has not yet migrated to this model. `VocabularyItem`,
  `UserWordProgress`, the existing review scheduler, quizzes, routes, and APIs remain unchanged.
- The approved design and its explicit deferred log are in
  `docs/superpowers/specs/2026-08-26-domain-model-v0.1-design.md` and
  `docs/progress/domain-model-v0.1.md`.
- A formally accepted ADR and an accepted backend-only foundation SDD were added on 2026-08-26. They
  remain design artifacts: no migrations, domain runtime, public APIs, or UI changes have been implemented.
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

- Postgres is the intended local/dev database via `docker-compose.yml`; tests override the DB with in-memory SQLite fixtures.
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
- There is no delete endpoint for vocabulary, no real auth, no roles, no rate limiting, and no CSRF/session hardening.

## Verification and Test Coverage

- Backend verification documented in `README.md`: `cd backend && .venv/bin/ruff check .` and `.venv/bin/pytest -v`.
- Backend editable installation is verified with `.venv/bin/python -m pip install -e ".[dev]"`;
  setuptools discovers only `app*`, and the dev dependency remains on Ruff `0.6.x`.
- Frontend verification documented in `README.md`: `cd frontend && npm run test:unit`, `npm run build`, and `npm run test:e2e`.
- Database rebuild/seed verification is documented in `README.md` with `docker compose up -d postgres`, Alembic downgrade/upgrade, and `python -m app.seed`.
- Backend tests cover health, config validation, schema defaults, profiles, vocabulary, learning
  sessions, SQL due filtering/order/cap, every interval transition and cap, row-lock serialization,
  precise status reconciliation, quiz schedule reset, compatibility batch scheduling, quiz
  selection/submission/completion, weak-word behavior, repeat limits, and answer reveal.
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
- Verified on 2026-07-25: backend Ruff passed; PostgreSQL-enabled backend tests passed with `221 passed`;
  frontend unit tests passed with `83 passed`; the production build passed; and all six Playwright
  tests passed.
- Manual MVP flow is in `docs/testing/mvp-manual-test.md`.

## Known Limitations / Deferred Scope

- Real authentication and authorization are deferred.
- Native mobile apps, audio pronunciation, bulk import, social features, and payments are not implemented.
- The current deterministic scheduler does not retain review events or fit FSRS parameters.
  Review-history analytics, desired-retention controls, and workload forecasting remain deferred.
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
- `docker-compose.yml`: local Postgres service.
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
- `backend/app/services/learning_service.py`: due query, interval transitions, row locking, and
  compatibility review completion.
- `backend/app/services/quiz_service.py`: incorrect-quiz schedule reset.
- `frontend/src/router.ts`: frontend route map.
- `frontend/src/api/client.ts`: typed frontend API wrapper.
- `frontend/src/views/ReviewView.vue`: reveal-first review, rating persistence, focus, and
  reconciliation.
- `frontend/tests/e2e/active-recall.spec.ts`: desktop/mobile active-recall journey and layout checks.
- `frontend/src/i18n/messages.ts`: UI copy.
- `docs/superpowers/plans/2026-07-02-serbian-vocabulary-trainer-mvp.md`: implementation plan.
- `docs/testing/mvp-manual-test.md`: manual test script.

## Maintenance Instructions for Future Agents

- Read this file, `README.md`, and any task-relevant docs before planning or coding.
- Treat this file as the canonical current-state audit, but verify facts against code when changing behavior.
- Update this file in the same PR/commit when product behavior, architecture, setup, caveats, verification, or deferred scope changes.
- Keep this file factual and concise. Summarize durable product facts; do not turn it into a verbose changelog.
- Before claiming completion on a product-state change, run relevant tests or sanity checks and document what was verified.
