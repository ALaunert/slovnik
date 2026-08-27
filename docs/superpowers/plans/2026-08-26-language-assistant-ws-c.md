# Language Assistant WS-C Progress and Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Project execution override:** Execute one task at a time in `/Users/launert/projects/slovnik-worktrees/ws-c` through a fresh Codex agent using `superpowers:test-driven-development`; stop for INT review after every task.

**Goal:** Implement replayable learner target state, conservative memory projection, legacy baseline, deterministic selection, learning shadow writes, and non-authoritative comparison.

**Architecture:** Frozen baseline and native evidence projections remain separate; competence and memory have distinct fields/policies. Selection consumes frozen Curriculum/Practice ports and never mutates data; legacy learning is an atomic shadow adapter behind a gated, false-by-default flag.

**Tech Stack:** Python pure policies/protocols, SQLAlchemy 2 row locks/upserts, pytest SQLite/PostgreSQL, Ruff

---

**Allowed owner paths:** `backend/app/domain/{progress,memory_policy,selection_policy,selection_ports}.py`, `backend/app/domain_models/progress.py`, `backend/app/repositories/progress.py`, `backend/app/services/{learner_projection_service,legacy_progress_bootstrap_service,next_activity_service,shadow_learning_service,shadow_comparison_service,learning_service}.py`, `backend/tests/{test_progress_contracts,test_projection,test_legacy_progress_bootstrap,test_next_activity,test_learning_shadow,test_learning,test_shadow_comparison}.py`.

**Forbidden paths:** shared/target/shadow contracts, registries, migration, shared fixtures, WS-A/WS-B files, progress docs, frontend, public route/schema files. P3.T2 uses fake frozen curriculum/history ports until integration.

**Mandatory microcycle:** Every behavior/assertion listed below is a separate 2–5 minute RED → GREEN → REFACTOR loop. Run the exact task pytest command after one new assertion for RED, after minimum code for GREEN, and after one cleanup for GREEN; only then add the next assertion.

### Task 1: P1.T6 — Learner Progress foundation

**Canonical references:** DTO-01 and SQL-01 learner state table; Domain Model §5.6–5.7.

**Files:**
- Create: `backend/app/domain/progress.py`
- Create: `backend/app/domain/memory_policy.py`
- Create: `backend/app/domain_models/progress.py`
- Create: `backend/app/repositories/progress.py`
- Test: `backend/tests/test_progress_contracts.py`

- [ ] **Step 1: RED — profile view and state invariants.** Test UserProfile adaptation L1=`ru`, requested level/daily budget, canonical learner+target key, neutral/legacy baseline shapes, evidence cursor null/non-null invariants, bounded values, and separate baseline/current fields. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_progress_contracts.py`; expect missing types.
- [ ] **Step 2: GREEN then REFACTOR — pure state values.** Implement one failing assertion, rerun `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_progress_contracts.py` GREEN, then make one cleanup and rerun it.
- [ ] **Step 3: RED — ORM/repository parity.** Test SQL-01 unique learner/target, due index, baseline JSON, timezone fields, conflict-safe ensure, row lock/load, and domain-not-ORM return values. Expect missing mapping/repository behavior.
- [ ] **Step 4: GREEN then REFACTOR — context persistence.** Implement one failing mapping/repository assertion, rerun the exact Progress contract command GREEN, then refactor one mapper and rerun it.
- [ ] **Step 5: RED → GREEN → REFACTOR — fake event-source isolation.** Add only the import/fake-source assertion, run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_progress_contracts.py -k 'fake_event_source or import_isolation'` RED, add the minimum protocol, rerun GREEN, refactor the protocol name/placement once, rerun GREEN.
- [ ] **Step 6: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_progress_contracts.py`, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/domain/progress.py app/domain/memory_policy.py app/domain_models/progress.py app/repositories/progress.py tests/test_progress_contracts.py`, `git diff --check`, `git diff --name-only HEAD | sort`; output must be a subset of the five P1.T6 files. Commit: `feat(P1.T6): add learner progress foundation`.

### Task 2: P2.T3 — Learner projector and MemoryPolicy v1

**Canonical references:** EVENT-01 and ALG-02 in P2; no reinterpretation of event facts.

**Files:**
- Modify: `backend/app/domain/progress.py`
- Modify: `backend/app/domain/memory_policy.py`
- Modify: `backend/app/repositories/progress.py`
- Create: `backend/app/services/learner_projection_service.py`
- Test: `backend/tests/test_projection.py`

- [ ] **Step 1: RED — deterministic competence transitions.** Add table tests for correct/incorrect/partial and assert only deterministic correct/incorrect change weights, uncertainty follows ALG-02, correct raises replayable peak, later incorrect never lowers peak. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_projection.py`; expect missing projection.
- [ ] **Step 2: GREEN then REFACTOR — pure competence reducer.** Implement one transition assertion, rerun `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_projection.py` GREEN, then refactor one reducer helper and rerun it.
- [ ] **Step 3: RED — memory transitions.** Table-test first exposure hold, deterministic success doubling/cap, failure immediate due/lapse, Again/Hard/Good/Easy intervals/caps, self-report competence neutrality, model-assisted neutrality. Expect missing schedule behavior.
- [ ] **Step 4: GREEN then REFACTOR — memory-v1.** Implement one schedule assertion, rerun the exact Projection command GREEN, then refactor one memory helper and rerun it.
- [ ] **Step 5: RED — conflict-safe first state and atomic apply.** Two-session PostgreSQL barrier test concurrent absent-row materialization and duplicate event application; expect one state, one application, no global lock.
- [ ] **Step 6: GREEN — insert then row lock.** Use dialect-safe conflict recovery followed by `SELECT ... FOR UPDATE`; do not swallow unrelated IntegrityError.
- [ ] **Step 7: RED — canonical replay.** Compare incremental versus shuffled storage order replay sorted `(occurred_at,event_id)`; add late event and reverse-ID/equal-time cases that must reset to frozen baseline. Expect divergence.
- [ ] **Step 8: GREEN then REFACTOR — target-local replay.** Implement one replay assertion, rerun the exact Projection command GREEN, then refactor one replay iterator and rerun it.
- [ ] **Step 9: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_projection.py tests/test_progress_contracts.py`, `SLOVNIK_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://slovnik:slovnik@localhost:5432/postgres' /Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_projection.py -k 'postgresql and concurrent'`, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/domain/progress.py app/domain/memory_policy.py app/repositories/progress.py app/services/learner_projection_service.py tests/test_projection.py`, `git diff --check`, `git diff --name-only HEAD | sort`. Commit: `feat(P2.T3): project learner evidence and memory`.

### Task 3: P2.T4 — Legacy progress bootstrap

**Canonical references:** P2.T4 `legacy-bootstrap-v1`; current due semantics in `learning_service.py` are evidence, not new truth.

**Files:**
- Create: `backend/app/services/legacy_progress_bootstrap_service.py`
- Modify: `backend/app/repositories/progress.py`
- Test: `backend/tests/test_legacy_progress_bootstrap.py`
- Modify: `backend/tests/test_projection.py`

- [ ] **Step 1: RED — target mapping and low confidence.** Seed seen/reviewing/learned rows and assert only mapped default Sense+retrieve_form state, zero weights/peak/evidence, uncertainty 1, legacy baseline/version/fingerprint, and zero synthetic events. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_legacy_progress_bootstrap.py`; expect missing service.
- [ ] **Step 2: GREEN then REFACTOR — deterministic baseline builder.** Implement one failing assertion, rerun `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_legacy_progress_bootstrap.py` GREEN, then refactor one builder helper and rerun it.
- [ ] **Step 3: RED — due/weak/null schedule matrix.** Fixed-UTC tests copy explicit due/interval, use bootstrap time for due/weak null schedule, next UTC day for same-day shown null schedule, and avoid ACQUIRE during future hold. Expect semantic mismatches.
- [ ] **Step 4: GREEN then REFACTOR — current-compatible due adapter.** Implement one due assertion, rerun the exact Bootstrap command GREEN, then refactor one due helper and rerun it.
- [ ] **Step 5: RED — repeat/freeze rules.** Test byte-stable rerun, changed source updates only evidence_count=0 baseline, native evidence state never changes, neutral state never overwritten, ambiguous mapping skipped with diagnostics. Expect unwanted overwrite/ID drift.
- [ ] **Step 6: GREEN then REFACTOR — guarded upsert.** Implement one freeze/rerun assertion, rerun the exact Bootstrap command GREEN, then refactor one guarded-upsert helper and rerun it.
- [ ] **Step 7: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_legacy_progress_bootstrap.py tests/test_projection.py`, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/services/legacy_progress_bootstrap_service.py app/repositories/progress.py tests/test_legacy_progress_bootstrap.py tests/test_projection.py`, `git diff --check`, `git diff --name-only HEAD | sort`, `rg -n 'learner_id|raw_response|answer' app/services/legacy_progress_bootstrap_service.py`; every match must be a domain field/query, never a log message. Commit: `feat(P2.T4): bootstrap legacy progress baseline`.

### Task 4: P3.T2 — Curated candidates and SelectionPolicy v1

**Canonical references:** ALG-03/ALG-04 and P3.T2 bounds. Use fake Curriculum/Progress/History ports for owner tests.

**Files:**
- Create: `backend/app/domain/selection_ports.py`
- Create: `backend/app/domain/selection_policy.py`
- Create: `backend/app/services/next_activity_service.py`
- Test: `backend/tests/test_next_activity.py`

- [ ] **Step 1: RED — port/candidate contracts.** Test curated lexical recognition/retrieval and construction complete/transform ActivitySpecs, one target, deterministic scorer, published-only marker, burden bounds, and AI candidate port with no implementation/network. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_next_activity.py`; expect missing contracts/provider.
- [ ] **Step 2: GREEN then REFACTOR — pure ports/provider.** Implement one candidate assertion, rerun `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_next_activity.py` GREEN, then refactor one provider helper and rerun it.
- [ ] **Step 3: RED — validity policy.** Reject unready HARD target, lexical unknown burden, construction >1 unknown SOFT item or missing gloss, mismatched scorer/operation/target; never assign arbitrary penalty. Expect invalid candidates accepted.
- [ ] **Step 4: GREEN then REFACTOR — strict validation.** Implement one validity assertion, rerun the exact Selector command GREEN, then refactor one validator and rerun it.
- [ ] **Step 5: RED — intent precedence.** With fixed UTC fakes, assert due REVIEW > weak STRENGTHEN > eligible ACQUIRE > ASSESS; unseen never ASSESS; future bootstrap hold excludes ACQUIRE; empty/no active/no valid/budget cases return exact decision codes. Expect missing selector.
- [ ] **Step 6: GREEN then REFACTOR — ALG-03 intent.** Implement one intent assertion, rerun the exact Selector command GREEN, then refactor one branch helper and rerun it.
- [ ] **Step 7: RED — daily acquisition budget.** Test distinct first completed ACQUIRE target per UTC day, retry/multiple activity dedupe, legacy baseline excluded, due review still selectable at limit. Expect wrong counts.
- [ ] **Step 8: GREEN then REFACTOR — history port count.** Implement one budget assertion, rerun the exact Selector command GREEN, then refactor one history query adapter and rerun it.
- [ ] **Step 9: RED — rank/fingerprint determinism.** Permute input row/JSON order; assert exact intent-specific rank components, target/fingerprint tie-break, ALG-04 equality, byte-stable decision, stable reasons/version.
- [ ] **Step 10: GREEN then REFACTOR — canonical rank.** Implement one rank/fingerprint assertion, rerun the exact Selector command GREEN, then refactor one tuple/fingerprint helper and rerun it.
- [ ] **Step 11: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_next_activity.py` twice, `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_next_activity.py -k 'does_not_mutate or no_network or deterministic'`, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/domain/selection_ports.py app/domain/selection_policy.py app/services/next_activity_service.py tests/test_next_activity.py`, `git diff --check`, `git diff --name-only HEAD | sort`. Commit: `feat(P3.T2): select deterministic next activity`.

### Task 5: P4.T2 — Learning shadow adapter

**Canonical references:** P4.T2, frozen P4.T1 contracts, EVENT-01/ALG-02; legacy learning behavior remains authoritative.

**Files:**
- Create: `backend/app/services/shadow_learning_service.py`
- Modify: `backend/app/services/learning_service.py`
- Modify: `backend/tests/test_learning.py`
- Test: `backend/tests/test_learning_shadow.py`

- [ ] **Step 1: RED — flag-off no queries/writes.** Spy on every domain adapter entry point for new-word complete and rating; assert zero calls and identical legacy response/progress when false. Run learning regression/shadow tests; expect missing seam.
- [ ] **Step 2: GREEN then REFACTOR — early guarded seam.** Add the minimum flag check, rerun `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_learning.py tests/test_learning_shadow.py` GREEN, then clean one seam and rerun it.
- [ ] **Step 3: RED — batch exposure mapping.** Flag on: one terminal run per accepted command, activities/events in input order, Sense+retrieve_form target, exposure/no operation/scorer, citation Form snapshot, legacy-new-word policy/reason, one-day memory due/no competence. Expect missing rows.
- [ ] **Step 4: GREEN then REFACTOR — atomic batch.** Implement one exposure assertion, rerun the exact Learning command GREEN, then refactor one batch helper and rerun it.
- [ ] **Step 5: RED — review self-report mapping.** Assert one single-activity terminal run/event per accepted Again/Hard/Good/Easy, same target, bounded rating response, unknown outcome, legacy-review metadata, memory-only ALG-02 transitions. Expect missing evidence/state.
- [ ] **Step 6: GREEN then REFACTOR — atomic rating adapter.** Implement one rating assertion, rerun the exact Learning command GREEN, then refactor one idempotency helper and rerun it.
- [ ] **Step 7: RED — lost-response and concurrency.** Same accepted request returns original event without orphan run; two concurrent ratings serialize with one accepted legacy transition/event and stable second result/error. Use barriers, not sleeps.
- [ ] **Step 8: GREEN then REFACTOR — pre-side-effect lookup and locks.** Implement one lost-response/race assertion, rerun the exact Learning command GREEN, then refactor one lock helper and rerun it.
- [ ] **Step 9: RED → GREEN → REFACTOR — rollback.** Add only injected event/projector failure and run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_learning_shadow.py -k 'shadow_failure_rolls_back'` RED; implement minimum transaction behavior, rerun GREEN, refactor one orchestration helper, rerun GREEN.
- [ ] **Step 10: RED → GREEN → REFACTOR — privacy.** Add only captured-log redaction and run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_learning_shadow.py -k 'logs_are_redacted'` RED; implement minimum redaction, rerun GREEN, refactor one log helper, rerun GREEN.
- [ ] **Step 11: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_learning.py tests/test_learning_shadow.py tests/test_projection.py`, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/services/shadow_learning_service.py app/services/learning_service.py tests/test_learning.py tests/test_learning_shadow.py`, `git diff --check`, `git diff --name-only HEAD | sort`, and `git diff --name-only HEAD | rg '^(frontend/|backend/app/routers/|backend/app/schemas.py$)'` (expect no output). Commit: `feat(P4.T2): shadow legacy learning evidence`.

### Task 6: P4.T4 — Non-authoritative shadow comparison

**Canonical references:** ALG-03 and frozen P4.T1 comparison contract; requires accepted P4.T2 and P4.T3.

**Files:**
- Create: `backend/app/services/shadow_comparison_service.py`
- Modify: `backend/app/services/next_activity_service.py`
- Test: `backend/tests/test_shadow_comparison.py`

- [ ] **Step 1: Sync exact integrated adapters.** Record `OLD_BASE`, `OLD_TIP`, the P4.T2 source SHA, and exact INT commit containing reviewed P4.T2/P4.T3. Run `git rebase --onto <INT_P4_ADAPTERS_SHA> <P4_T2_SOURCE_SHA> codex/language-assistant-ws-c`, then `git range-diff <OLD_BASE>..<OLD_TIP> <INT_P4_ADAPTERS_SHA>..HEAD`. For every outstanding old/new pair run `git show <OLD_SHA> | git patch-id --stable` and `git show <NEW_SHA> | git patch-id --stable`, comparing the first fields. This drops the already-integrated P4.T2 patch instead of replaying it. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_learning_shadow.py tests/test_quiz_shadow.py`.
- [ ] **Step 2: RED — stable categories.** Add due/new/weak agreement/difference fixtures asserting policy version, legacy intent, selected target, bounded reason codes, and comparison category. Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_shadow_comparison.py`; expect missing service.
- [ ] **Step 3: GREEN then REFACTOR — typed comparison.** Implement one category assertion, rerun `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_shadow_comparison.py` GREEN, then refactor one mapping helper and rerun it.
- [ ] **Step 4: RED — non-authority and isolation.** Snapshot catalog/curriculum/state/history before and after comparison, inject selector/metrics/logger failures, and assert no mutation and no rollback of already valid event/projection. Expect mutation/exception propagation before fix.
- [ ] **Step 5: GREEN then REFACTOR — best-effort diagnostics.** Implement one non-authority/failure assertion, rerun the exact Comparison command GREEN, then refactor one diagnostics boundary and rerun it.
- [ ] **Step 6: RED → GREEN → REFACTOR — disabled paths/privacy.** Add one disabled zero-call assertion and run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_shadow_comparison.py -k 'disabled'` RED, implement, rerun GREEN, refactor, rerun GREEN. Repeat separately with `-k 'logs_are_redacted'` for learner ID/response/translation redaction.
- [ ] **Step 7: Verify and commit.** Run `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_shadow_comparison.py tests/test_next_activity.py tests/test_learning_shadow.py tests/test_quiz_shadow.py`, `/Users/launert/projects/slovnik/backend/.venv/bin/ruff check app/services/shadow_comparison_service.py app/services/next_activity_service.py tests/test_shadow_comparison.py`, `git diff --check`, `git diff --name-only HEAD | sort`, `/Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_shadow_comparison.py -k 'does_not_mutate or disabled or logs_are_redacted'`. Commit: `feat(P4.T4): compare shadow selection non-authoritatively`.
