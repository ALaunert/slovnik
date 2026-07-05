# Slovnik Product State

Last audited: 2026-07-05

## Product Summary

Slovnik is a Serbian vocabulary trainer MVP for Russian-speaking learners. It has a FastAPI backend, Postgres persistence, Alembic migrations, and a Vue 3/Vite frontend. The app supports lightweight `userId` profile access, a shared vocabulary pool, per-user learning progress, daily new-word and review sessions, daily and weekly quizzes, weak-word tracking, a password-gated manual vocabulary editor, and Russian/Serbian UI copy.

This audit reflects the code merged in PR #1, "Serbian vocabulary trainer MVP": merge commit `7f99f084347e51212d5e78ff1ebdb0a5b457ea83`, final feature branch head `906d4ec7dcee7befc5703ff7c7714dee7332fb4d`.

## Implemented User-Facing Capabilities

- User entry screen creates or loads a profile by `userId`; the last `userId` and UI language are stored in browser localStorage.
- Dashboard lets a learner change CEFR level, daily new-word count, and UI language.
- Vocabulary list supports CEFR and theme filters, shows Serbian Cyrillic/Latin, Russian translation, level, and theme.
- Editor password unlocks add/edit controls; the editor can create and update vocabulary entries with optional register, stress, notes, examples, and example translations.
- Daily new-word session selects unseen words at the learner's preferred level up to `daily_new_word_count`; completion records per-user progress.
- Review session selects weak words and previously seen/reviewing/learned words that are due, includes weak metadata, and marks reviewed words as `reviewing` unless already `learned`.
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
  - `GET /api/vocabulary`, `GET /api/vocabulary/themes`, `GET /api/vocabulary/{word_id}`, `POST /api/vocabulary`, `PUT /api/vocabulary/{word_id}`, `POST /api/vocabulary/editor/verify`
  - `GET /api/learning/{user_id}/new-words`, `POST /api/learning/{user_id}/new-words/complete`, `GET /api/learning/{user_id}/review`, `POST /api/learning/{user_id}/review/complete`
  - `POST /api/quizzes/{user_id}/start`, `POST /api/quizzes/{user_id}/{attempt_id}/answers`, `GET /api/quizzes/{user_id}/{attempt_id}/questions/{word_id}/{question_type}/answer`, `POST /api/quizzes/{user_id}/{attempt_id}/complete`
- Business logic lives in `backend/app/services/profile_service.py`, `vocabulary_service.py`, `learning_service.py`, and `quiz_service.py`.
- `backend/app/seed.py` seeds three sample A1 words only.

## Frontend Architecture and Routes/Views

- Vue app bootstraps in `frontend/src/main.ts`; routes are defined in `frontend/src/router.ts`.
- Routes: `/`, `/dashboard`, `/vocabulary`, `/new-words`, `/review`, `/quiz`, `/results`, `/editor`, `/editor/:id`.
- API calls are centralized in `frontend/src/api/client.ts`.
- Browser session state is centralized in `frontend/src/stores/session.ts`.
- Route-level views live in `frontend/src/views/`; reusable display components live in `frontend/src/components/`.
- `frontend/src/i18n/messages.ts` contains Russian and Serbian UI strings.

## Data Model and Persistence

- Postgres is the intended local/dev database via `docker-compose.yml`; tests override the DB with in-memory SQLite fixtures.
- Initial migration `20260702_0001_initial_schema.py` creates:
  - `vocabulary_items`: global word content, CEFR level, theme, optional notes/examples, timestamps.
  - `user_profiles`: `user_id`, preferred level, daily new-word count, UI language.
  - `user_word_progress`: per-user word status, seen/quizzed timestamps, correct/incorrect counts, weak status.
  - `quiz_attempts`: user-scoped quiz type, timestamps, score, total questions, serialized question plan.
  - `quiz_answers`: submitted answers per attempt/question.
- Vocabulary content is global; profiles, progress, quiz attempts, answers, and weak-word state are scoped by `user_id`.

## Security/Access Model and Caveats

- `userId` access is not authentication. Anyone who knows a `userId` can load that profile.
- Vocabulary create/update and editor verification use the `X-Editor-Password` header compared directly with `EDITOR_PASSWORD`.
- The editor password is a simple shared secret, not a user account or session system.
- Production startup rejects placeholder editor passwords unless `ENVIRONMENT` is explicitly local/test.
- There is no delete endpoint for vocabulary, no real auth, no roles, no rate limiting, and no CSRF/session hardening.

## Verification and Test Coverage

- Backend verification documented in `README.md`: `cd backend && .venv/bin/ruff check .` and `.venv/bin/pytest -v`.
- Frontend verification documented in `README.md`: `cd frontend && npm run test:unit`, `npm run build`, and `npm run test:e2e`.
- Database rebuild/seed verification is documented in `README.md` with `docker compose up -d postgres`, Alembic downgrade/upgrade, and `python -m app.seed`.
- Backend tests cover health, config validation, schema defaults, profiles, vocabulary, learning sessions, quiz selection/submission/completion, weak-word behavior, repeat limits, and answer reveal.
- Frontend unit tests cover app shell localization, session persistence, dashboard settings/localization, vocabulary API helpers, quiz repeat/self-check behavior, and word editor update flow.
- Playwright e2e currently covers only the basic user-id-to-dashboard path with mocked profile API.
- Manual MVP flow is in `docs/testing/mvp-manual-test.md`.

## Known Limitations / Deferred Scope

- Real authentication and authorization are deferred.
- Native mobile apps, audio pronunciation, bulk import, social features, payments, AI generation, and advanced spaced repetition are not implemented.
- Weekly quiz uses calendar-week selection plus weak words, not a full scheduling system.
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
- `frontend/src/router.ts`: frontend route map.
- `frontend/src/api/client.ts`: typed frontend API wrapper.
- `frontend/src/views/`: user-facing workflows.
- `frontend/src/i18n/messages.ts`: UI copy.
- `docs/superpowers/plans/2026-07-02-serbian-vocabulary-trainer-mvp.md`: implementation plan.
- `docs/testing/mvp-manual-test.md`: manual test script.

## Maintenance Instructions for Future Agents

- Read this file, `README.md`, and any task-relevant docs before planning or coding.
- Treat this file as the canonical current-state audit, but verify facts against code when changing behavior.
- Update this file in the same PR/commit when product behavior, architecture, setup, caveats, verification, or deferred scope changes.
- Keep this file factual and concise. Summarize durable product facts; do not turn it into a verbose changelog.
- Before claiming completion on a product-state change, run relevant tests or sanity checks and document what was verified.
