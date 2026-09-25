# PR #6 Review Fixes Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans task by task. Write and observe a failing regression test before each behavior change.

**Goal:** Close the concrete PR #6 review findings while keeping the pilot inactive and legacy quiz behavior intact.

**Architecture:** Repair the existing publication transaction and draft validator rather than adding learner routes. Persist only the publication-request fingerprint needed to verify active retries; use an additive nullable migration so older curriculum versions remain readable. Keep source artifact checks scoped to referenced items and use a trusted manifest root. Bound quiz distractor reads without dropping valid later choices.

**Tech Stack:** Python 3.12, SQLAlchemy, Alembic, pytest, FastAPI; file-backed JSON pilot fixtures.

**Spec:** The findings in the PR #6 code-review conversation, `docs/learning/implementation-plan.md` P0-04/P0-05/P0-08/P1-04a, and `docs/product-state.md`.

## Global constraints

- Preserve the eight `synthetic_test_only` pilot fixtures and their rejection under `--publish`.
- Do not activate learner content, change progression, or treat AI review as educator/rights approval.
- Keep existing standalone `CurriculumService.publish` behavior and old quiz answer plans.
- Update `docs/product-state.md` for durable behavior and gate changes.

## Review focus

- A child added while a lexical unit is published must not leave parent and child statuses inconsistent.
- An edited legacy word must not make a mapping stale between preflight and activation.
- Repeating a publication with different rights/source inputs must be rejected, not called idempotent.
- Missing or changed pinned source bytes must block activation.
- Assessment keys must not leak through practice answer policies; an empty reviewed pack must fail draft publish validation.
- Duplicate distractors must still be skipped without reading the whole vocabulary in the common case.

## Task 1: Publication integrity and provenance

**Files:** `backend/app/repositories/catalog.py`, `backend/app/services/content_publication_service.py`, `backend/app/domain_models/curriculum.py`, one additive Alembic revision, `backend/tests/test_content_publication.py` and migration tests if needed.

- [x] Add failing tests that force each publication race after a previously valid read: new child, changed legacy word, changed active-repeat source mapping, and nonexistent or modified pinned artifact.
- [x] Run each new test and confirm the expected failure before changing production code.
- [x] Serialize the catalog/legacy reads needed for publication, recheck child completeness, verify referenced artifact bytes, and persist/compare a deterministic publication request fingerprint in the same transaction.
- [x] Re-run focused publication/provenance and migration tests; inspect rollback, active retry, and older null-fingerprint behavior.

## Task 2: Pilot validator coverage and isolation

**Files:** `content/curricula/a1-pilot/validate_examples.py`, `backend/tests/test_pilot_examples.py`.

- [x] Add failing publish-mode tests for an empty reviewed pack and for an exact assessment answer exposed by a practice answer policy.
- [x] Require authored outcome/role coverage and include accepted variants in split-leakage checks without making the unchanged synthetic draft invalid.
- [x] Run focused validator tests and confirm the existing test-only pack still passes draft validation and fails publish validation.

## Task 3: Bounded quiz distractor reads

**Files:** `backend/app/services/quiz_service.py`, `backend/tests/test_quizzes.py`.

- [x] Add a failing test with a long duplicate run and a later valid distractor, checking that the query fetches candidates in bounded batches.
- [x] Implement bounded reads while retaining the current ranking, normalization, unique-choice and random-position behavior.
- [x] Run focused quiz and quiz-shadow tests.

## Task 4: Integrate and update PR

**Files:** `docs/product-state.md`, this plan and changed implementation/tests.

- [x] Review the combined diff and resolve any overlapping assumptions.
- [x] Run the full backend suite, Ruff, frontend unit/typecheck/build/browser checks, both draft validators, expected publish rejection, migration upgrade/downgrade, and `git diff --check`.
- [x] Commit only intentional files, push the branch, and verify PR #6 reflects the new commit.

## Verification (2026-09-25)

- Full backend with disposable PostgreSQL integration: 775 passed; Ruff clean.
- Frontend: 87 unit tests, Vue typecheck, Vite build and 6 Playwright tests passed.
- Pilot manifest and draft examples validated; publish mode rejected the unchanged synthetic pack as expected.
- Migration upgrade/downgrade and PostgreSQL concurrency cases passed; `git diff --check` passed.
