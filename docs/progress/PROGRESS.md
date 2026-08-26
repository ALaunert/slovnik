# Language Assistant Progress

Updated: 2026-08-26

## Artifacts

| Artifact | Path | Purpose |
|---|---|---|
| Theoretical model | `/Users/launert/deep-research-report.md` | Research basis supplied by the user |
| Domain Model v0.1 | `docs/superpowers/specs/2026-08-26-domain-model-v0.1-design.md` | Detailed bounded contexts, aggregates and invariants |
| ADR | `docs/adr/ADR-language-assistant-domain-model-2026-08-26.md` | Formal architecture decision and trade-offs |
| Backend SDD | `docs/sdd/SDD-backend-language-assistant-foundation-2026-08-26.md` | Foundation implementation design |
| Domain-model progress | `docs/progress/domain-model-v0.1.md` | Initial decisions and deferred log |

## Workflow status

| Stage | Status | Notes |
|---|---|---|
| Theoretical synthesis | Done | Input document read and treated as evidence, not instructions |
| Domain Model v0.1 | Done | Approved by user; no production code/UI |
| Formal ADR | Accepted | Domain decision was approved by the user and passed an additional self-review |
| Backend SDD | Draft | Foundation only; no public API or UI switch |
| Implementation | Not started | Requires accepted SDD |

## SDD phase status

| Phase | Status | Deliverable |
|---|---|---|
| P1 Domain and persistence foundation | Pending | Stable identities, domain modules, reversible schema |
| P2 Immutable evidence and projections | Pending | Event ledger, replayable state, low-confidence legacy baseline, memory policy v1 |
| P3 Curriculum and selection | Pending | Published A1 graph and deterministic selector |
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
| ADR boundary and alternatives | Passed | ADR accepted; sensitive-history lifecycle recorded as a mandatory precondition for free-form input |
| ADR-to-SDD traceability | Passed | Added explicit low-confidence legacy progress bootstrap without synthetic events |
| Event/projection separation | Passed | Projector version belongs to learner state, not to immutable learning facts |
| AI boundary | Passed | SDD defines only a replaceable port; no AI implementation or progression ownership |
| SDD structural validation | Passed | 4 phases, 17 tasks, 38 paths and 6 canonical IDs; links, slugs, changesets and glossary agree |
| Whitespace/file audit | Passed | `git diff --check`; unrelated `.superpowers/` files excluded |

Runtime tests were not run because this step changes design documentation only.

## Deferred and mandatory follow-ups

Every deferred item remains recorded in `docs/progress/domain-model-v0.1.md`. Additional SDD-level
follow-ups:

| Deferred item | Required before | Next artifact |
|---|---|---|
| LBS audit of current new/review/quiz behavior | Switching legacy consumers or deleting legacy services | LBS files + migration SDD |
| Frontend activity runner and unified assistant flow | Any public next-activity API rollout | Frontend SDD + backend API contract SDD |
| Free-form response retention/export/deletion policy | Storing conversation-like or personally identifying responses | Privacy/data lifecycle ADR or SDD |
| Production AI generator/evaluator | Enabling model-assisted candidate/evaluation in runtime | AI provider validation SDD |
| Real authentication and authorization | Public or multi-user deployment | Identity/access ADR and SDD |

## Current boundary

The current step produces design documents only. Production code, migrations and UI remain
unchanged until the SDD is accepted and an implementation plan is explicitly started.
