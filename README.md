# Slovnik

Serbian vocabulary trainer MVP with a FastAPI backend, Postgres persistence, and a Vue 3 frontend.

## Local Development

1. Copy `.env.example` to `.env`; keep `ENVIRONMENT=development` locally.
2. Install backend dependencies: `cd backend && python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"`.
3. Install frontend dependencies: `cd frontend && npm install`.
4. Start Postgres: `docker compose up -d postgres`.
5. Run migrations: `cd backend && .venv/bin/alembic upgrade head`.
6. Seed sample words: `cd backend && .venv/bin/python -m app.seed`.
7. Start backend: `cd backend && .venv/bin/uvicorn app.main:app --reload`.
8. Start frontend: `cd frontend && npm run dev`.
9. Check backend: `curl http://localhost:8000/api/health`.

If local port `5432` is busy, set `POSTGRES_PORT` and update `DATABASE_URL` in `.env`, for example `POSTGRES_PORT=55432` and `DATABASE_URL=postgresql+psycopg://slovnik:slovnik@localhost:55432/slovnik`.

After pulling changes, run `cd backend && .venv/bin/alembic upgrade head` before starting the app. Backend setup uses the supported editable install command shown above.

For production deployments, set `ENVIRONMENT=production` and replace `EDITOR_PASSWORD` with a non-placeholder secret before starting the backend. Placeholder editor passwords are accepted only for explicit local/test environments.

## AI Vocabulary Fill

AI fill appears only after the vocabulary editor password is verified. Set `OPENAI_API_KEY` in the backend environment to enable new generation; the key remains backend-only and must never be added to frontend variables or browser code. `OPENAI_MODEL` is configurable and defaults to `gpt-5.6-luna`; `OPENAI_TIMEOUT_SECONDS` defaults to `20`.

`POST /api/vocabulary/ai-fill` accepts one Serbian word and the editor password header. It uses a strict key normalized with Unicode NFC, trimming, and case folding. The backend checks existing vocabulary first, then the persistent generation store, and calls OpenAI only when neither has a match. Stored drafts are reused and v1 has no regenerate action. Valid partial drafts are allowed; failed, timed-out, or invalid generations are not cached.

Structured stress stores aligned Cyrillic and Latin syllables plus one stressed-syllable index. The editor preview, vocabulary list, and new-word/review cards emphasize the full stressed syllable. When structured stress is absent, the legacy `stress_marker` remains visible as metadata without inferred emphasis.

## Verification

Backend:

```bash
cd backend
.venv/bin/ruff check .
.venv/bin/pytest -v
```

Frontend:

```bash
cd frontend
npm run test:unit
npm run build
npm run test:e2e
```

Database rebuild and seed:

```bash
docker compose up -d postgres
cd backend
.venv/bin/alembic downgrade base
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed
```

## MVP Access Caveat

The `userId` flow is lightweight profile access for the MVP. It is not secure authentication, and anyone who knows a `userId` can load that profile until real auth is added.
