# Docker Compose Development Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start PostgreSQL, FastAPI, and Vue/Vite with live reload and automatic Alembic upgrades through one Docker Compose command, while keeping seed manual.

**Architecture:** PostgreSQL retains its named volume and gains a readiness check. The backend container receives `.env` values, overrides the host database address with `postgres:5432`, migrates, then starts Uvicorn. The frontend container serves Vite with a source bind mount and container-owned `node_modules`; only the browser-facing API URL enters its environment.

**Tech Stack:** Docker Compose, Python 3.12, FastAPI/Uvicorn, Alembic, PostgreSQL 16, Node 22, Vue 3/Vite.

**Spec:** `docs/superpowers/specs/2026-09-24-docker-compose-dev-stack-design.md`

## Global Constraints

- Default command: `docker compose up -d --build` starts the development stack with live reload.
- Published ports are 8000 for FastAPI and 5173 for Vite; PostgreSQL keeps `${POSTGRES_PORT:-5432}:5432`.
- Backend uses `postgres:5432` internally; the browser uses `http://localhost:8000` by default.
- `alembic upgrade head` completes before Uvicorn starts. Migration failure must prevent API startup.
- Seed runs only through `docker compose exec backend python -m app.seed`.
- Preserve the existing host-run workflow and update `docs/product-state.md` with durable setup and verification facts.
- Preserve unrelated files and stage only files named in this plan.

## File Map

- `docker-compose.yml`: service wiring, readiness, ports, bind mounts, environment, startup order, and the frontend dependency volume.
- `backend/Dockerfile` and `backend/.dockerignore`: backend image and build context exclusions.
- `frontend/Dockerfile` and `frontend/.dockerignore`: frontend image, npm lockfile installation, and build context exclusions.
- `README.md`: Compose and host development workflows plus manual seed and verification commands.
- `docs/product-state.md`: canonical audit of the changed development setup and observed verification.

## Review Focus

1. A host `.env` whose `DATABASE_URL` says `localhost` still connects from backend to `postgres:5432` — exercise with Compose configuration and the running API.
2. A slow PostgreSQL start does not race Alembic — exercise with a fresh named volume and inspect backend logs/current revision.
3. A failed migration does not start Uvicorn — verify the command's `&&` ordering in effective Compose configuration and a successful migration-before-listener runtime log.
4. Frontend source edits reload and frontend never receives `OPENAI_API_KEY` or `EDITOR_PASSWORD` — inspect its effective environment and probe a changed source file through Vite.
5. Repeated `compose up` does not load sample words — compare vocabulary count before and after restart, then run manual seed explicitly.

---

### Task 1: Backend image, database readiness, and migration-gated API

**Files:**
- Create: `backend/Dockerfile`, `backend/.dockerignore`
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: root `.env` based on `.env.example`; `backend/pyproject.toml`; `backend/alembic.ini`; `backend/app/config.py`.
- Produces: `backend` Compose service on port 8000 with database URL `postgresql+psycopg://slovnik:slovnik@postgres:5432/slovnik` and a successful Alembic upgrade before Uvicorn.

- [ ] **Step 1: Record the failing baseline.** Run `docker compose config --services` (only `postgres` should appear), and `docker compose config --format json | python3 -c 'import json,sys; c=json.load(sys.stdin); assert "backend" in c["services"]'` (should fail). Do not print the full effective configuration because it can contain secrets.
- [ ] **Step 2: Add `backend/Dockerfile`.** Use this content:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
```

- [ ] **Step 3: Add `backend/.dockerignore`.** Exclude `.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `*.pyc`, `.env`, and `.env.*`. Keep `alembic/`, `alembic.ini`, `app/`, and `pyproject.toml` in the build context.
- [ ] **Step 4: Extend Compose.** Add `postgres.healthcheck` using `pg_isready -U slovnik -d slovnik`; add `backend` with `build: ./backend`, `env_file: .env`, `DATABASE_URL: postgresql+psycopg://slovnik:slovnik@postgres:5432/slovnik`, `WATCHFILES_FORCE_POLLING: "true"`, `./backend:/app`, `8000:8000`, and `depends_on.postgres.condition: service_healthy`. Its command is:

```yaml
command: >
  sh -c "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
```

- [ ] **Step 5: Validate and run.** `docker compose config --quiet` and the Step 1 assertion should pass. Run `docker compose up -d --build postgres backend`, `docker compose exec -T backend alembic current`, `curl --fail http://localhost:8000/api/health`, and `docker compose logs backend --tail=80`. The migration revision must equal the repository head, and the logs must show migration before Uvicorn startup. Inspect `docker compose config --format json` programmatically to assert the effective backend database URL is the service URL, without printing other environment values.
- [ ] **Step 6: Commit only this task's files.** Stage `backend/Dockerfile`, `backend/.dockerignore`, and `docker-compose.yml`; commit as `feat: run backend and migrations in Docker Compose`.

### Task 2: Frontend image, full-stack smoke checks, and setup documentation

**Files:**
- Create: `frontend/Dockerfile`, `frontend/.dockerignore`
- Modify: `docker-compose.yml`, `README.md`, `docs/product-state.md`

**Interfaces:**
- Consumes: the `backend` Compose service from Task 1 and `frontend/package-lock.json`.
- Produces: `frontend` Compose service on port 5173, with `VITE_API_BASE_URL` defaulting to `http://localhost:8000` and no backend secrets.

- [ ] **Step 1: Record the failing baseline.** `docker compose config --format json | python3 -c 'import json,sys; c=json.load(sys.stdin); assert "frontend" in c["services"]'` should fail.
- [ ] **Step 2: Add `frontend/Dockerfile`.** Use this content:

```dockerfile
FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
CMD ["npm", "run", "dev"]
```

- [ ] **Step 3: Add `frontend/.dockerignore`.** Exclude `node_modules`, `dist`, `coverage`, `test-results`, `playwright-report`, `.env`, and `.env.*`. Keep the lockfile and Vite sources in the context.
- [ ] **Step 4: Extend Compose.** Add `frontend` with `build: ./frontend`, `./frontend:/app`, a named `frontend_node_modules:/app/node_modules` volume, `5173:5173`, `CHOKIDAR_USEPOLLING: "true"`, and `VITE_API_BASE_URL: ${VITE_API_BASE_URL:-http://localhost:8000}`. It may depend on `backend` starting, but should not receive `env_file: .env`. Declare `frontend_node_modules` under top-level volumes.
- [ ] **Step 5: Update docs.** README should begin local setup with copying `.env.example` to `.env`, then `docker compose up -d --build`, `http://localhost:5173`, and `curl http://localhost:8000/api/health`. Document automatic migration, manual `docker compose exec backend python -m app.seed`, `docker compose logs -f backend frontend`, `docker compose down` (without `-v`), and the existing host-run alternative. Explain that changing frontend npm dependencies requires `docker compose run --rm frontend npm ci` for the persisted dependency volume. Update the setup, verification, and source-file descriptions in `docs/product-state.md` with observed checks only.
- [ ] **Step 6: Validate full stack.** Run `docker compose config --quiet`, `docker compose up -d --build`, `docker compose ps`, `docker compose exec -T backend alembic current`, `curl --fail http://localhost:8000/api/health`, and `curl --fail http://localhost:5173/`. Parse `docker compose config --format json` to assert frontend environment keys include only `VITE_API_BASE_URL` and `CHOKIDAR_USEPOLLING`, and backend database URL points at `postgres`. Check a temporary Vue source edit causes Vite to serve updated content, then restore the file. Compare vocabulary counts across a backend restart to confirm no automatic seed; run manual seed only if the test database is disposable or already used for sample data. Run `cd backend && .venv/bin/ruff check .` and `cd frontend && npm run build` if local dependencies are available.
- [ ] **Step 7: Review and commit.** Run `git diff --check`, inspect changed files and `git status --short`, then stage `frontend/Dockerfile`, `frontend/.dockerignore`, `docker-compose.yml`, `README.md`, and `docs/product-state.md`. Commit as `feat: launch full dev stack with Docker Compose`.

### Task 3: Final verification and review

**Files:** None unless a check reveals a defect; in that case update the owning task's files and the product-state verification note.

**Interfaces:**
- Consumes: completed Compose stack and documentation.
- Produces: verified build/startup results and a concise report of any Docker daemon limitation.

- [ ] **Step 1: Re-run the full command.** `docker compose up -d --build`, then check `docker compose ps`, API health, frontend HTML, and `alembic current`. Confirm `docker compose up -d` without `--build` also starts existing images.
- [ ] **Step 2: Review the branch.** Compare `git diff main...HEAD`, run `git diff --check`, and verify the docs reflect the observed behavior and seed policy. Fix concrete defects, commit only their related files, and report the exact checks performed.
