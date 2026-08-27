# Language Assistant Integrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Project execution override:** INT coordinates `superpowers:dispatching-parallel-agents`; each implementation task uses a fresh Codex agent and `superpowers:test-driven-development`. This plan never authorizes parallel edits to the same tracked path.

**Goal:** Freeze shared contracts and integrate all context work into one reversible, tested, shadow-first backend foundation.

**Architecture:** INT owns cross-context seams: stable target contracts, package/ORM registries, one Alembic revision, shared fixtures, integration gates, shadow contracts/configuration, and durable documentation. Context code arrives only as reviewed, green task commits.

**Tech Stack:** Python dataclasses/enums, SQLAlchemy 2, Alembic, SQLite/PostgreSQL, pytest, Ruff

---

Use `PY=/Users/launert/projects/slovnik/backend/.venv/bin` conceptually; run the expanded absolute executable paths shown below from `/Users/launert/projects/slovnik-worktrees/int/backend`.

**Mandatory microcycle:** Every individual assertion/behavior below is separate: add one assertion → run its exact pytest node/file and record RED → add minimum code → rerun the identical command GREEN → make one cleanup → rerun the identical command GREEN. A list of behaviors is a queue of microcycles, never one batch. P1.T2 uses a temporary probe because its normative changeset has no durable test path.

### Task 1: P1.T1 — Freeze Gate 0 shared contracts and canonical TargetSpec

**Canonical references:** P1 DTO-01 and ALG-01 only; do not duplicate or reinterpret them here.

**Files:**
- Create: `backend/app/domain/__init__.py`
- Create: `backend/app/domain/shared.py`
- Create: `backend/app/domain/target.py`
- Test: `backend/tests/test_domain_contracts.py`

- [ ] **Step 1: RED — public wire enums and imports.** Add tests for every v1 enum wire value and public import listed by DTO-01, plus an import-isolation test that blocks FastAPI, SQLAlchemy, Pydantic settings, and OpenAI modules. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_domain_contracts.py`; expect import/definition failures.
- [ ] **Step 2: GREEN — minimum shared values.** Implement standard-library-only `str, Enum` types and immutable value objects needed by DTO-01. Re-run the same command; expect the wire/import group to pass.
- [ ] **Step 3: REFACTOR.** Remove duplicate validation helpers without changing wire values; rerun the group.
- [ ] **Step 4: RED — TargetSpec compatibility and canonical key.** Add table tests for three allowed MVP pairings, ordinary Sense recall, form-specific conditioned recall, invalid pairings, lowercase canonical UUID, schema version, and 255-character bound. Expect missing validation/key failures.
- [ ] **Step 5: GREEN — immutable TargetSpec.** Implement DTO-01 validation and ALG-01 key construction exactly, with expected Form excluded from ordinary learner identity. Rerun targeted tests; expect pass.
- [ ] **Step 6: RED — canonical condition profile.** Add tests for key-order equivalence, recursive NFC normalization, NFC-key collision, floats/NaN, booleans versus integers, non-string keys, unsupported objects, and defensive immutability. Expect invalid cases to be accepted before implementation.
- [ ] **Step 7: GREEN then REFACTOR — canonical JSON.** Add the minimum recursive canonicalizer and run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_domain_contracts.py` GREEN. Then remove duplication without changing behavior and rerun the identical command GREEN.
- [ ] **Step 8: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/domain tests/test_domain_contracts.py`, `git diff --check`, `git status --short`, and `git diff --name-only 64c1dbb...HEAD`. Commit only the four files: `feat(P1.T1): freeze language assistant target contracts`.

### Task 2: P1.T2 — Prepare registry and single migration shell

**Canonical reference:** P1 SQL-01. Context mappings are deliberately absent until P1.T7.

**Files:**
- Create: `backend/app/domain_models/__init__.py`
- Create: `backend/app/repositories/__init__.py`
- Modify: `backend/app/db.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/20260826_0005_domain_foundation.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Temporary RED probes.** Create `/private/tmp/slovnik-p1-t2/test_p1_t2.py`. Add one test at a time for registry import isolation, legacy metadata creation, revision/down-revision identity, exactly one revision, SQL-01 shape, and downgrade helpers. For each assertion run `cd /Users/launert/projects/slovnik-worktrees/int/backend && PYTHONPATH=. /Users/launert/projects/slovnik/backend/.venv/bin/pytest -v /private/tmp/slovnik-p1-t2/test_p1_t2.py`; record the named RED.
- [ ] **Step 2: GREEN each probe.** Add only the minimum code in the six P1.T2 files, rerun the identical probe command GREEN, then make one cleanup and rerun it GREEN before adding the next assertion.
- [ ] **Step 3: Durable regression.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_schema.py tests/test_migrations.py`; expect green. Remove the temporary probe with `apply_patch`; do not modify either durable test file in P1.T2.
- [ ] **Step 4: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/db.py alembic/env.py alembic/versions/20260826_0005_domain_foundation.py tests/conftest.py`, `git diff --check`, `git diff --name-only HEAD | sort`; output must be a subset of the six P1.T2 paths. Commit: `feat(P1.T2): add domain registry and migration shell`.

### Task 3: P1.T7 — Assemble G1 foundation integration gate

**Files:**
- Modify: `backend/app/domain/__init__.py`
- Modify: `backend/app/domain_models/__init__.py`
- Modify: `backend/alembic/versions/20260826_0005_domain_foundation.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_migrations.py`

- [ ] **Step 1: Admit inputs.** Verify reviewed task commits P1.T2–P1.T6, exact owner path lists, and no cross-workstream overlap. Cherry-pick/integrate in declared order and record SHAs.
- [ ] **Step 2: RED — full metadata discovery.** Add an integration test that imports the ORM registry, asserts all 11 SQL-01 tables are registered once, and creates/drops them with legacy tables in SQLite. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_migrations.py -k 'domain or metadata'`; expect missing registry imports/mapping parity.
- [ ] **Step 3: GREEN then REFACTOR — registry completion.** Add the minimum exports/imports/migration parity, rerun `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_migrations.py -k 'domain or metadata'` GREEN, then clean one registry duplication and rerun the identical command GREEN.
- [ ] **Step 4: RED — reversible legacy preservation.** Extend SQLite round-trip tests to upgrade from 0004, compare all seeded legacy field values, validate new constraints/indexes, downgrade to 0004, and prove only 11 new tables/indexes disappear. Expect incomplete round-trip failures.
- [ ] **Step 5: GREEN — complete migration.** Fix ordering, foreign keys, constraints, partial index, and downgrade order minimally; rerun the migration test until green.
- [ ] **Step 6: PostgreSQL RED/GREEN evidence.** Start project PostgreSQL and run `SLOVNIK_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://slovnik:slovnik@localhost:5432/postgres' /Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_migrations.py`; diagnose any dialect failure with `superpowers:systematic-debugging` and rerun fresh.
- [ ] **Step 7: G1 verification and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_domain_contracts.py tests/test_domain_catalog.py tests/test_curriculum_contracts.py tests/test_practice_contracts.py tests/test_progress_contracts.py tests/test_migrations.py`, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check .`, `git diff --check`, `git diff --name-only HEAD | sort`, and `git diff --name-only HEAD | rg '^(frontend/|backend/app/routers/|backend/app/schemas.py$)'` (expect no output), then commit: `test(P1.T7): close foundation integration gate`.

### Task 4: P2.T5 — Close evidence, transaction, replay, and concurrency matrix

**Files:**
- Modify: `backend/tests/test_learning_events.py`
- Modify: `backend/tests/test_projection.py`
- Modify: `backend/tests/test_migrations.py`

- [ ] **Step 1: Admit P2 inputs.** Verify reviewed P2.T1–P2.T4 commits and their owner-local RED/GREEN evidence; integrate in task order.
- [ ] **Step 2: RED — transaction rollback.** Add a test that injects projector failure after event/activity changes and asserts event, terminal transition, and target state all roll back. Run the single test; expect leaked state or missing orchestration coverage.
- [ ] **Step 3: GREEN then REFACTOR.** Return production defects before admission, validate one replacement source commit in the disposable G2 worktree, and rerun the exact rollback node GREEN. Then clean one INT test fixture and rerun the identical node GREEN.
- [ ] **Step 4: RED — cross-owner replay/idempotency.** Add one assertion at a time for same semantic key, conflicting payload, different learner ownership, late/reverse-ID order, and baseline-plus-events replay. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_learning_events.py tests/test_projection.py`; record the named RED before its owner fix.
- [ ] **Step 5: GREEN then REFACTOR.** For each failing matrix node, validate one owner replacement commit before admission, rerun that exact node GREEN, then make one test-only cleanup and rerun it. Never create a post-admission owner fix commit.
- [ ] **Step 6: PostgreSQL RED → GREEN → REFACTOR.** Add one barrier-based node at a time for first state-row creation and duplicate submission. Run `SLOVNIK_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://slovnik:slovnik@localhost:5432/postgres' /Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_migrations.py -k 'postgresql and (event or projection or state)'` for RED, validate the owner fix, rerun GREEN, then refactor the synchronization fixture and rerun GREEN.
- [ ] **Step 7: G2 verification and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_practice_contracts.py tests/test_learning_events.py tests/test_projection.py tests/test_legacy_progress_bootstrap.py tests/test_migrations.py`, the exact PostgreSQL command from Step 6, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check .`, `git diff --check`, `git status --short`, `git diff --name-only HEAD | sort`. Commit: `test(P2.T5): close evidence and replay gate`.

### Task 5: P3.T4 — Close curriculum and selector integration matrix

**Files:**
- Modify: `backend/tests/test_curriculum.py`
- Modify: `backend/tests/test_next_activity.py`
- Modify: `backend/tests/test_projection.py`

- [ ] **Step 1: Admit P3 inputs after G2.** Verify and integrate reviewed P3.T1–P3.T3 only after the exact G2 commit.
- [ ] **Step 2: RED — frontier/projection integration.** Add one fixed-UTC assertion at a time for missing/native evidence, high-water readiness, failure after unlock, due memory, SOFT readiness, and reason codes. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_curriculum.py tests/test_next_activity.py tests/test_projection.py`; record the named RED before its owner fix.
- [ ] **Step 3: GREEN then REFACTOR.** Correct one owner defect at a time before admission, rerun its exact node GREEN, then refactor one fixture and rerun it. Keep competence and memory separate.
- [ ] **Step 4: RED — deterministic decision snapshots.** Add row-order permutations, exact rank components, no-activity decision codes, daily distinct-target acquisition budget, stable fingerprint, and selector non-mutation assertions. Expect any nondeterministic or missing metadata failure.
- [ ] **Step 5: GREEN then REFACTOR.** Correct through owners before admission, rerun the exact snapshot node GREEN, then perform one test-only cleanup and rerun it. Keep explicit no-network/no-mutation assertions.
- [ ] **Step 6: PostgreSQL publication gate.** Run `SLOVNIK_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://slovnik:slovnik@localhost:5432/postgres' /Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_curriculum.py -k 'postgresql and concurrent'`; expect one active winner and no invalid graph activation.
- [ ] **Step 7: G3 verification and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_curriculum.py tests/test_next_activity.py tests/test_projection.py`, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check .`, `git diff --check`, `git status --short`, `git diff --name-only HEAD | sort`, and `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_next_activity.py -k 'does_not_mutate or no_network or deterministic'`. Commit: `test(P3.T4): close curriculum selection gate`.

### Task 6: P4.T1 — Freeze shadow contracts and feature flag

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/services/domain_shadow_contracts.py`
- Test: `backend/tests/test_domain_shadow_contracts.py`

- [ ] **Step 1: RED — flag defaults and production gates.** Add config tests for false default, explicit test/development enable, production rejection without both data-lifecycle and identity/trusted-deployment gates, and case-insensitive environment handling. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_domain_shadow_contracts.py tests/test_config.py`; expect missing settings/validation failures.
- [ ] **Step 2: GREEN then REFACTOR — gated configuration.** Add minimal boolean/gate settings and validator, rerun `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_domain_shadow_contracts.py tests/test_config.py` GREEN, then simplify one validation branch and rerun the identical command GREEN.
- [ ] **Step 3: RED — typed adapter contracts.** Add byte-level wire tests for legacy source kinds, idempotency inputs, policy/reason codes, adapter result, and non-authoritative comparison categories; assert no raw response/provider-secret fields and no imports of legacy services.
- [ ] **Step 4: GREEN then REFACTOR — frozen contracts.** Implement the minimum immutable contracts, rerun `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_domain_shadow_contracts.py tests/test_config.py` GREEN, then deduplicate one bounded validator and rerun the identical command GREEN.
- [ ] **Step 5: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_domain_shadow_contracts.py tests/test_config.py`, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/config.py app/services/domain_shadow_contracts.py tests/test_domain_shadow_contracts.py tests/test_config.py`, `git diff --check`, `git diff --name-only HEAD | sort`, then commit: `feat(P4.T1): freeze shadow integration contracts`.

### Task 7: P4.T5 — Close G4 regression and durable state

**Files:**
- Modify: `backend/tests/test_migrations.py`
- Create: `backend/tests/test_domain_shadow_integration.py`
- Modify: `docs/product-state.md`
- Modify: `docs/progress/PROGRESS.md`
- Modify when a new deferred decision is accepted: `docs/progress/domain-model-v0.1.md`

- [ ] **Step 1: Admit P4 inputs.** Verify reviewed P4.T2/P4.T3/P4.T4 commits, integrate in order, and confirm the frozen P4.T1 contract did not drift.
- [ ] **Step 2: RED — cross-flow atomicity/idempotency.** Add flag-on integration cases for learning exposure/review and quiz initial/retry events, injected failures, lost-response retries, and absence of orphan run/activity/event/state rows. Run the new file; expect missing cross-flow coverage or failures.
- [ ] **Step 3: GREEN then REFACTOR.** Return each defect before admission, validate the replacement source commit, and rerun the exact failing node GREEN; then make one integration-fixture cleanup and rerun the identical node. Keep comparison failure non-authoritative.
- [ ] **Step 4: PostgreSQL RED → GREEN → REFACTOR.** Add one barrier-based review or quiz duplicate node at a time, run `ENVIRONMENT=test LANGUAGE_ASSISTANT_SHADOW_ENABLED=true SLOVNIK_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://slovnik:slovnik@localhost:5432/postgres' /Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_migrations.py -k 'postgresql and (shadow or review or quiz)'` RED, validate the owner fix, rerun GREEN, then refactor the barrier fixture and rerun GREEN.
- [ ] **Step 5: Flag-off full regression.** Run `ENVIRONMENT=test LANGUAGE_ASSISTANT_SHADOW_ENABLED=false /Users/launert/projects/slovnik/backend/.venv/bin/pytest -v`; expect all legacy tests pass.
- [ ] **Step 6: Flag-on targeted verification.** Run `ENVIRONMENT=test LANGUAGE_ASSISTANT_SHADOW_ENABLED=true /Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_domain_shadow_contracts.py tests/test_learning_shadow.py tests/test_quiz_shadow.py tests/test_shadow_comparison.py tests/test_domain_shadow_integration.py`; expect all pass.
- [ ] **Step 7: Migration/PostgreSQL verification.** Run `ENVIRONMENT=test LANGUAGE_ASSISTANT_SHADOW_ENABLED=true SLOVNIK_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://slovnik:slovnik@localhost:5432/postgres' /Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_migrations.py`; prove both dialect round trips and concurrency.
- [ ] **Step 8: Durable docs.** Update `docs/product-state.md` with only implemented backend/shadow behavior and current verification. Update `docs/progress/PROGRESS.md` with accepted P1.T1–P4.T4 SHAs, G0–G4 evidence, and P4.T5 status as “completed by this documentation/gate commit”; do not invent the commit's own SHA. Record only accepted new deferred items in the canonical log.
- [ ] **Step 9: Final local verification and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check .`, exact Steps 5–7, `git diff --check`, `git status --short`, `git diff --name-only 64c1dbb..HEAD | sort`, and `git diff --name-only 64c1dbb..HEAD | rg '^(frontend/|backend/app/routers/|backend/app/schemas.py$)'` (expect no output). Run `rg -n 'api[_-]?key|provider.*prompt|raw_response' app/services/domain_shadow_contracts.py app/services/shadow_* tests/test_*shadow*`; every match must be a redaction assertion, never payload/log storage. Commit: `docs(P4.T5): close shadow foundation gate`. After commit, run `git log -1 --format=%H` and use that returned SHA only in the final report/task ledger outside the commit.
