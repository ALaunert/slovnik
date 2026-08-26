# Language Assistant Progress

Updated: 2026-08-26

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
| Implementation | Ready for Gate 0 | Three workstreams start only after INT freezes shared contracts |

## SDD phase status

| Phase | Status | Deliverable |
|---|---|---|
| P1 Contracts and context foundations | Pending | Gate 0, exclusive context ownership, registry and reversible schema |
| P2 Immutable evidence and projections | Pending | Event ledger, replayable state, low-confidence legacy baseline, memory policy v1 |
| P3 Curriculum and selection | Pending | Technical A1 pilot graph and deterministic selector |
| P4 Legacy shadow integration | Pending | Feature-flagged dual-write without API changes |

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

Runtime tests were not run because this step changes design documentation only.

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

The design stage is complete and SDD revision 2 is accepted. Production code, migrations and UI
remain unchanged; the next implementation step is INT/P1.T1 Gate 0 contract freeze.
