# Learner Local Days Implementation Plan

> For agentic workers: use superpowers:executing-plans inline, preserving the dirty shared checkout.

**Goal:** Implement P2-03 local-day semantics without resetting consumed written quota.
**Architecture:** Pure day/window utility plus additive profile fields; callers use one locked profile
and post-lock clock for writes. Existing due instants and snapshots remain immutable.
**Tech Stack:** Python zoneinfo, SQLAlchemy/Alembic, FastAPI, Vue/TypeScript.
**Spec:** ../specs/2026-10-01-learner-local-days-design.md

## Global Constraints

UTC fallback; no automatic zone detection; requested change never shortens active allocation;
no auth scope; legacy new-word count remains batch size; no timestamp backfill or minute forecast.

## Review Focus

- Invalid IANA keys and missing timezone data: reject before persistence; bundle tzdata.
- Repeated/pending changes: idempotency and no quota reset, including date-line travel.
- Gap/fold midnight and skipped date: first existing boundary, half-open UTC windows.
- Stale profile after lock wait: refresh locked row and obtain database clock afterwards.
- Display/server disagreement: all review paths and reports share the same boundaries.

## Task 1: Calendar/profile contract

Files: app/learner_time.py, models.py, schemas.py, services/profile_service.py,
routers/profiles.py, alembic/versions/20261001_0006_learner_timezone.py, pyproject.toml,
tests/test_learner_time.py, tests/test_profiles.py, tests/test_migrations.py.
Interfaces: day_window(now, zone), allocation_window(profile, now), request_timezone(profile, zone, now).
- [x] Write failing DST/midnight/travel/profile/migration assertions; run focused pytest.
- [x] Implement utility and additive fields/migration, validated profile read/update.
- [x] Run focused tests; review window/locking decisions.

## Task 2: Product integration

Files: services/learning_service.py, quiz_service.py, local_workload.py, local_practice_service.py;
frontend api/client.ts, DashboardView.vue, PracticeView.vue, i18n/messages.ts and corresponding tests.
- [x] Write failing review/calendar/quota/parallel and frontend form/reset tests; observe RED.
- [x] Integrate effective calendar and exact allocation report/snapshot; preserve legacy semantics.
- [x] Run focused backend/frontend checks, PostgreSQL races, real browser test.

## Task 3: Verification and documentation

Files: docs/product-state.md, docs/learning/implementation-plan.md, local-written-practice.md, README.md.
- [x] Independent Astra review; fix findings with regressions.
- [x] Run full PostgreSQL/backend/browser, frontend unit/type/build/e2e and Ruff/diff check.
- [x] Update durable audit with actual results and unmeasured human workload limitation.
No commit/staging: workspace includes existing user changes.
