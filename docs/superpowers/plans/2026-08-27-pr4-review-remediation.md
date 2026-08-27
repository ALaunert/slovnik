# PR #4 Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix every confirmed PR #4 review blocker, verify production-schema behavior, and repeat independent review.

**Architecture:** Preserve legacy authority and public APIs. Add only the missing immutable provenance/evidence fields, rollout-safe shadow boundaries, catalog freshness validation, and a read-only runtime selector composition isolated in its own session.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL/SQLite, pytest, Ruff.

---

### Task 1: Schema parity, idempotency, and deterministic evidence

**Files:**
- Modify: `backend/alembic/versions/20260826_0005_domain_foundation.py`
- Modify: `backend/app/domain/progress.py`
- Modify: `backend/app/domain/practice.py`
- Modify: `backend/app/domain_models/{catalog,curriculum,practice,progress}.py`
- Modify: `backend/app/repositories/{practice,progress}.py`
- Modify: `backend/app/services/{learning_event_service,learner_projection_service,next_activity_service}.py`
- Modify: `backend/app/services/{shadow_learning_service,shadow_quiz_service}.py`
- Test: `backend/tests/test_{migrations,learning_events,progress_contracts,projection,next_activity,practice_contracts}.py`

- [ ] Add failing tests for the deployed constraint name, migrated-domain metadata parity, persisted feedback policy version, deterministic evidence count, replay, and partial→ASSESS.
- [ ] Run each focused test and confirm the expected failure.
- [ ] Align migration/ORM names and types; persist `feedback_policy_version` and `deterministic_evidence_count`; update mapping and selector logic. Both shadow activity creators pass their frozen `legacy-new-word-v1`/`legacy-review-v1`/`legacy-quiz-v1` feedback policy values.
- [ ] Run focused SQLite and PostgreSQL tests until green, then refactor without behavior changes.
- [ ] Commit the task.

### Task 2: Catalog freshness

**Files:**
- Modify: `backend/app/services/domain_bootstrap_service.py`
- Create: `backend/app/services/catalog_mapping_service.py`
- Modify: `backend/app/services/{shadow_learning_service,shadow_quiz_service}.py`
- Test: `backend/tests/test_{domain_catalog,learning_shadow,quiz_shadow}.py`
- Modify: `README.md`

- [ ] Add failing fresh/stale/missing/ambiguous mapping and audit tests.
- [ ] Run them and confirm stale content is currently accepted.
- [ ] Store a canonical source fingerprint, centralize mapping resolution, reject stale evidence writes, and expose a read-only audit command/function.
- [ ] Run focused tests and commit.

### Task 3: Quiz rollout and privacy

**Files:**
- Modify: `backend/app/services/{quiz_service,shadow_quiz_service}.py`
- Test: `backend/tests/test_{quiz_shadow,quizzes}.py`

- [ ] Add failing tests for off→on, on→off→on, exact answer/event parity, answer-versus-completion locking, fixed `quiz_shadow_enrollment_gap` diagnostics, and secret-bearing start/answer/complete shadow failures with suppressed causes.
- [ ] Confirm every test fails for the intended reason.
- [ ] Add per-attempt enrollment fallback, abandon drifted runs, enforce attempt-first locking, and sanitize failures with `ShadowQuizFailure`.
- [ ] Run focused SQLite/PostgreSQL tests and commit.

### Task 4: Runtime comparison

**Files:**
- Create: `backend/app/services/shadow_selection_runtime.py`
- Modify: `backend/app/services/{learning_service,shadow_comparison_service}.py`
- Modify as needed: `backend/app/repositories/{practice,progress,curriculum,catalog}.py`
- Test: `backend/tests/test_{shadow_comparison,domain_shadow_integration}.py`

- [ ] Add failing endpoint-level tests proving enabled new/review requests map first-word/`NONE`/`WEAK` semantics, reconstruct history fingerprints from stored snapshot plus generator/scorer/feedback versions, attempt comparison, and isolate failures from the authoritative session.
- [ ] Run them RED.
- [ ] Implement persistence-backed ports and invoke comparison in a separate short-lived read session.
- [ ] Run focused tests and commit.

### Task 5: Documentation, verification, and re-review

**Files:**
- Modify: `docs/product-state.md`
- Modify: `docs/progress/PROGRESS.md`
- Modify if required: `README.md`

- [ ] Update durable state, rollout/audit commands, verification, and deferred semantic versioning.
- [ ] Run Ruff, full flag-off backend tests, targeted flag-on tests, migration round trips, PostgreSQL concurrency, privacy searches, and `git diff --check`.
- [ ] Dispatch an independent code reviewer over the new base/head range.
- [ ] Fix confirmed review findings with new RED-GREEN cycles and rerun verification.
- [ ] Commit, push the branch, update PR #4, and publish the final review result.
