# Slovnik

Serbian vocabulary trainer MVP.

## Local Development

1. Copy `.env.example` to `.env`.
2. Start Postgres: `docker compose up -d postgres`.
3. Start backend: `cd backend && uvicorn app.main:app --reload`.
4. Start frontend: `cd frontend && npm install && npm run dev`.
5. Check backend: `curl http://localhost:8000/api/health`.
