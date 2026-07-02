# Slovnik

Serbian vocabulary trainer MVP with a FastAPI backend, Postgres persistence, and a Vue 3 frontend.

## Local Development

1. Copy `.env.example` to `.env`.
2. Install backend dependencies: `cd backend && python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"`.
3. Install frontend dependencies: `cd frontend && npm install`.
4. Start Postgres: `docker compose up -d postgres`.
5. Run migrations: `cd backend && .venv/bin/alembic upgrade head`.
6. Seed sample words: `cd backend && .venv/bin/python -m app.seed`.
7. Start backend: `cd backend && .venv/bin/uvicorn app.main:app --reload`.
8. Start frontend: `cd frontend && npm run dev`.
9. Check backend: `curl http://localhost:8000/api/health`.

If local port `5432` is busy, set `POSTGRES_PORT` and update `DATABASE_URL` in `.env`, for example `POSTGRES_PORT=55432` and `DATABASE_URL=postgresql+psycopg://slovnik:slovnik@localhost:55432/slovnik`.

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
