# Strong Document Audit — Language Assistant v0.1

Date: 2026-08-26

## Scope

The audit compared the theoretical model, Domain Model v0.1, accepted ADR, backend SDD, current
product audit, database migrations, learning/review services, quiz lifecycle and frontend recall
semantics. It reviewed domain meaning, aggregate boundaries, schema feasibility, migration safety,
idempotency, concurrency, replay, privacy, MVP scope and A1→C2 extensibility.

## Verdict

The four-context modular-monolith decision remains sound. The previous SDD was structurally valid
but not implementation-ready: several cross-document invariants were underspecified or mutually
inconsistent. The audit corrected those defects without adding production code, UI or AI runtime.

## Findings and resolutions

| Severity | Finding | Resolution |
|---|---|---|
| High | Russian→Serbian recall was mapped to `Form`, fragmenting one sense across realizations | Default target is now `Sense + retrieve_form`; expected `Form` lives in the activity snapshot |
| High | Quiz repeat produced two events for one terminal activity | Every accepted attempt now owns a separate linked `ActivityInstance`; one activity has at most one event |
| High | Practice order depended on timestamps | Added unique per-run `sequence_number`; retries append deterministically |
| High | New-word exposure could not satisfy mandatory exercise `operation`/scorer | Added explicit `activity_kind`; exposure has no operation/scorer, exercise requires both |
| High | Service-only locking could not guarantee one first active curriculum version | Added a partial unique index and a concurrent-first-publish test |
| High | Concurrent first events for a learner/target had no safe state-row creation algorithm | Required conflict-safe state materialization followed by row locking |
| High | Late events could make incremental state differ from replay | Late `occurred_at` triggers target-local canonical replay |
| High | Mutable legacy seed disappeared into current state, so later replay had no stable starting point | State now preserves a frozen neutral/legacy baseline; replay is baseline plus immutable events |
| High | Self-rated review gave zero memory credit and would stay permanently due in shadow state | Self-report still gives no competence credit but updates memory through explicit v1 rating rules |
| High | Exposure-only state was immediately eligible for ACQUIRE again | First exposure now creates a one-day acquisition hold/retrieval due without competence credit |
| High | New-word exposure scheduled memory on recognition while the actual next review retrieves form | Shadow exposure now prepares `Sense + retrieve_form`; it schedules that target without claiming retrieval evidence |
| High | Selector used an undefined weighted sum | Replaced it with an exact intent-specific lexicographic order and stable tie-break |
| High | Current competence could re-lock an already opened prerequisite after one later failure | Added replayable `competence_peak`; failures raise practice priority without revoking readiness |
| High | Global peak calculation gave an exposure a synthetic 0.5 competence value | `competence_peak` now changes only after deterministic success; exposure/self/AI never receive competence credit |
| High | Learning history was called immutable without a learner-data lifecycle | Separated application append-only semantics from administrative erasure/anonymization and gated production shadow writes |
| High | Active curriculum could become unusable if a referenced content target was retired later | Retirement is now forbidden until a replacement curriculum without that reference is active |
| High | Production shadow history could be polluted under the current guessable `userId` access model | Production enablement now requires auth or an explicit trusted/non-public deployment constraint |
| High | Domain required AI-evaluator confidence, but EVENT-01 had only learner self-confidence | Added separate bounded `evaluation_confidence`, required only for model-assisted evaluation |
| Medium | AI candidate generation was drawn as a Practice dependency | Candidate port now feeds selection; evaluator port feeds Practice |
| Medium | Legacy integer foreign keys were declared as `BIGINT` | SDD schema now matches existing `INTEGER` primary keys |
| Medium | Logical `TIMESTAMP` could be read as PostgreSQL timestamp without timezone | SQL-01 now explicitly maps it to SQLAlchemy timezone-aware type and PostgreSQL `TIMESTAMP WITH TIME ZONE` |
| Medium | Independent event/retry foreign keys allowed cross-run or cross-learner references | Composite FKs now bind retry to its run/target and event to one learner/run/activity/target chain |
| Medium | Idempotency equality, nested event bounds and shadow selection provenance were ambiguous | Defined canonical request fingerprint, closed bounded payload shapes and distinct selector/legacy reason codes |
| Medium | Event source/outcome/partial-score combinations were not cross-validated | Defined exposure, deterministic, self-report and model-assisted compatibility rules; partial has no v1 credit |
| Medium | Native event time accepted no bounds, allowing pre-activity or far-future schedules | Added timezone, selected-at and five-minute future-skew validation; imports require a separate policy |
| Medium | Concurrent retry could observe terminal activity before recognizing the just-committed idempotency key | Required idempotency recheck after activity lock; same-key retries return the original event |
| Medium | Run/activity terminal timestamps and event-kind consistency were enforceable only by convention | Added lifecycle/retry CHECKs, locked sequence allocation and activity-kind-bound event FK/CHECK |
| Medium | “All terminal” allowed an empty or cancelled run to be called completed | Completion now requires a non-empty run whose every activity is completed; cancellation belongs to abandonment |
| Medium | Activity could persist a selection-policy version different from its run snapshot | Composite FK now makes the run policy version authoritative for every owned activity |
| Medium | Curriculum was called fully immutable while activation also changed `active -> retired` | Immutability now applies to graph/content; the sole allowed lifecycle transition is explicit |
| Medium | Curriculum status and publication/retirement timestamps could contradict each other | Added a status/timestamp CHECK for draft, active and retired versions |
| Medium | One prerequisite pair could be both HARD and SOFT or point to itself | Edge uniqueness is now independent of kind, and self-edges are rejected |
| Medium | Daily acquisition budget had no exact day/count semantics | v1 counts distinct first ACQUIRE targets per UTC day; learner-local timezone is explicitly deferred |
| Medium | Selector text still mentioned an expected-success heuristic despite forbidding uncalibrated probabilities | v1 now records only observable difficulty features and does not estimate expected success |
| Medium | Activity fingerprint omitted generator/scorer kind and feedback policy | ALG-04 now includes every versioned field that can change presented or evaluated behavior |
| Medium | `Submission` was modeled as an entity although it had no independent identity, storage or lifecycle | Reduced it to bounded `ResponseSubmission` value object; accepted result becomes the event atomically |
| Medium | New-word/review shadow events had no explicit run boundary, and quiz self-check schedule divergence was implicit | Defined batch/single-activity terminal runs and recorded `AGAIN +10m` as an expected non-authoritative shadow difference |
| Medium | CEFR on the curriculum-version row encouraged one-level versions | Removed it; stable node outcome codes carry CEFR association and versions remain cumulative/extensible |
| Medium | Target condition canonicalization allowed cross-runtime ambiguity | Restricted values, rejected floats/NFC key collisions and fixed exact JSON serialization |
| Medium | Current three-word seed could be mistaken for A1 course coverage | Renamed it a technical A1 pilot and added a mandatory curated-content gate |
| Medium | Historical `QuizAnswer` import was promised by the broad migration design but not needed by foundation | Explicitly deferred until legacy retirement/analytics; P4 only dual-writes new answers |

## Remaining implementation gates

- The backend SDD remains Draft and requires explicit acceptance before implementation.
- Production shadow writes require a retention/export/delete or anonymization decision.
- Production shadow writes also require real auth or an explicit trusted/non-public deployment constraint.
- A public unified assistant requires an LBS migration audit, backend API contract, frontend SDD,
  real access control and a curated A1 content/curriculum pack.
- Historical quiz import is required before legacy quiz tables are retired or old evidence is used
  for analytics; it is not required for the additive foundation.
- Production AI generation/evaluation remains a separate validation SDD and cannot own progression.

## Traceability spot checks

| Theoretical invariant | Domain decision | SDD implementation point |
|---|---|---|
| Language, curriculum, competence, memory and activity are distinct | Four contexts; memory is a policy inside Learner Progress | P1 catalog/curriculum/practice/state tables and pure domain modules |
| KC = target × capability × modality × condition | `TargetSpec` value object | DTO-01 and ALG-01 |
| Exposure is not retrieval; recognition is not production | Separate event kind and capability-specific targets | SQL-01 activity kind, EVENT-01 and ALG-02 credit rules |
| Competence differs from current retrievability | Separate competence weights/peak and memory schedule | `learner_target_states`, projector and frontier policy |
| Curriculum constrains adaptation | HARD/SOFT graph before ranking | P3.T1 and ALG-03 |
| Raw observations must survive model changes | Immutable event plus versioned, replayable projection | EVENT-01, frozen baseline, ALG-02 and one-event-per-activity constraint |
| AI is optional and untrusted | Candidate/evaluator ports without progression authority | P1 domain ports, P3 curated default, separate future AI SDD |
| Serbian form–meaning and constructions cannot be flat cards | `LexicalUnit`, `Sense`, `Form`, `Construction` | P1 catalog schema and Sense-based lexical targets |

## Verification

Structural validation covers 4 phases, 17 tasks, 39 paths and 7 canonical IDs. SQL-01 executes on
SQLite with all 11 tables and negative checks for curriculum lifecycle/edge shape, active-version
uniqueness, cross-version edges, run/activity lifecycle and policy consistency, same-run retry,
event ownership/target/kind and event uniqueness. All canonical algorithms remain within 25 lines.
Final command evidence is mirrored in `docs/progress/PROGRESS.md`.
