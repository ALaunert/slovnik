# Language Assistant WS-B Practice and History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Project execution override:** Execute one task at a time in `/Users/launert/projects/slovnik-worktrees/ws-b` through a fresh Codex agent using `superpowers:test-driven-development`; stop for INT review after every task.

**Goal:** Implement PracticeRun/Activity lifecycle, immutable idempotent learning evidence, and the legacy quiz shadow adapter while preserving the existing quiz API and behavior.

**Architecture:** Practice owns pure lifecycle/state contracts, SQL persistence, and application services. Every accepted attempt owns one immutable event and one terminal ActivityInstance; retries are new linked activities, and projection is invoked atomically through a frozen port.

**Tech Stack:** Python dataclasses/enums/protocols, SQLAlchemy 2 row locks, pytest SQLite/PostgreSQL, Ruff

---

**Allowed owner paths:** `backend/app/domain/{practice,practice_ports}.py`, `backend/app/domain_models/practice.py`, `backend/app/repositories/practice.py`, `backend/app/services/{practice_service,learning_event_service,shadow_quiz_service,quiz_service}.py`, `backend/tests/{test_practice_contracts,test_learning_events,test_quiz_shadow,test_quizzes}.py`.

**Forbidden paths:** frozen shared/shadow contracts, registries, migration, shared fixtures, WS-A/WS-C files, progress docs, frontend, public schemas/routes. Use DTO-01, EVENT-01, and shadow contracts through public imports.

**Mandatory microcycle:** Every behavior/assertion listed below is a separate 2–5 minute RED → GREEN → REFACTOR loop. Run the exact task pytest command after the new assertion for RED, after minimum code for GREEN, and after one cleanup for GREEN. P2.T1 uses a temporary probe because its normative changeset contains no test path.

### Task 1: P1.T5 — Practice & History foundation

**Canonical references:** DTO-01; SQL-01 Practice/Event tables; EVENT-01 registry (shape only until P2.T2).

**Files:**
- Create: `backend/app/domain/practice.py`
- Create: `backend/app/domain/practice_ports.py`
- Create: `backend/app/domain_models/practice.py`
- Create: `backend/app/repositories/practice.py`
- Test: `backend/tests/test_practice_contracts.py`

- [ ] **Step 1: RED — run/activity shapes.** Test run active/terminal timestamp rules, exposure versus exercise operation/scorer shape, one canonical TargetSpec/key, 64 KiB spec bound, bounded selection metadata, deterministic-v1 null propensity, and policy inheritance. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_practice_contracts.py`; expect missing types.
- [ ] **Step 2: GREEN then REFACTOR — pure state values.** Implement one failing assertion, rerun `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_practice_contracts.py` GREEN, then make one cleanup and rerun it.
- [ ] **Step 3: RED — retry and terminal invariants.** Test attempt 1 has no parent, retry has same run/target and increasing attempt, pending has no terminal time, terminal has one, and activity cannot accept two terminal results. Expect missing validation.
- [ ] **Step 4: GREEN then REFACTOR — lifecycle guards.** Add one failing guard, rerun the exact Practice contract command GREEN, then refactor one helper and rerun it.
- [ ] **Step 5: RED — ports and ORM parity.** Test evaluator port import isolation, SQL-01 composite ownership/uniqueness, portable JSON, and repository returns domain values. Expect mapping/repository failures.
- [ ] **Step 6: GREEN then REFACTOR — context mapping/repository primitives.** Implement one failing mapping/repository behavior, rerun the exact contract command GREEN, then refactor one mapper and rerun it.
- [ ] **Step 7: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_practice_contracts.py`, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/domain/practice.py app/domain/practice_ports.py app/domain_models/practice.py app/repositories/practice.py tests/test_practice_contracts.py`, `git diff --check`, `git diff --name-only HEAD | sort`; output must be a subset of the five P1.T5 files. Commit: `feat(P1.T5): add practice history foundation`.

### Task 2: P2.T1 — PracticeRun and ActivityInstance lifecycle

**Files:**
- Modify: `backend/app/domain/practice.py`
- Modify: `backend/app/domain/practice_ports.py`
- Modify: `backend/app/repositories/practice.py`
- Create: `backend/app/services/practice_service.py`

- [ ] **Step 1: Temporary RED probe.** Create `/private/tmp/slovnik-p2-t1/test_p2_t1.py`. Add one assertion at a time for learner ownership, terminal rejection, non-empty/all-completed run, abandonment cancellation, locked sequence allocation, policy inheritance, retry identity/order/snapshot, and activity-lock race boundary. Run `cd /Users/launert/projects/slovnik-worktrees/ws-b/backend && PYTHONPATH=. /Users/launert/projects/slovnik/backend/.venv/bin/pytest -v /private/tmp/slovnik-p2-t1/test_p2_t1.py`; record each RED.
- [ ] **Step 2: GREEN then REFACTOR.** For each assertion add minimum code only in the four P2.T1 files, rerun the identical command GREEN, then make one cleanup and rerun GREEN. Use barriers/events, never sleeps.
- [ ] **Step 3: Durable regression.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_practice_contracts.py`; expect green. Remove the temporary probe with `apply_patch`; do not modify `tests/test_practice_contracts.py` in P2.T1.
- [ ] **Step 4: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/domain/practice.py app/domain/practice_ports.py app/repositories/practice.py app/services/practice_service.py`, `git diff --check`, `git diff --name-only HEAD | sort`; output must be a subset of the four P2.T1 files. Commit: `feat(P2.T1): implement practice lifecycle`.

### Task 3: P2.T2 — Canonical immutable LearningEvent

**Canonical references:** EVENT-01 and P2.T2 bounds/compatibility matrix. Do not store projector version in the event.

**Files:**
- Modify: `backend/app/domain/practice.py`
- Modify: `backend/app/repositories/practice.py`
- Create: `backend/app/services/learning_event_service.py`
- Test: `backend/tests/test_learning_events.py`

- [ ] **Step 1: RED — EVENT-01 validation matrix.** Add table tests for exposure, deterministic correct/incorrect/partial, self-report unknown/rating, and model-assisted finite confidence; reject incompatible source/outcome/score/activity combinations. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_learning_events.py`; expect missing event builder.
- [ ] **Step 2: GREEN then REFACTOR — bounded immutable event.** Implement one failing assertion, rerun `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_learning_events.py` GREEN, then refactor one builder and rerun it.
- [ ] **Step 3: RED — payload/privacy bounds.** Test response truncation at 2000 code points, closed response/hint/feedback/reason shapes, 16 KiB payload, tag/hint bounds, NFC normalization, and absence of API keys/provider prompts/free conversation. Expect oversize/unknown fields accepted before fix.
- [ ] **Step 4: GREEN then REFACTOR — one canonical serializer.** Implement one failing bound, rerun the exact event command GREEN, then refactor one serializer helper and rerun it.
- [ ] **Step 5: RED — native event time.** Test timezone-aware, selected-at lower bound, receipt+5m upper bound, and database-clock created time. Expect invalid timestamp acceptance.
- [ ] **Step 6: GREEN then REFACTOR — UTC boundary.** Implement one timestamp rule, rerun the exact event command GREEN, then refactor one UTC helper and rerun it.
- [ ] **Step 7: RED — semantic idempotency.** Test pre-lock lookup, post-lock lookup, same learner/key/activity/normalized response/legacy ref returns identical event, different semantic payload conflicts, excluded latency/evaluation/server IDs/timestamps do not change fingerprint, and another learner scopes independently. Expect duplicates or wrong conflict.
- [ ] **Step 8: GREEN then REFACTOR — canonical request fingerprint.** Implement one failing lookup/fingerprint rule, rerun the exact event command GREEN, then refactor one lookup helper and rerun it. No retry/run side effect may occur first.
- [ ] **Step 9: RED → GREEN → REFACTOR — one-event concurrency.** Add only the same-key two-session barrier test and run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_learning_events.py -k 'concurrent_same_key'` RED; implement the minimum, rerun GREEN, refactor synchronization, rerun GREEN. Repeat as a separate cycle for different keys.
- [ ] **Step 10: RED → GREEN → REFACTOR — atomic projection.** Add only the injected-projector-failure rollback node and run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_learning_events.py -k 'projector_failure'` RED; implement through the frozen projection port, rerun GREEN, refactor transaction orchestration, rerun GREEN.
- [ ] **Step 11: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_learning_events.py tests/test_practice_contracts.py`, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/domain/practice.py app/repositories/practice.py app/services/learning_event_service.py tests/test_learning_events.py`, `git diff --check`, `git diff --name-only HEAD | sort`, `rg -n 'api[_-]?key|provider.*prompt|raw_response' app/services/learning_event_service.py tests/test_learning_events.py`; every match must be a redaction assertion. Commit: `feat(P2.T2): record immutable learning events`.

### Task 4: P4.T3 — Quiz shadow adapter

**Canonical references:** P4.T3, frozen P4.T1 shadow contracts, EVENT-01; legacy `quiz_service.py` remains authoritative.

**Files:**
- Modify: `backend/app/services/quiz_service.py`
- Create: `backend/app/services/shadow_quiz_service.py`
- Modify: `backend/tests/test_quizzes.py`
- Test: `backend/tests/test_quiz_shadow.py`

- [ ] **Step 1: RED — flag-off zero work.** Instrument domain query/write entry points and assert start/answer/complete paths do not call them when disabled; all existing responses/database mutations remain byte-equivalent. Run quiz regression and shadow tests; expect missing adapter.
- [ ] **Step 2: GREEN then REFACTOR — guarded seam.** Add the minimum flag guard, rerun `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_quizzes.py tests/test_quiz_shadow.py` GREEN, then clean one seam and rerun it.
- [ ] **Step 3: RED — run and snapshot creation.** With flag on, assert quiz start creates one mapped run, one pending activity per question-plan order, exact bounded prompt/options/answer-version snapshot, target mappings per question type, legacy policy/reason, and no events. Expect missing rows.
- [ ] **Step 4: GREEN then REFACTOR — deterministic start mapping.** Implement one snapshot/mapping assertion, rerun the exact quiz command GREEN, then refactor one mapper and rerun it.
- [ ] **Step 5: RED — accepted answer event mapping.** Assert flush gives `QuizAnswer.id`, idempotency key `legacy:quiz-answer:{id}`, deterministic choice/typing versus self-report recognition, forgot→AGAIN, remembered→GOOD, and exactly one event before commit. Expect missing event.
- [ ] **Step 6: GREEN then REFACTOR — atomic answer adapter.** Implement one answer mapping assertion, rerun the exact quiz command GREEN, then refactor one adapter helper and rerun it.
- [ ] **Step 7: RED — retry chronology and limits.** Test incorrect first answer terminalizes original and creates linked retry at end; second answer owns retry event; same answer loss/retry is idempotent; no activity has two events. Expect reuse/order defect.
- [ ] **Step 8: GREEN then REFACTOR — retry mapping.** Implement one retry assertion, rerun the exact quiz command GREEN, then refactor one lock/order helper and rerun it.
- [ ] **Step 9: RED → GREEN → REFACTOR — concurrency.** Add only `test_concurrent_first_quiz_answers` and run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_quiz_shadow.py -k 'concurrent_first_quiz_answers'` RED; implement minimum locking, rerun GREEN, refactor barrier fixture, rerun GREEN.
- [ ] **Step 10: RED → GREEN → REFACTOR — rollback/privacy.** Add only injected shadow-failure rollback, run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_quiz_shadow.py -k 'shadow_failure_rolls_back'` RED, implement and rerun GREEN, refactor transaction helper and rerun. Repeat separately with the full `tests/test_quiz_shadow.py` command for wrong-user/out-of-plan/completed no-row cases and log redaction.
- [ ] **Step 11: RED → GREEN → REFACTOR — completion.** Add only run-completion/incomplete-run assertion, run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_quiz_shadow.py -k 'domain_run_completion'` RED, implement, rerun GREEN, refactor completion helper, rerun GREEN.
- [ ] **Step 12: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_quizzes.py tests/test_quiz_shadow.py tests/test_learning_events.py`, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/services/quiz_service.py app/services/shadow_quiz_service.py tests/test_quizzes.py tests/test_quiz_shadow.py`, `git diff --check`, `git diff --name-only HEAD | sort`, and `git diff --name-only HEAD | rg '^(frontend/|backend/app/routers/|backend/app/schemas.py$)'` (expect no output). Commit: `feat(P4.T3): shadow legacy quiz evidence`.
