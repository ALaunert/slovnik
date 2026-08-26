# Language Assistant Parallel Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Project execution override:** The accepted SDD requires `superpowers:dispatching-parallel-agents` with three simultaneously active, path-disjoint Codex implementers. Do not use `subagent-driven-development` as the primary executor. Every implementer must use `superpowers:test-driven-development`.

**Goal:** Deliver P1.T1–P4.T5 as a backend-only, shadow-first foundation through gates G0–G4 without changing public APIs or UI.

**Architecture:** INT owns frozen contracts, registries, the single migration, cross-context integration, gates, and durable documentation. WS-A owns Catalog/Curriculum, WS-B owns Practice/History, and WS-C owns Progress/Selection; active workstreams never edit the same tracked path.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, SQLite, pytest, Ruff, Git worktrees, Codex parallel agents

---

## 1. Canonical inputs and non-goals

- Base commit: `64c1dbb02126b1779d5e578c09b8aa993be3ccc1`.
- Canonical contracts: DTO-01/ALG-01 and SQL-01 in `docs/sdd/SDD-backend-language-assistant-foundation-2026-08-26.P1.md`; EVENT-01/ALG-02 in P2; ALG-03/ALG-04 in P3.
- Canonical architecture: `docs/adr/ADR-language-assistant-domain-model-2026-08-26.md` and `docs/superpowers/specs/2026-08-26-parallel-sdd-execution-design.md`.
- No frontend files, public route/schema changes, unified-flow API, production AI adapter, new DI framework, or Unit of Work abstraction.
- `LANGUAGE_ASSISTANT_SHADOW_ENABLED` remains false by default and cannot be enabled in production without the recorded privacy and identity gates.

## 2. Worktrees and branch discipline

| Role | Worktree | Branch | Creation point |
|---|---|---|---|
| INT | `/Users/launert/projects/slovnik-worktrees/int` | `codex/language-assistant-foundation` | exact base commit |
| WS-A | `/Users/launert/projects/slovnik-worktrees/ws-a` | `codex/language-assistant-ws-a` | exact verified G0 commit |
| WS-B | `/Users/launert/projects/slovnik-worktrees/ws-b` | `codex/language-assistant-ws-b` | exact verified G0 commit |
| WS-C | `/Users/launert/projects/slovnik-worktrees/ws-c` | `codex/language-assistant-ws-c` | exact verified G0 commit |

- [ ] Before creation, verify each path/branch is absent with `git worktree list --porcelain` and `git branch --list 'codex/language-assistant-*'`.
- [ ] Create workstreams only after G0 with `git worktree add <absolute-path> -b <branch> <G0_SHA>`.
- [ ] Run all commands from the owning worktree; reuse `/Users/launert/projects/slovnik/backend/.venv/bin/*` without installing dependencies into tracked paths.
- [ ] Before every wave, verify `git rev-parse HEAD`, `git status --short`, and exact synchronization commit.
- [ ] Synchronize only at a gate boundary. Drop already-integrated source commits and replay only outstanding commits with `git rebase --onto <EXACT_GATE_SHA> <LAST_INTEGRATED_SOURCE_SHA> <BRANCH>`. Record `git log --oneline --decorate -8` before/after, verify outstanding commits with `git range-diff <OLD_BASE>..<OLD_TIP> <EXACT_GATE_SHA>..<NEW_TIP>`, and compute each ID with `git show <COMMIT_SHA> | git patch-id --stable`; compare the first field for the old/new commit pair. Never rebase the whole branch onto a gate that already contains cherry-picked equivalents, and never resolve semantic conflicts with `ours`/`theirs`.
- [ ] Preserve the user's untracked `/Users/launert/projects/slovnik/.superpowers/` and never stage it.

## 3. Exclusive ownership

| Owner | Exclusive tracked paths while active |
|---|---|
| INT | `backend/app/domain/__init__.py`, `domain/shared.py`, `domain/target.py`, `domain_models/__init__.py`, `repositories/__init__.py`, `backend/app/db.py`, `backend/alembic/env.py`, `backend/alembic/versions/20260826_0005_domain_foundation.py`, `backend/app/config.py`, `backend/tests/conftest.py`, cross-context/integration tests, `docs/product-state.md`, `docs/progress/*`, these five plans |
| WS-A | `domain/catalog.py`, `domain/curriculum.py`, `domain/curriculum_policy.py`, `domain_models/catalog.py`, `domain_models/curriculum.py`, `repositories/catalog.py`, `repositories/curriculum.py`, `services/domain_bootstrap_service.py`, `services/curriculum_service.py`, `app/seed.py`, Catalog/Curriculum owner tests |
| WS-B | `domain/practice.py`, `domain/practice_ports.py`, `domain_models/practice.py`, `repositories/practice.py`, `services/practice_service.py`, `services/learning_event_service.py`, `services/shadow_quiz_service.py`, `services/quiz_service.py`, Practice/Event/Quiz owner tests |
| WS-C | `domain/progress.py`, `domain/memory_policy.py`, `domain/selection_policy.py`, `domain/selection_ports.py`, `domain_models/progress.py`, `repositories/progress.py`, projection/bootstrap/selection/learning-shadow/comparison services, Progress/Projection/Selection/Learning-shadow owner tests |

No concurrent group may contain two tasks whose declared changesets intersect. Package exports, migration, shared fixtures, shared contracts, and progress docs are always INT-only.

## 4. DAG, waves, and merge order

```text
P1.T1 -> G0
G0 -> INT:P1.T2 || A:P1.T3 -> A:P1.T4 || B:P1.T5 || C:P1.T6
accepted P1.T2..T6 -> INT:P1.T7 -> G1
G1 -> A:P3.T1 -> A:P3.T3
G1 -> B:P2.T1 -> B:P2.T2
G1 -> C:P2.T3 -> C:P2.T4 -> C:P3.T2
accepted B/C P2 -> INT:P2.T5 -> G2
G2 -> accept A/C P3 -> INT:P3.T4 -> G3
G3 -> INT:P4.T1
P4.T1 -> C:P4.T2 || B:P4.T3
accepted P4.T2/P4.T3 -> sync C -> C:P4.T4
accepted P4.T2..T4 -> INT:P4.T5 -> G4
G4 -> final independent review -> final verification -> branch handoff
```

Merge/cherry-pick order is task order inside each gate, not completion time: P1.T2, P1.T3, P1.T4, P1.T5, P1.T6, P1.T7; then P2.T1–P2.T5; then P3.T1–P3.T4; then P4.T1–P4.T5. P3 commits may exist early but cannot enter INT before G2.

## 5. Task commit protocol

For each SDD task:

- [ ] Dispatch one fresh Codex implementer with `fork_turns="none"`, one task slug, the full corresponding plan task, canonical contract references, allowed changeset, forbidden paths, test commands, and result schema.
- [ ] Implementer reads `AGENTS.md`, `README.md`, `docs/product-state.md`, the named plan task, and only required canonical references.
- [ ] Every behavior named in a task is a separate 2–5 minute microcycle: add one assertion/test → run the exact node/file command and record expected RED → add minimum code → rerun the identical command and record GREEN → make at most one behavior-preserving refactor → rerun the identical command. Never combine GREEN with REFACTOR or two behaviors in one cycle. For changesets without a durable test path (P1.T2, P2.T1, P3.T3), use `/private/tmp/slovnik-<slug>/test_<slug>.py`, run it with `PYTHONPATH=<worktree>/backend`, preserve its transcript, and remove it with `apply_patch` before commit.
- [ ] Implementer runs owner-local tests, Ruff on changed Python files, `git diff --check`, `git status --short`, and a changeset/ownership audit.
- [ ] Implementer creates exactly one commit whose subject contains the task slug, for example `feat(P2.T2): record immutable learning events`.
- [ ] Implementer returns status, commit SHA, changed files, RED/GREEN evidence, verification commands, assumptions, blockers, contract-change requests, and deferred proposals; then stops.
- [ ] INT independently compares `git diff <parent>..<task_sha> --name-only` to the task changeset and reviews SDD invariants before code review. Record `source_sha`, `source_patch_id`, reviewer result, and later `integrated_sha` in the task ledger.
- [ ] A fresh Codex reviewer reviews the commit. Critical/Important findings return before INT admission; the implementer amends/replaces the task commit, returns a new source SHA, and the complete task is re-reviewed. Superseded source SHAs are recorded but never cherry-picked into INT.
- [ ] Minor findings are deferred only when INT records reason, return trigger, future home, and production-gate impact in `docs/progress/domain-model-v0.1.md`.

## 6. Contract-change protocol

- [ ] Dependent implementer stops only the affected task and returns the missing contract, proof from SDD/ADR, affected paths/tasks, compatibility impact, and smallest proposed change.
- [ ] INT rejects scope expansion or creates a separate `contract:` commit on the integrator branch.
- [ ] INT updates contract tests first, observes RED, implements the minimum contract change, obtains GREEN, and runs all contract consumers' tests.
- [ ] A fresh reviewer approves the contract commit before any workstream syncs it.
- [ ] All affected worktrees rebase onto the same contract commit and report their new base SHA; work resumes only then.

## 7. Gate admission and verification

Common command root is the relevant worktree's `backend/`; `PY=/Users/launert/projects/slovnik/backend/.venv/bin`.

| Gate | Required evidence | Exact verification |
|---|---|---|
| G0 | DTO-01, ALG-01, stable exports/wire values, no framework imports | `$PY/pytest -v tests/test_domain_contracts.py`; `$PY/ruff check app/domain tests/test_domain_contracts.py`; `git diff --check` |
| G1 | All context contracts/repositories, metadata discovery, one reversible migration, legacy preservation | `$PY/pytest -v tests/test_domain_contracts.py tests/test_domain_catalog.py tests/test_curriculum_contracts.py tests/test_practice_contracts.py tests/test_progress_contracts.py tests/test_migrations.py`; `$PY/ruff check .`; PostgreSQL target below |
| G2 | Lifecycle, immutable EVENT-01, idempotency, rollback, replay, legacy baseline, PostgreSQL concurrency | `$PY/pytest -v tests/test_practice_contracts.py tests/test_learning_events.py tests/test_projection.py tests/test_legacy_progress_bootstrap.py tests/test_migrations.py`; `$PY/ruff check .`; PostgreSQL target below |
| G3 | Publication/frontier, one-active invariant, selector determinism/budget/fingerprint, no mutation/network | `$PY/pytest -v tests/test_curriculum.py tests/test_next_activity.py tests/test_projection.py`; `SLOVNIK_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://slovnik:slovnik@localhost:5432/postgres' $PY/pytest -v tests/test_curriculum.py -k 'postgresql and concurrent'`; `$PY/ruff check .`; `git diff --check` |
| G4 | Flag-off regression, flag-on adapters/comparison, atomic rollback, privacy, idempotency/concurrency, durable docs | `ENVIRONMENT=test LANGUAGE_ASSISTANT_SHADOW_ENABLED=false $PY/pytest -v`; `ENVIRONMENT=test LANGUAGE_ASSISTANT_SHADOW_ENABLED=true $PY/pytest -v tests/test_domain_shadow_contracts.py tests/test_learning_shadow.py tests/test_quiz_shadow.py tests/test_shadow_comparison.py tests/test_domain_shadow_integration.py`; `ENVIRONMENT=test LANGUAGE_ASSISTANT_SHADOW_ENABLED=true SLOVNIK_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://slovnik:slovnik@localhost:5432/postgres' $PY/pytest -v tests/test_migrations.py`; `$PY/ruff check .`; `git diff --check`; `git diff --name-only 64c1dbb..HEAD | sort`; `git diff --name-only 64c1dbb..HEAD | rg '^(frontend/|backend/app/routers/|backend/app/schemas.py$)'` must print nothing |

PostgreSQL verification (after `docker compose up -d postgres`, adjusting the port only if documented):

```bash
SLOVNIK_TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://slovnik:slovnik@localhost:5432/postgres' \
  /Users/launert/projects/slovnik/backend/.venv/bin/pytest -v tests/test_migrations.py
```

Each gate also requires `git status --short`, a task-SHA ledger, reviewer approval for every admitted commit, and verification run after the final gate commit—not stale branch-local output.

### Candidate integration before permanent admission

- [ ] INT creates a clean validation worktree under `/private/tmp/slovnik-<gate>-validation` from current INT HEAD and writes the gate integration tests there first. Run the exact tests before candidate commits and record RED caused by missing context behavior.
- [ ] Cherry-pick reviewed source commits only into that disposable validation branch, in declared order. Run the exact gate tests, Ruff, migration/concurrency targets, and ownership audit there.
- [ ] If a candidate fails, do not cherry-pick it into INT. Return it to its owner, receive one amended/replacement source commit, recreate the clean validation branch, and repeat complete review/validation.
- [ ] After candidate validation is green, cherry-pick the exact accepted source commits into INT, apply the identical gate-test patch, rerun the commands, and create the one INT gate-task commit.
- [ ] Record `slug | final source SHA | source patch-id | final integrated SHA | integrated patch-id | reviewer | gate`; obtain each patch ID with `git show <SHA> | git patch-id --stable` and require matching first fields. Superseded SHAs remain audit notes, not commits in INT history.

## 8. Rollback and failure behavior

- Unexpected failure invokes `superpowers:systematic-debugging`: reproduce, isolate, form one hypothesis, test it, and fix the root cause; never skip or weaken the assertion.
- A red workstream commit is not integrated to unblock another branch. Independent tracks may continue if their path/contract is unaffected.
- Migration G1 failure: keep legacy tables authoritative, fix the single INT-owned revision, and prove upgrade/downgrade again on both dialects.
- G2 event/projection failure: roll back the entire event/activity/state transaction; do not persist partial evidence.
- G3 selector failure: return `no_activity` only for specified decision codes; do not add fallback selection or AI/network access.
- G4 adapter failure: shadow-enabled legacy mutation and shadow write roll back together; flag-off is the immediate runtime rollback. Comparison failures remain non-authoritative and cannot undo valid evidence.
- If PostgreSQL is unavailable, complete independent SQLite/unit checks but leave the affected gate explicitly unpassed.
- Destructive cleanup, push, PR, or merge to `main` requires user choice after `superpowers:finishing-a-development-branch`.

## 9. Commit admission checklist

- [ ] Exact SDD slug and one-task scope.
- [ ] Changeset is a subset of owner paths and has no frontend/public-schema/router edits.
- [ ] RED proves missing behavior; GREEN and refactor verification are fresh.
- [ ] No canonical contract drift, hidden migration, secret/raw-response logging, AI authority, or feature-flag enablement.
- [ ] `git diff --check`, owner-local Ruff/tests, and fresh independent code review pass.
- [ ] Required assumptions/deferred proposals are accepted or rejected by INT.
- [ ] Gate dependency is green and merge order is respected.

## 10. Completion checklist

- [ ] `docs/progress/PROGRESS.md` records accepted SHAs for P1.T1–P4.T4 and records P4.T5 as completed by the current documentation/gate commit (a commit cannot contain its own SHA). After commit, the final report obtains the P4.T5 SHA from `git log -1 --format=%H` and presents the complete P1.T1–P4.T5 SHA table.
- [ ] G0–G4 have fresh command evidence, including SQLite/PostgreSQL migration round trip and concurrency tests.
- [ ] Full backend regression and Ruff pass on final INT HEAD.
- [ ] Fresh final reviewer approves the full range `64c1dbb..HEAD`; all Critical/Important findings are fixed and re-reviewed.
- [ ] `docs/product-state.md` describes only actual runtime behavior; canonical deferred log contains every new deferred decision.
- [ ] `superpowers:verification-before-completion` and `superpowers:finishing-a-development-branch` are completed without automatic merge/push/cleanup.
