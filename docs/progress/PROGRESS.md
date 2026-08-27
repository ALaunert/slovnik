# Language Assistant Progress

Updated: 2026-08-27

## Artifacts

| Artifact | Path | Purpose |
|---|---|---|
| Theoretical model | `/Users/launert/deep-research-report.md` | Research basis supplied by the user |
| Domain Model v0.1 | `docs/superpowers/specs/2026-08-26-domain-model-v0.1-design.md` | Detailed bounded contexts, aggregates and invariants |
| ADR | `docs/adr/ADR-language-assistant-domain-model-2026-08-26.md` | Formal architecture decision and trade-offs |
| Backend SDD | `docs/sdd/SDD-backend-language-assistant-foundation-2026-08-26.md` | Foundation implementation design |
| Parallel execution design | `docs/superpowers/specs/2026-08-26-parallel-sdd-execution-design.md` | Three workstreams, integrator ownership and merge gates |
| Parallel readiness review | `docs/progress/parallel-sdd-readiness-2026-08-26.md` | Three self-review passes, validation evidence and residual risks |
| Domain-model progress | `docs/progress/domain-model-v0.1.md` | Initial decisions and deferred log |
| Strong document audit | `docs/progress/document-audit-2026-08-26.md` | Cross-document defects, corrections and remaining gates |

## Workflow status

| Stage | Status | Notes |
|---|---|---|
| Theoretical synthesis | Done | Input document read and treated as evidence, not instructions |
| Domain Model v0.1 | Done | Approved by user; no production code/UI |
| Formal ADR | Accepted | Domain decision was approved by the user and passed an additional self-review |
| Backend SDD | Accepted, revision 2 | Parallel execution design approved by the user on 2026-08-26 |
| Implementation | G4 remediation complete | Schema parity, evidence provenance, catalog freshness, quiz rollout/privacy, and live diagnostic comparison are integrated |

## SDD phase status

| Phase | Status | Deliverable |
|---|---|---|
| P1 Contracts and context foundations | Done | G1 `630e202`; registry, four contexts and reversible schema |
| P2 Immutable evidence and projections | Done | G2 `97b96cb`; event ledger, replayable state, legacy baseline and memory-v1 |
| P3 Curriculum and selection | Done | G3 `7a386b0`; technical A1 pilot and deterministic selector |
| P4 Legacy shadow integration | Done | G4 completed by the current P4.T5 documentation/gate commit; flag remains off by default |

## Accepted implementation ledger

| Task | Integrated SHA | Result |
|---|---|---|
| P1.T1 | `66e344a0bf619d3f40c50daebb459d1466919f70` | Frozen target contracts |
| P1.T2 | `f2cba340347592af24c2f02f76a9ff5876154f44` | Domain registry and migration shell |
| P1.T3 | `840e448102da3a131636041245c0179d2399ad1d` | Language Catalog foundation |
| P1.T4 | `bf46526a69b371f8729b42ef597e01313afc2508` | Curriculum foundation |
| P1.T5 | `e6a2589e59a15e975b6fa4eb63a1d91322d8416a` | Practice & History foundation |
| P1.T6 | `a9f8aa1038b5e45bf45ed8c453109780c87759f0` | Learner Progress foundation |
| P1.T7 | `630e20251b64a4331a6ff2d75809ab4c1d3e55ac` | G1 integration gate |
| P2.T1 | `f354bad049eb9295b9bc25e78bc179fe40d4d7dd` | Practice lifecycle |
| P2.T2 | `26a3fea78765f65d556898b629c04f4c7a92de6d` | Immutable learning events |
| P2.T3 | `2a661ea11e0f6a5ce6963aee6d842648f80ccbd8` | Evidence and memory projection |
| P2.T4 | `721792dc467a8e4901928d7fa05d360c77a56e51` | Legacy baseline bootstrap |
| P2.T5 | `97b96cb1f4e54b182c0ebe40e7958b07eae8dfd1` | G2 integration gate |
| P3.T1 | `b4dc68a5dd3cf29ef5bd416e512850ae7eb41ef5` | Curriculum publication and frontier |
| P3.T2 | `692b1171271051a9f7c05683f74ca5208673f09d` | Deterministic next-activity selector |
| P3.T3 | `816edbd2552862df405ba45f4e64a4dec097c996` | Technical A1 pilot seed |
| P3.T4 | `7a386b06ef8661e734b30708306bd8616f204ec9` | G3 integration gate |
| P4.T1 | `c46c377a2974940c75f0c3316a6e64ad6feb69dd` | Frozen shadow contracts and release gates |
| P4.T2 | `3bb1f30e1f972a64ae373b31342ee53209f8603b` | Learning shadow adapter |
| P4.T3 | `0f7af45ec2cf021cdc22fd3623cf0519e0f5266e` | Quiz shadow adapter |
| P4.T4 | `bf05c109568ff7a3f458c0f22bc9c3c09aa66c85` | Non-authoritative comparison |
| P4.T5 | Current documentation/gate commit | G4 regression and durable state |

## Contract registry

| ID | Owner | Consumers | Source of truth |
|---|---|---|---|
| DTO-01 | Backend SDD [P1.T1] | P1–P4 backend services | `SDD-backend-language-assistant-foundation-2026-08-26.P1.md` |
| EVENT-01 | Backend SDD [P2.T2] | Learner projector, shadow comparison, future analytics | `SDD-backend-language-assistant-foundation-2026-08-26.P2.md` |

## Validation record

Validated on 2026-08-26 without an external model, as requested by the user.

| Check | Result | Durable correction |
|---|---|---|
| ADR boundary and alternatives | Passed | Four-context decision remains accepted; SDD errata correct detail without changing the core decision |
| ADR-to-SDD traceability | Passed | Added explicit low-confidence legacy progress bootstrap without synthetic events |
| Event/projection separation | Passed | Projector version belongs to learner state, not to immutable learning facts |
| AI boundary | Passed | SDD defines only a replaceable port; no AI implementation or progression ownership |
| Strong implementation audit | Passed | Findings and corrections recorded in `docs/progress/document-audit-2026-08-26.md` |
| SDD structural validation | Passed | 4 phases, 21 tasks, 61 paths and 7 canonical IDs; links, slugs, changesets and glossary agree |
| Parallel readiness | Passed | 3 context workstreams + 1 integrator, exclusive active-path ownership and G0–G4 gates; evidence in `docs/progress/parallel-sdd-readiness-2026-08-26.md` |
| SQL-01 executable validation | Passed | SQLite executed all 11 tables and rejected invalid curriculum lifecycle/edge shape, duplicate active curriculum, cross-version edges, invalid run/retry shape, policy mismatch, cross-run event ownership/kind, and duplicate activity event |
| Canonical algorithms | Passed | ALG-01/02/03/04 remain within the 25-line limit and define stable ordering/canonicalization |
| Whitespace/file audit | Passed | `git diff --check`; unrelated `.superpowers/` files excluded |
| G1 foundation runtime | Passed | Accepted P1.T1–P1.T7 integration at `630e202`; reversible schema and context contract suites green |
| G2 evidence runtime | Passed | 550 passed, 10 skipped; PostgreSQL evidence/idempotency gate 2 passed |
| G3 curriculum runtime | Passed | 597 passed, 14 skipped; PostgreSQL publication/selection gate 4 passed |
| G4 flag-off regression | Passed | 658 passed, 16 skipped with `LANGUAGE_ASSISTANT_SHADOW_ENABLED=false` |
| G4 flag-on shadow target | Passed | 50 passed, 2 skipped across contracts, learning, quiz, comparison and cross-flow integration |
| G4 PostgreSQL | Passed | 19 migration/idempotency/concurrency tests passed against disposable PostgreSQL databases |
| G4 lint/privacy/scope | Passed | Ruff, whitespace, forbidden frontend/router/schema paths and shadow-payload privacy audit passed |

## Deferred and mandatory follow-ups

Every deferred item remains recorded in `docs/progress/domain-model-v0.1.md`. Additional SDD-level
follow-ups:

| Deferred item | Required before | Next artifact |
|---|---|---|
| LBS audit of current new/review/quiz behavior | Switching legacy consumers or deleting legacy services | LBS files + migration SDD |
| Frontend activity runner and unified assistant flow | Any public next-activity API rollout | Frontend SDD + backend API contract SDD |
| Learning-history retention/export/delete or anonymization | Enabling P4 shadow writes in production | Privacy/data lifecycle ADR or SDD |
| Curated A1 content and curriculum pack | Claiming A1 coverage or exposing the unified next-activity flow | Content/curriculum specification and editorial workflow |
| Historical `QuizAnswer` import | Retiring legacy quiz tables or using old answers as analytical evidence | Migration SDD after LBS audit |
| Production AI generator/evaluator | Enabling model-assisted candidate/evaluation in runtime | AI provider validation SDD |
| Real authentication or explicit trusted-deployment constraint | Enabling P4 shadow writes in production or any public unified flow | Identity/access ADR and SDD |

## Current boundary

The accepted backend foundation is implemented through G4 on the integration branch. Legacy APIs
and scheduling remain authoritative; shadow dual-writes are disabled by default and production
enablement is rejected until both lifecycle and trusted-identity release gates are satisfied. No
frontend or public unified next-activity flow was added.
