# Domain Model v0.1 Progress

Updated: 2026-08-26

## Current status

| Milestone | Status | Evidence |
|---|---|---|
| Read current product audit and README | Done | `docs/product-state.md`, `README.md` |
| Read theoretical system model | Done | `/Users/launert/deep-research-report.md` |
| Audit current entities and learning flows | Done | Read-only review of backend/frontend and migrations |
| Select bounded-context decomposition | Approved | Four-context modular monolith |
| Approve aggregate/entity/value-object model | Approved | User confirmation on 2026-08-26 |
| Approve relations, invariants, assistant flow and AI boundary | Approved | User confirmation on 2026-08-26 |
| Write Domain Model v0.1 | Done | `docs/superpowers/specs/2026-08-26-domain-model-v0.1-design.md` |
| Independent self-review | Done | Research/MVP/current-state passes recorded below |
| Formal ADR review | Done | Accepted ADR in `docs/adr/ADR-language-assistant-domain-model-2026-08-26.md` |
| Backend foundation SDD | Draft | Four phases in `docs/sdd/SDD-backend-language-assistant-foundation-2026-08-26.md` |
| Production code or UI work | Not started | Explicitly outside current task |

## Durable decisions

- AI/LLM is not the foundation of the learning process.
- AI may generate candidate exercises or evaluate ambiguous responses through replaceable ports.
- Core is a constrained adaptive loop over curriculum, learner competence, memory and activities.
- The MVP uses four bounded contexts: Language Catalog, Curriculum, Practice & History, Learner Progress.
- `LearningEvent` is immutable historical evidence; learner state is a replayable projection.
- Competence and memory remain separate.
- One MVP activity has one primary elicited target.
- A modular monolith is preferred over early service decomposition.

## Self-review record

Completed on 2026-08-26 without an external model, as requested by the user.

| Pass | Result | Corrections made |
|---|---|---|
| Theoretical consistency | Passed | Kept content, curriculum, activity/history, competence and memory semantically separate; made `TargetSpec` explicit in the relation graph |
| MVP/YAGNI | Passed | Kept four contexts and seven aggregate roots; retained embedded examples and only four active exercise operations |
| Current-product compatibility | Passed | Preserved stable legacy mappings, low-confidence progress bootstrap and partial quiz evidence without inventing history |
| AI boundary | Passed | Added explicit `MODEL_ASSISTED` evaluation provenance/confidence and prohibited direct state mutation |

The review also generalized `WordForm` to MVP entity `Form`, so one aggregate can represent both
inflected word forms and fixed MWE forms without introducing a second hierarchy. A future rich
linguistic ontology may split this type when a concrete scenario requires it.

## Deferred log

Nothing in this table may be silently dropped. When a return trigger occurs, the item must move
into a new design/SDD or be explicitly rejected with a recorded reason.

| Deferred item | Why not in MVP | Return trigger | Expected future home |
|---|---|---|---|
| Full Serbian linguistic ontology | No A1 activity currently needs every relation | First approved scenario requiring rich aspect, clitic, derivation or prosody semantics | Language Catalog / Knowledge extension |
| Separate `GrammarFeature`, `GovernmentFrame`, `AgreementRule`, `AspectRelation` entities | `Construction + MorphosyntacticFeatures` covers initial use cases | A rule must be reused/versioned independently across multiple constructions | Language Catalog |
| Independent annotated sentence corpus | Embedded examples are sufficient and cheaper initially | The same example must serve multiple targets/activities or requires independent governance | Language Catalog content corpus |
| All word forms and paradigms | Creates unused data and editorial burden | A productive morphology activity requires form generation beyond curated forms | Language Catalog morphology extension |
| Audio/listening state | MVP has no reliable audio observations | Curated audio activities are accepted into MVP scope | Target taxonomy and Learner Progress |
| Speech/pronunciation/prosody scoring | High evaluation uncertainty and no current input pipeline | Reliable recording and scoring workflow is designed | Practice evaluator + Catalog phonology |
| Multi-primary-target activities | Makes evidence attribution ambiguous | A real scenario cannot be represented with one primary target | Practice & History |
| Incidental-KC learning credit | Evidence weights are unvalidated | Delayed outcome data can compare incidental exposure with retrieval | LearnerStateProjector |
| Remaining exercise primitives | No active MVP scenario needs them | Accepted activity requires `CONSTRUCT`, `COMPREHEND`, `PRODUCE`, `REPAIR` or `IMITATE` | Practice taxonomy |
| Full FSRS or fitted memory model | Insufficient history for trustworthy calibration | Enough longitudinal retrieval events and delayed outcomes exist | MemoryPolicy |
| IRT/BKT/deep KT | Premature statistical complexity | Baseline projections show measurable predictive limitations on adequate data | LearnerStateProjector |
| Bandits or RL | Reward and logged-policy support are absent | Controlled experiments and delayed reward instrumentation are available | SelectionPolicy |
| Automatic prerequisite discovery | Expert A1 graph is sufficient | Learner path data reveals systematic sequencing failures | Curriculum tooling |
| Unrestricted AI exercise generation | Linguistic validity and scoring cannot be guaranteed | Validated constrained generation pipeline and safe fallback exist | `ActivityCandidateProvider` adapter |
| Production AI response evaluator | Not required to establish core domain | A free-response scenario cannot be scored deterministically | `ResponseEvaluator` adapter |
| Authentication and authorization | Orthogonal to learning domain redesign | Product prepares multi-user or public deployment | Identity/access context |
| Native mobile and UI redesign | Explicitly outside Domain Model task | Separate UX/product scope is approved | Dedicated UX/implementation specs |

## Next expected step

Review and accept the backend foundation SDD. After acceptance, create an executable implementation
plan for P1; do not start production code from the Domain Model or a draft SDD alone. Initiative-wide
status and all mandatory follow-ups are mirrored in `docs/progress/PROGRESS.md`.
