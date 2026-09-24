# Docker Compose development stack

## Goal

Make `docker compose up -d --build` start the local Slovnik development stack: PostgreSQL, FastAPI, and Vue/Vite. Python and Vue source edits should appear through live reload. Database schema upgrades should finish before the API serves requests. The three sample words and pilot curriculum seed remain an explicit, manual action.

## Scope and interface

- The existing `postgres` service and named data volume remain the development database. Compose adds `backend` and `frontend` services, publishing ports 8000 and 5173.
- A backend Dockerfile installs the Python application and Alembic dependencies. A frontend Dockerfile installs the npm lockfile dependencies. Docker ignore files keep host virtual environments, `node_modules`, build output, and local secrets out of image build contexts.
- Compose bind-mounts source directories for development. Container-local dependency locations remain available despite those mounts. Backend runs Uvicorn with reload; frontend runs the existing Vite dev script. File watchers use polling where Docker Desktop bind mounts need it.
- Compose reads the root `.env` for backend settings. The container's `DATABASE_URL` overrides the host-oriented value with the `postgres` service address and internal port 5432. The backend settings file's relative `../.env` path is not needed in the container because Compose supplies environment variables. The frontend receives only `VITE_API_BASE_URL`, whose browser-facing default is `http://localhost:8000`; it never receives backend secrets.

## Startup and data flow

1. PostgreSQL starts and passes a `pg_isready` healthcheck.
2. Backend waits for that healthcheck, runs `alembic upgrade head`, then starts Uvicorn on `0.0.0.0:8000` with reload. A migration failure stops backend startup rather than serving against an outdated schema.
3. Frontend starts Vite on `0.0.0.0:5173`. The browser uses the published API port and existing CORS origin.
4. Seed is run only on request with `docker compose exec backend python -m app.seed`. Repeated stack starts do not add sample data.

The Compose setup targets local development. It does not add a production image, static frontend server, authentication, or a new database password scheme.

## Documentation and verification

README will make the Compose workflow the one-command local path and retain the existing host-run workflow as an alternative. It will document `.env` setup, the browser and API URLs, the manual seed command, migration behavior, and relevant commands for rebuild, logs, and shutdown. `docs/product-state.md` will record the durable setup and verification change.

Verify Compose configuration, image builds, stack startup, current Alembic revision, API health, and the Vite page. Run focused backend/frontend checks for changes that affect their startup or build. The verification report must distinguish completed runtime checks from anything blocked by Docker daemon access.
