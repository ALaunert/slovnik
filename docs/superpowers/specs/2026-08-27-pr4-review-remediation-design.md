# PR #4 Review Remediation Design

**Date:** 2026-08-27
**Status:** Approved for specification review
**Scope:** Backend-only remediation of the deep-review findings on PR #4

## 1. Goal

Make the language-assistant foundation safe to merge by fixing the confirmed correctness,
rollout, privacy, runtime-wiring, and schema-parity defects without replacing the legacy public
API or introducing automatic semantic catalog versioning.

## 2. Non-goals

- No public next-activity endpoint or frontend change.
- No automatic inference that a changed translation is the same or a new lexical meaning.
- No replacement of the legacy scheduler, quiz scoring, or vocabulary editor.
- No repair of pre-existing Alembic/ORM drift outside the eleven domain tables introduced by
  revision `20260826_0005`.
- No durable metrics backend; structured application logging remains the initial comparison sink.

## 3. Schema and idempotency parity

Revision `20260826_0005` has not been merged or released, so it remains the single editable domain
foundation migration. Its domain column types, indexes, foreign keys, checks, and constraint names
will be aligned exactly with the ORM metadata. The idempotency constraint will use one canonical
name in Alembic, ORM mapping, exception recovery, and tests.

`ActivityInstance` will also persist its immutable `feedback_policy_version`. That value already
participates in ALG-04 candidate fingerprints but is currently lost when a candidate becomes a
stored activity. Every activity creator must provide it, repository round-trips must preserve it,
and the migration/ORM column is non-null and bounded like the other policy versions.

The migration test suite will compare the migrated domain schema with `Base.metadata` for the
eleven domain tables. Pre-existing legacy-table differences will not be hidden or rewritten.
Concurrency recovery will be exercised on an Alembic-migrated PostgreSQL database, including two
different activities racing on the same learner/idempotency key.

## 4. Native deterministic evidence

`EvidenceSummary` and `learner_target_states` will gain a non-negative
`deterministic_evidence_count`, bounded by total evidence count. Neutral and legacy-bootstrap
baselines start at zero because imported counters are not native evidence.

Projection increments this counter for every native deterministic `response_evaluated` event,
including `correct`, `incorrect`, and `partial`. Exposure, self-report, and model-assisted events do
not increment it. Selector acquisition/assessment classification uses this counter rather than
competence weights. Consequently, deterministic `partial` evidence leaves competence and memory
unchanged but moves the target out of `ACQUIRE` and into `ASSESS` when no higher-priority intent
applies. Replay must reproduce the same value.

## 5. Quiz shadow enrollment and flag transitions

The global flag still guarantees zero domain queries and writes while disabled. When enabled,
shadow participation is decided per quiz attempt:

- a newly started non-empty quiz creates its linked run as today;
- an older attempt with no linked run remains legacy-only instead of failing;
- an attempt with an active, synchronized linked run continues shadow recording;
- if the flag was disabled mid-attempt and legacy answers now exceed mapped domain events, the
  linked run is marked `abandoned` and the attempt remains legacy-only;
- an absent or abandoned run never blocks legacy answer or completion behavior.

Synchronization is exact set parity, not count parity: every persisted legacy `QuizAnswer.id` must
have exactly one event with the corresponding `legacy:quiz-answer:{id}` key and legacy source ref,
and no mapped quiz event may reference an absent answer. A gap emits only the fixed safe diagnostic
category `quiz_shadow_enrollment_gap`; no abandonment reason is added to `PracticeRun` or persisted
elsewhere. The existing `status` and `ended_at` fields remain the complete abandonment contract.

Answer and completion paths will lock `QuizAttempt` before domain run/activity rows, using one lock
order. Completion will re-read answer history while holding that lock. This prevents answer versus
completion races and avoids lock inversion.

Empty quizzes remain legacy-only and do not create synthetic runs. A run left active while the flag
stays disabled is an observable operational artifact; it is converted to `abandoned` only if that
attempt is touched after re-enablement.

## 6. Privacy-safe shadow failures

Quiz shadow operations will use a typed `ShadowQuizFailure` boundary equivalent to learning shadow
failures. Start, answer, and completion roll back both legacy and domain mutations, emit only a
fixed phase/category message, and raise a fixed public infrastructure exception with suppressed
cause. Logs and exception strings must not include learner IDs, question prompts, answers, SQL
parameter payloads, or provider data.

Expected enrollment fallbacks are values, not exceptions, and therefore do not generate error
tracebacks.

## 7. Catalog mapping freshness

The bootstrap representation will store a canonical SHA-256 source fingerprint in the citation
Form bootstrap metadata. The fingerprint covers every `VocabularyItem` field copied into the
catalog aggregate, with normalized portable JSON serialization.

Learning and quiz adapters will resolve mappings through one shared freshness checker. A mapping is
usable only when it has exactly one published Sense, one published citation/fixed Form, and its
stored fingerprint matches the current legacy word. Missing, ambiguous, or stale mappings abort
the shadow transaction through a sanitized typed failure before any learning event is persisted.

`bootstrap_catalog()` remains creation-only and idempotent. It must not silently mutate a published
target or reuse its stable ID after an editor changes meaning. An audit function and documented
deployment command will report counts and identifiers for missing/stale mappings without exposing
learner data. Automatic content versioning and editor integration require a later design because
the current editor cannot distinguish a gloss correction from a new semantic identity.

## 8. Runtime shadow comparison

A new persistence-backed runtime composition module will implement the existing selector ports:

- legacy profile to `LearnerProfile`;
- active technical-pilot curriculum plus frontier evaluation;
- stored learner target states;
- completed activity/acquisition history;
- published catalog snapshots for curated candidates.

The existing deterministic selector and validity policies remain unchanged. History fingerprints
will be reconstructed from immutable activity snapshots and stored generator, scorer, and feedback
policy versions using the canonical fingerprint algorithm; no state is mutated and no version is
inferred from current constants.

`get_daily_new_words()` and `get_review_words()` will invoke comparison after their authoritative
legacy selection has been calculated. The first legacy-selected word is mapped to its canonical
target; an empty list maps to `NONE`, and a weak review maps to `WEAK`. Comparison uses
`ApplicationComparisonLogger`; selector, mapping, metrics, or logger failures remain best-effort and
cannot change returned words or database state. No learner ID, translation, or response is logged.
All persistence-backed comparison reads run in a separate short-lived SQLAlchemy `Session` created
from the request session's bind. A diagnostic database failure therefore cannot leave the
authoritative request session in a failed transaction.

Quiz scoring is not a current next-activity selector and will not trigger comparison in this patch.

## 9. Testing strategy

Every behavior change follows RED-GREEN-REFACTOR:

1. Alembic constraint-name recovery and domain metadata parity.
2. Deterministic partial projection and partial-to-assess selection.
3. Quiz off-to-on, on-to-off-to-on, answer/completion concurrency, and abandoned-run fallback.
4. Quiz exception/log redaction with an unbounded-looking sentinel answer.
5. Missing, ambiguous, fresh, and stale catalog mapping checks plus audit output.
6. Endpoint-level new/review comparison invocation and diagnostic failure isolation.

Final verification includes Ruff, the full flag-off backend suite, targeted flag-on shadow tests,
Alembic upgrade/downgrade, PostgreSQL idempotency/concurrency tests, privacy searches, and
`git diff --check`. `docs/product-state.md`, the SDD progress record, and deployment instructions
will be updated with only verified behavior and remaining limitations.

## 10. Acceptance criteria

- All six Important review findings have regression tests that fail before their fixes.
- Domain migration and ORM metadata agree, and deployed constraint names drive recovery correctly.
- A deterministic partial event cannot be selected as unseen acquisition.
- Changing the feature flag cannot turn an otherwise valid legacy quiz request into a 500.
- No stale catalog mapping can receive new evidence.
- Real new-word/review requests attempt non-authoritative comparison when enabled.
- Injected quiz shadow failures cannot expose learner-controlled content in logs or exceptions.
- Existing public routes, schemas, successful response bodies, and authoritative legacy decisions
  remain unchanged.
