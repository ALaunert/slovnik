# Language Assistant WS-A Catalog and Curriculum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Project execution override:** Execute one task at a time in `/Users/launert/projects/slovnik-worktrees/ws-a` through a fresh Codex agent using `superpowers:test-driven-development`; stop for INT review after every task.

**Goal:** Implement Language Catalog and Curriculum foundations, publication/frontier policy, and an idempotent technical A1 pilot without touching shared contracts or integration-owned files.

**Architecture:** Pure dataclass/enum aggregates are separated from SQLAlchemy mappings and Session-based repositories. Catalog bootstraps stable mappings from legacy vocabulary; Curriculum owns immutable graph publication and readiness based only on frozen target/progress contracts.

**Tech Stack:** Python standard-library domain types, SQLAlchemy 2, pytest, Ruff

---

**Allowed owner paths:** `backend/app/domain/{catalog,curriculum,curriculum_policy}.py`, `backend/app/domain_models/{catalog,curriculum}.py`, `backend/app/repositories/{catalog,curriculum}.py`, `backend/app/services/{domain_bootstrap_service,curriculum_service}.py`, `backend/app/seed.py`, `backend/tests/{test_domain_catalog,test_curriculum_contracts,test_curriculum}.py`.

**Forbidden shared paths:** `domain/__init__.py`, `domain/shared.py`, `domain/target.py`, package registries, migration, `db.py`, Alembic env, shared fixtures, WS-B/WS-C paths, progress docs, frontend. Import DTO-01 through its frozen public path.

Run commands from `/Users/launert/projects/slovnik-worktrees/ws-a/backend` with `/Users/launert/projects/slovnik/backend/.venv/bin/*`.

**Mandatory microcycle:** Every behavior/assertion listed below is a separate 2–5 minute RED → GREEN → REFACTOR loop using the exact task pytest command. Add one assertion, run and record RED, add minimum code, rerun the identical command GREEN, make one cleanup, rerun GREEN, then start the next assertion. P3.T3 uses a temporary probe because its normative changeset contains no test file.

### Task 1: P1.T3 — Language Catalog foundation

**Canonical references:** P1.T3 changeset; SQL-01 Catalog tables; Domain Model §§5.1–5.2, invariants 1–5a.

**Files:**
- Create: `backend/app/domain/catalog.py`
- Create: `backend/app/domain_models/catalog.py`
- Create: `backend/app/repositories/catalog.py`
- Create: `backend/app/services/domain_bootstrap_service.py`
- Test: `backend/tests/test_domain_catalog.py`

- [ ] **Step 1: RED — aggregate invariants.** Test `LexicalUnit` requires at least one Sense and written Form for publication, stable IDs are canonical lowercase UUID strings, status/revision transitions are valid, Serbian Cyrillic/Latin orthographies are present, and incomplete content remains draft. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_domain_catalog.py`; expect missing imports.
- [ ] **Step 2: GREEN then REFACTOR — pure aggregate.** Implement only the minimum value for the current failing assertion, rerun `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_domain_catalog.py` GREEN, then make one cleanup and rerun the identical command GREEN before the next assertion.
- [ ] **Step 3: RED — ORM parity and repository boundary.** Add SQLite repository tests for SQL-01 Catalog columns/relations, JSON `None` behavior, stable mapping lookup by legacy ID, and return of domain values rather than ORM objects. Expect missing mapping/repository failures.
- [ ] **Step 4: GREEN then REFACTOR — mappings/repository.** Implement the minimum mapping/repository behavior, rerun the exact `tests/test_domain_catalog.py` command GREEN, then refactor one mapper and rerun it.
- [ ] **Step 5: RED — bootstrap preservation/idempotency.** Seed valid, structured-stress, legacy-marker, MWE-like, and partial legacy vocabulary; assert two runs keep IDs/bytes stable, preserve scripts/stress/examples/CEFR/theme metadata, conservatively classify ambiguity, publish only valid content, and create no learning events. Expect missing service behavior.
- [ ] **Step 6: GREEN then REFACTOR — deterministic bootstrap.** Implement one failing bootstrap behavior at a time, rerun the exact Catalog test command GREEN, then refactor one helper and rerun it. Never infer morphology or synthetic history.
- [ ] **Step 7: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_domain_catalog.py`, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/domain/catalog.py app/domain_models/catalog.py app/repositories/catalog.py app/services/domain_bootstrap_service.py tests/test_domain_catalog.py`, `git diff --check`, `git diff --name-only HEAD | sort`; output must be a subset of the five P1.T3 files. Commit: `feat(P1.T3): add language catalog foundation`.

### Task 2: P1.T4 — Curriculum foundation

**Canonical references:** DTO-01 and SQL-01 in P1; publication/frontier is deliberately deferred to P3.T1.

**Files:**
- Create: `backend/app/domain/curriculum.py`
- Create: `backend/app/domain_models/curriculum.py`
- Create: `backend/app/repositories/curriculum.py`
- Test: `backend/tests/test_curriculum_contracts.py`

- [ ] **Step 1: RED — draft aggregate shape.** Test draft version identity/code/version, bounded priority/outcome format, one target key per version, edge endpoint ownership, no self-edge, and one edge kind per pair. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_curriculum_contracts.py`; expect missing types.
- [ ] **Step 2: GREEN then REFACTOR — pure draft graph.** Implement one failing graph assertion, rerun `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_curriculum_contracts.py` GREEN, then clean one helper and rerun it.
- [ ] **Step 3: RED — lifecycle boundaries.** Test draft cannot masquerade as active/retired, graph/content mutation is rejected after publication snapshot, and only eventual active→retired lifecycle shape is representable. Expect missing validation.
- [ ] **Step 4: GREEN then REFACTOR — lifecycle minimum.** Add the minimum lifecycle guard, rerun the exact Curriculum contract command GREEN, then refactor one error helper and rerun it.
- [ ] **Step 5: RED — repository round trip.** Test draft graph storage/read with fake target resolver, composite same-version edges, JSON conditions, and no implicit publication. Expect missing repository/mapping behavior.
- [ ] **Step 6: GREEN then REFACTOR — ORM/repository.** Implement one failing repository behavior, rerun the exact contract command GREEN, then refactor one mapper and rerun it.
- [ ] **Step 7: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_curriculum_contracts.py`, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/domain/curriculum.py app/domain_models/curriculum.py app/repositories/curriculum.py tests/test_curriculum_contracts.py`, `git diff --check`, `git diff --name-only HEAD | sort`; output must be a subset of the four P1.T4 files. Commit: `feat(P1.T4): add curriculum foundation`.

### Task 3: P3.T1 — Curriculum publication and frontier policy

**Canonical references:** P3.T1 and Domain Model Curriculum invariants; use frozen progress view/ports, never WS-C repository internals.

**Files:**
- Modify: `backend/app/domain/curriculum.py`
- Create: `backend/app/domain/curriculum_policy.py`
- Modify: `backend/app/repositories/curriculum.py`
- Create: `backend/app/services/curriculum_service.py`
- Test: `backend/tests/test_curriculum.py`

- [ ] **Step 1: RED — publication validation.** Add tests for missing/unpublished/retired target, duplicate node, invalid outcome/priority, cross-version/self/double-kind edge, and HARD cycle; include a SOFT cycle that is valid. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_curriculum.py`; expect missing publication behavior.
- [ ] **Step 2: GREEN then REFACTOR — pure validation.** Implement one failing validation rule, rerun `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_curriculum.py` GREEN, then refactor one graph helper and rerun it.
- [ ] **Step 3: RED — activation lifecycle.** Test publication timestamps/status, published graph immutability, activating v2 retires v1 atomically, historical v1 remains readable, and retirement of active-referenced content is rejected until replacement activation. Expect lifecycle failures.
- [ ] **Step 4: GREEN then REFACTOR — transactional publication.** Implement one lifecycle assertion, rerun the exact Curriculum test command GREEN, then refactor one transaction helper and rerun it.
- [ ] **Step 5: RED — concurrent one-active invariant.** Add PostgreSQL two-session barrier tests for two replacements and two first publications. Expect one winner/one active row and stable loser handling.
- [ ] **Step 6: GREEN — concurrency root cause only.** Correct locking/IntegrityError translation without sleeps, global locks, or weakening the index.
- [ ] **Step 7: RED — frontier readiness.** Add one assertion at a time for missing/legacy-only state, deterministic peak ≥0.6, later failure/overdue memory, HARD, SOFT, and CEFR envelope; run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_curriculum.py` and record each RED.
- [ ] **Step 8: GREEN then REFACTOR — pure frontier.** Implement one failing decision, rerun the exact command GREEN, then refactor one policy helper and rerun it.
- [ ] **Step 9: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_curriculum.py`, `SLOVNIK_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://slovnik:slovnik@localhost:5432/postgres' /Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_curriculum.py -k 'postgresql and concurrent'`, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/domain/curriculum.py app/domain/curriculum_policy.py app/repositories/curriculum.py app/services/curriculum_service.py tests/test_curriculum.py`, `git diff --check`, `git diff --name-only HEAD | sort`. Commit: `feat(P3.T1): publish curriculum and compute frontier`.

### Task 4: P3.T3 — Technical A1 pilot bootstrap

**Canonical references:** P3.T3; DTO-01/ALG-01; curated-content deferred gate in `docs/progress/domain-model-v0.1.md`.

**Files:**
- Modify: `backend/app/services/domain_bootstrap_service.py`
- Modify: `backend/app/services/curriculum_service.py`
- Modify: `backend/app/seed.py`

- [ ] **Step 1: Temporary RED probe.** Create `/private/tmp/slovnik-p3-t3/test_p3_t3.py`. Add one assertion at a time for pilot identity, two Sense capabilities, distinct target keys/same Sense (neither node targets Form), idempotent stable IDs, explicit HARD/SOFT edges, invalid Construction all-draft behavior, unchanged three legacy seed rows, and no A2–C2 generation. Run `cd /Users/launert/projects/slovnik-worktrees/ws-a/backend && PYTHONPATH=. /Users/launert/projects/slovnik/backend/.venv/bin/pytest -v /private/tmp/slovnik-p3-t3/test_p3_t3.py`; record each RED. Citation Form belongs to the later WS-C ActivitySpec snapshot and is verified in P3.T2/P3.T4, not stored by this task.
- [ ] **Step 2: GREEN then REFACTOR.** For each probe assertion add minimum code only in the three P3.T3 files, rerun the identical command GREEN, then make one cleanup and rerun GREEN. Never infer edges or call AI.
- [ ] **Step 3: Durable regression.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_domain_catalog.py tests/test_curriculum.py tests/test_curriculum_contracts.py tests/test_schema.py`; expect green. Remove the temporary probe with `apply_patch`; do not edit durable tests in P3.T3.
- [ ] **Step 4: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/services/domain_bootstrap_service.py app/services/curriculum_service.py app/seed.py`, `git diff --check`, `git diff --name-only HEAD | sort`; output must be exactly a subset of the three P3.T3 files. Commit: `feat(P3.T3): seed technical A1 curriculum pilot`.
