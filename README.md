# Slovnik

Serbian vocabulary trainer MVP with a FastAPI backend, Postgres persistence, and a Vue 3 frontend.

## Local Development

1. Copy `.env.example` to `.env` and keep `ENVIRONMENT=development` for local use.
2. Start the development stack: `docker compose up -d --build`.
3. Open `http://localhost:5173`.
4. Check the API: `curl http://localhost:8000/api/health`.

Compose starts PostgreSQL, runs Alembic migrations before the FastAPI server starts, and serves the Vue/Vite frontend with source reload. It does not seed vocabulary automatically. To add the three sample words explicitly, run `docker compose exec backend python -m app.seed`.

Use `docker compose logs -f backend frontend` to follow app logs and `docker compose down` to stop the stack while keeping database and frontend dependency volumes. After changing frontend npm dependencies, run `docker compose run --rm frontend npm ci` to update the persisted `node_modules` volume. Rebuild images with `docker compose up -d --build` after changing Dockerfiles or package installation inputs.

If local port `5432` is busy, set `POSTGRES_PORT` in `.env`; the backend container still connects to PostgreSQL on the internal `postgres:5432` address. `VITE_API_BASE_URL` defaults to the browser-facing `http://localhost:8000` and may be overridden in `.env`. The frontend container receives only this URL and its file-watcher setting, not backend secrets.

### Host-run alternative

1. Copy `.env.example` to `.env`; keep `ENVIRONMENT=development` locally.
2. Install backend dependencies: `cd backend && python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"`.
3. Install frontend dependencies: `cd frontend && npm install`.
4. Start Postgres: `docker compose up -d postgres`.
5. Run migrations: `cd backend && .venv/bin/alembic upgrade head`.
6. Seed sample words if wanted: `cd backend && .venv/bin/python -m app.seed`.
7. Start backend: `cd backend && .venv/bin/uvicorn app.main:app --reload`.
8. Start frontend: `cd frontend && npm run dev`.
9. Check backend: `curl http://localhost:8000/api/health`.

When using a nondefault `POSTGRES_PORT` with the host-run backend, also update the host-oriented `DATABASE_URL` in `.env`, for example `POSTGRES_PORT=55432` and `DATABASE_URL=postgresql+psycopg://slovnik:slovnik@localhost:55432/slovnik`. After pulling changes, run the host Alembic upgrade before starting the host-run app.

For production deployments, set `ENVIRONMENT=production` and replace `EDITOR_PASSWORD` with a non-placeholder secret before starting the backend. Placeholder editor passwords are accepted only for explicit local/test environments.

## AI Vocabulary Fill

AI fill appears only after the vocabulary editor password is verified. Set `OPENAI_API_KEY` in the backend environment to enable new generation; the key remains backend-only and must never be added to frontend variables or browser code. `OPENAI_MODEL` is configurable and defaults to `gpt-5.6-luna`; `OPENAI_TIMEOUT_SECONDS` defaults to `20`.

`POST /api/vocabulary/ai-fill` accepts one Serbian word and the editor password header. It uses a strict key normalized with Unicode NFC, trimming, and case folding. The backend checks existing vocabulary first, then the persistent generation store, and calls OpenAI only when neither has a match. Stored drafts are reused and v1 has no regenerate action. Valid partial drafts are allowed; failed, timed-out, or invalid generations are not cached.

Concurrent requests for the same normalized word share one provider call through an expiring database reservation. Lease timestamps use the database clock, acquisition is bounded by database lock/statement timeouts derived from a monotonic request deadline, and a heartbeat renews the lease in short independent transactions through validation and fenced persistence/release. Provider failures release the reservation, expired reservations can be reclaimed after a worker crash, and waiters return a stable `503` after a bounded wait. The request session holds no open transaction during the OpenAI call.

Structured stress stores aligned Cyrillic and Latin syllables plus one stressed-syllable index. The editor preview, vocabulary list, and new-word/review cards emphasize the full stressed syllable. When structured stress is absent, the legacy `stress_marker` remains visible as metadata without inferred emphasis.

## Language-assistant shadow audit

Catalog bootstrap is creation-only and records a fingerprint of each source `VocabularyItem`; shadow learning and quiz writes reject missing, ambiguous, or stale mappings before evidence is stored. Audit mappings without changing data:

```bash
cd backend
.venv/bin/python -m app.catalog_audit
```

The output contains only legacy word IDs grouped as `missing`, `stale`, or `ambiguous`. The audit does not rewrite published content.

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
