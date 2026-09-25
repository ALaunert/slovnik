# Learning-system implementation plan: P0–P3

Status: approved implementation in progress. Checklist marks verified work; unmarked tasks are pending or externally gated. The plan itself is not evidence that any unmarked task has shipped. Based on the [roadmap](roadmap.md), [review](review.md), [research](research.md), [Serbian resource register](serbian-resources.md), [learning model](learning-model.md), [content pipeline](content-pipeline.md), [audit](audit.md), and current repository. The roadmap's parent IDs and priorities are preserved. Letter suffixes split a parent milestone into independently verifiable work. A conditional task is complete as **not triggered** only when its named trigger was checked and the decision recorded.

## Implementation principles

1. Keep the FastAPI/PostgreSQL four-context monolith and Vue client. Extend the existing catalog, curriculum, practice/history and progress contracts; do not create a learning service, graph database or general example corpus without a demonstrated need.
2. Preserve legacy vocabulary, quiz, review, score and progress behavior until an explicit versioned cutover. Never manufacture missing history or infer old answer keys, contexts, permissions or ownership. Published content and immutable events remain replayable.
3. Treat an issued activity's content, answer policy, source and context family as versioned facts. Keep private keys server-side. A self-rating, assisted answer, repair, exposure and independent scored answer are different evidence. Unknown is not failure.
4. Use reviewed authored content and deterministic validation first. Lexicons/corpora provide candidates and usage evidence, not CEFR, sense, rights or scoring truth. LLM proposals enter only measured P3 experiments and never directly update content or learner state.
5. A finite **written** pilot can run supervised on a true loopback deployment with consented data handling. Every new direct-write route enforces that boundary itself. Remote/public histories require P2-01 and P2-02; hard mastery unlocks require a P2-08 decision. No quiz score or narrow pilot yields a CEFR certificate.
6. Each implementation task must update [product state](../product-state.md) when behavior, architecture, setup, verification or deferred scope changes. Run focused tests, inspect the diff and preserve unrelated files. Where this plan names a proposed path, reuse an existing module if the current code makes that simpler; preserve the domain and test contract.

## Compact execution checklist

- [x] P0-01 — metrics and baseline fixtures
- [x] P0-07 — written pilot and holdout brief
- [x] P0-04 — source and rights manifest
- [x] P0-05 — example and answer fixtures
- [x] P0-02 — frozen quiz answer keys
- [x] P0-08 — unbiased valid choices
- [x] P0-03 — first-attempt result breakdown
- [x] P0-06 — read-only evidence diagnostics
- [ ] P1-03a — reviewed example bank
- [ ] P1-03b — independent example persistence, if triggered
- [x] P1-04a — atomic publication boundary
- [ ] P1-04b — reviewed pack activation
- [ ] P1-05a — bounded answer policy
- [ ] P1-05b — gated backend lifecycle
- [ ] P1-05c — Vue practice flow
- [ ] P1-06a — linked repair evidence
- [ ] P1-06b — reviewed feedback UI
- [ ] P1-08a — selector and budget policy
- [ ] P1-08b — workload and stop UI
- [ ] P1-09a — supervised local flow
- [ ] P1-09b — consented probe protocol/export
- [ ] P1-09c — pilot evaluation/report
- [ ] P2-01a — identity decision/threat model (`blocked_external`: provider/deployment, credential/session, editor authority and independent legacy-claim proof decisions)
- [ ] P2-01b — ownership integration
- [ ] P2-02a — lifecycle policy decision
- [ ] P2-02b — authenticated owner export
- [ ] P2-02c — deletion and retention
- [ ] P2-03 — local days and workload
- [ ] P2-04a — reviewed audio assets
- [ ] P2-04b — listening activity/evidence
- [ ] P2-05a — routines/past pack, if measured gap
- [ ] P2-05b — travel/location pack, if measured gap
- [ ] P2-05c — comparison/arrangements pack, if measured gap
- [ ] P2-06 — srLex trial, if measured gap
- [ ] P2-07 — CLASSLA trial, if measured gap
- [ ] P2-08a — readiness shadow comparison
- [ ] P2-08b — readiness activation, if justified
- [ ] P3-01a — offline memory comparison
- [ ] P3-01b — prospective memory trial, if justified
- [ ] P3-02a — LLM editorial trial
- [ ] P3-02b — LLM response-review trial
- [ ] P3-03a — sequencing simulation
- [ ] P3-03b — controlled sequencing trial, if justified

## Execution record (2026-09-24; review fixes 2026-09-25)

- P0-01: frozen v1 evidence definitions and six hand-reconciled invented histories; 5 eligible first attempts, 4 first successes, 1 repair, 1 assisted success, 1 self-rating, 1 unresolved answer and 1 delayed new-context success. The fixture consistency, quiz and projection tests passed (42 passed, 1 skipped).
- P0-04: file-backed source manifest and use-specific rights validator; no actual source is marked approved. Authored, corpus, translation, audio, attribution, checksum and path-safety tests passed (13 passed). Human rights review remains necessary for real sources.
- P0-06: read-only v1 classifier and adapter distinguish first unaided, confirmed recovery, unverified retry, assisted, self-report, exposure, unresolved and unknown evidence. Mixed first/final verdicts and hints without proven timing stay unknown; recovery requires an incorrect linked parent; delayed probes require a prior known context and explicit held-out marker. Frozen fixture and projection/shadow regressions passed (42 passed, 2 skipped). No projector, public API or scheduler behavior changed.

- P0-07: four-outcome written pilot/holdout manifest and editorial brief remain provisional. Manifest validation, reference, rubric, cycle and family-separation tests passed (7 passed). Serbian L2 approval is a P1 publication gate.
- P0-02: newly issued quiz plans carry private v1 answer keys; grading, self-check reveal and mistake corrections use issued content, while old plans retain legacy behavior. Quiz/shadow regressions passed (42 passed, 1 skipped).
- P0-05: eight synthetic, explicitly unpublishable example/answer fixtures and a contract decision cover scripts, target spans, variants, context/source references, normalization and holdout leakage. Publish validation checks the pilot manifest, approved source-backed outcome/role coverage and exact assessment-answer exposure inside visible input/practice text, translations or answer variants at token boundaries; semantic paraphrase separation still needs editorial review. The unchanged draft passes draft checks and fails publish checks. The P1-03b example-table trigger was checked and is not demonstrated by these fixtures.
- P0-08: multiple-choice construction normalizes/deduplicates labels, searches beyond duplicate candidates in bounded batches, omits an invalid choice item with fewer than two distinct options, and uses fresh issuance randomness rather than a fixed word-ID seed. Quiz/shadow and frontend quiz regressions passed; semantic distractor review remains editorial.
- P0-03: completion response v2 keeps the legacy mixed practice score and adds separate first objective attempts, successful repair count and subjective remembered ratings. Legacy/mixed answer-key plans report unavailable; zero objective denominator reports not measured. Backend quiz/shadow tests passed (56 passed, 1 skipped); all 87 frontend unit tests and Vue typecheck passed. Old cached results display their practice score with unavailable breakdown.
- P1-04a: caller-owned catalog/curriculum publication stages draft content and retirement/activation in one transaction. Preflight resolves referenced owners, written rights, graph/target validity and unrelated IDs; commit rechecks legacy fingerprints and pinned artifact bytes. A stored request fingerprint restricts active retries to matching provenance. Parent locking, final child-set checks and migration guards reject child insertion, moves into/out of non-draft parents, child/parent deletion, reverse parent-status transitions and child status drift. Published-to-retired remains permitted; direct SQL payload edits and unsynchronized direct SQL retirement are outside this guard contract. Fault injection and migration tests protect rollback. The 2026-09-25 follow-up backend run passed 805 tests with disposable PostgreSQL integration enabled; Ruff passed. The synthetic pilot is still inactive.

- P2-01a preparation: identity ADR, 20-route ownership inventory and seven synthetic linking scenarios are recorded in `docs/adr/ADR-production-identity-and-legacy-linking-2026-09-24.md`; the executable inventory check passed. Provider, deployment, credential/session, editor role and independent legacy-claim proof choices remain an external decision. P2-01b is not eligible until that gate closes.

## Ready-to-resume gates (2026-09-24)

The P0 fixtures and pilot brief are review inputs, not approved learning content. P1-03a preparation stopped when automatic approval review rejected a new review-packet test as outside its interpreted authorization; the existing synthetic contract and editorial brief remain available for a qualified reviewer. No rights or educator approval has been inferred.

A [separate AI-provisional private revision contract](a1-private-prototype-brief.md) now narrows authoring to four written tasks, one target each, Latin only and one immediate candidate assessment family per outcome. Its 16 family IDs are reserved slots, not authored items. It does not clear P1-03a, P1-04b, rights, human review or delayed-probe gates; the P0 manifest and eight synthetic fixtures remain test-only. Next: author a separate candidate pack with public prompts/private keys, verify source and language decisions, then run draft preflight without activation.

| Task | Status | Exact resume condition |
| --- | --- | --- |
| P1-03a | `blocked_external` | Qualified Serbian L2 reviewer approves the four-outcome/holdout brief; source text and translation rights are documented item by item, then examples receive recorded bilingual review. |
| P1-03b | `pending_conditional` | After P1-03a, demonstrate a concrete cross-target reuse or independently governed withdrawal that file-backed revisions cannot handle; otherwise record not triggered. |
| P1-04b | `blocked_external` | P1-03a and P1-04a complete, any P1-03b trigger resolved, educator/rights approvals recorded, then preflight and activate a reviewed pack. |
| P1-05a, P1-05b, P1-05c | `blocked_dependency` | Reviewed P1-04b content/answer variants and the preceding task in this chain are available. |
| P1-06a, P1-06b | `blocked_dependency` | P1-05b event lifecycle, then P1-05c UI and linked-repair evidence are available. |
| P1-08a, P1-08b | `blocked_dependency` | P1-05b selector lifecycle, then P1-05c UI and P1-08a policy are available. |
| P1-09a | `blocked_dependency` | P1-04b, P1-05c, P1-06b and P1-08b pass the supervised loopback gate. |
| P1-09b | `blocked_dependency` | P1-09a local flow and explicit consent/retention review before human answers; freeze probes/export before observations. |
| P1-09c | `awaiting_real_world_evaluation` | P1-09b protocol, recruited consenting participants, elapsed 7/28-day windows and blinded Serbian L2 raters. |
| P2-01a | `blocked_external` | Product owner selects provider/deployment, credential and session validation/logout, editor authority, and independent proof for claiming legacy records; review the prepared identity ADR/matrix. |
| P2-01b | `blocked_dependency` | Approved P2-01a identity and legacy-linking decision. |
| P2-02a | `blocked_external` | P1-09b local consent/export design plus product/legal/operations decisions on jurisdiction, retention, deletion and backup periods. |
| P2-02b, P2-02c | `blocked_dependency` | Approved P2-02a policy and P2-01b ownership; deletion additionally needs owner export and backup operations. |
| P2-03 | `blocked_dependency` | P1-08a stable workload policy; coordinate additive timezone profile migration with P2-01b. |
| P2-04a, P2-04b | `awaiting_real_world_evaluation` | P1-09c feasibility and rights-cleared speaker recordings with human audio review; then add modality evidence after P1-05b. |
| P2-05a, P2-05b, P2-05c | `pending_conditional` | P1-09c measures the respective outcome gap; if present, obtain educator/rights approval and publish serially after P1-04b. Otherwise record not triggered. |
| P2-06, P2-07 | `pending_conditional` | P1-09c documents a form or context/frequency gap, with source/output rights and bounded resource budget; otherwise record not triggered. |
| P2-08a, P2-08b | `awaiting_real_world_evaluation` | P1-06a stable repair evidence and P1-09c pilot data permit shadow comparison; activate only after a reviewed threshold/rollout decision. |
| P3-01a, P3-01b | `awaiting_real_world_evaluation` | P1-09c longitudinal consented data and P2-02a lifecycle policy permit offline calibration; a prospective trial additionally needs favorable offline results and an approved protocol. |
| P3-02a | `blocked_external` | P1-03a reviewed examples, rights-cleared experimental inputs and independent human gold decisions. |
| P3-02b | `blocked_external` | P1-05a deterministic scorer, P2-02a consent for response text and independent human gold answers. |
| P3-03a, P3-03b | `awaiting_real_world_evaluation` | P1-08a selector logs, P1-09c pilot data and reviewed contrast contexts permit offline simulation; a trial additionally needs a feasible result and approved protocol. |

## Complete inventory and dependency graph

| Roadmap parent | Plan tasks | Priority and disposition |
|---|---|---|
| P0-01/02/03/04/05/06/07/08 | Same IDs | P0 required; no parent omitted |
| P1-03 | P1-03a, P1-03b | P1; `b` conditional on proven independent reuse/withdrawal |
| P1-04 | P1-04a, P1-04b | P1; transaction boundary before activation |
| P1-05 | P1-05a, P1-05b, P1-05c | P1; scorer, gated lifecycle, then UI |
| P1-06 | P1-06a, P1-06b | P1; repair events before feedback UI |
| P1-08 | P1-08a, P1-08b | P1; policy before workload UI |
| P1-09 | P1-09a, P1-09b, P1-09c | P1; local flow, consented protocol, then study |
| P2-01 | P2-01a, P2-01b | P2; external provider/deployment choice between them |
| P2-02 | P2-02a, P2-02b, P2-02c | P2; approved policy, export, then deletion/retention |
| P2-03 | P2-03 | P2 required for local-day promise |
| P2-04 | P2-04a, P2-04b | P2; rights-cleared assets before modality/evidence |
| P2-05 | P2-05a, P2-05b, P2-05c | P2; each pack requires a measured gap, otherwise record no-go |
| P2-06/07 | Same IDs | P2 optional resource trials, each requires a recorded gap |
| P2-08 | P2-08a, P2-08b | P2; shadow comparison before conditional activation |
| P3-01 | P3-01a, P3-01b | P3 experiment, conditional prospective trial |
| P3-02 | P3-02a, P3-02b | P3 distinct editorial and response-review experiments |
| P3-03 | P3-03a, P3-03b | P3 experiment, conditional controlled trial |

Direct predecessors form the task-level DAG below. Commas mean **all** listed tasks; `?` means a named conditional gate, not a hidden prerequisite. Human decisions are specified in task cards. The parent roadmap numbers P1-01/02/07 remain intentionally vacant after the review moved those ideas to P2-06/07/08.

```text
P0-01 <- ∅                 P0-04 <- ∅
P0-07 <- P0-01             P0-05 <- P0-04,P0-07
P0-02 <- P0-01             P0-08 <- P0-02
P0-03 <- P0-01,P0-02,P0-08    P0-06 <- P0-01

P1-03a <- P0-04,P0-05,P0-07     P1-03b? <- P1-03a,P0-05
P1-04a <- P0-04,P0-05           P1-04b <- P1-03a,P1-04a,(P1-03b if triggered)
P1-05a <- P0-02,P0-05,P0-06,P0-08,P1-04b
P1-05b <- P1-05a                P1-05c <- P1-05b
P1-06a <- P1-05b,P0-06         P1-06b <- P1-05c,P1-06a
P1-08a <- P1-05b,P0-01         P1-08b <- P1-05c,P1-08a
P1-09a <- P1-04b,P1-05c,P1-06b,P1-08b
P1-09b <- P0-01,P0-07,P1-09a   P1-09c <- P1-09b

P2-01a <- ∅                    P2-01b <- P2-01a
P2-02a <- P1-09b               P2-02b <- P2-02a,P2-01b
P2-02c <- P2-02b
P2-03 <- P1-08a                P2-04a <- P0-04,P1-09c
P2-04b <- P2-04a,P1-05b        P2-05a <- P1-04b,P1-09c
P2-05b <- P1-04b,P1-09c       P2-05c <- P1-04b,P1-09c
P2-06? <- P0-04,P0-05,P1-09c P2-07? <- P0-04,P0-07,P1-09c
P2-08a <- P0-06,P1-06a,P1-09c P2-08b? <- P2-08a

P3-01a <- P1-09c,P2-02a       P3-01b? <- P3-01a,P2-01b,P2-02c
P3-02a <- P1-03a,P0-01       P3-02b <- P1-05a,P0-01,P2-02a
P3-03a <- P1-08a,P1-09c      P3-03b? <- P3-03a,P2-01b,P2-02c
```

**Parallel lanes:** P0-04 and P0-01 may start independently. After P0-01, pilot drafting, quiz fixes and read-only evidence work can proceed separately. P1-04a can run alongside editorial P1-03a; frontend P1-05c and backend P1-06a can run after P1-05b. P2 identity/lifecycle design, timezone, audio rights, outcome-pack drafts and bounded resource trials have independent owners after their listed gates. The three P2-05 packs have no mutual dependency; publish them serially against the current active revision to avoid conflicting activations. P3-02a/b can be evaluated independently; no experiment waits for an unrelated P3 experiment.

## Ordered execution sequence

1. **P0 foundation:** P0-01 first; start P0-04 independently; then P0-07→P0-05 and P0-02→P0-08→P0-03; run P0-06 after P0-01. Checkpoint P0 before publishing anything.
2. **P1 content:** obtain Serbian L2 educator approval of the proposed pilot crosswalk; deliver P1-03a, decide P1-03b from P0-05's recorded trigger, deliver P1-04a, then P1-04b. Do not make P2 lexicon/corpus trials blockers.
3. **P1 practice:** P1-05a→P1-05b; then P1-05c and P1-06a; then P1-06b and P1-08a; then P1-08b. Close usability and scoring defects before local enrollment.
4. **P1 evaluation:** P1-09a→P1-09b→P1-09c, allowing the specified 7-/28-day observation windows. Feasibility and results checkpoint precedes decisions about expansion, readiness and models.
5. **P2 production and breadth:** P2-01a→P2-01b and P2-02a→P2-02b→P2-02c are the public-history gate. P2-03 may run alongside them. P2-04a→P2-04b is a separate listening lane. Select and publish P2-05a/b/c in the order the pilot gaps support. Run P2-06/07 only for a documented candidate gap. P2-08a precedes any justified P2-08b; public release also waits for identity/lifecycle and content gates.
6. **P3 experiments:** run P3-01a, P3-02a, P3-02b and P3-03a against frozen baselines when their data gates hold. Run P3-01b and P3-03b only after prespecified offline and operational gates. Record success, failure or inconclusive outcome; adoption requires its own reviewed decision.

## Detailed task specifications

### P0 — evidence and content contracts

P0 adds versioned quiz-plan data, additive result fields, file-backed editorial contracts and read-only diagnostics. It adds no content table, public practice route or replacement scheduler. **Implement P0-01 first.**

#### P0-01 — Define evidence metrics and freeze baseline fixtures

- **Goal:** define exactly what exposure, first unaided scored response, assisted response, retry, self-report, delayed response and unresolved answer mean. Record current behavior separately from desired metrics.
- **Why:** existing quiz and shadow totals mix unlike observations, so later progress claims need a shared denominator before code changes.
- **Dependencies:** none.
- **Affected repository parts:** create `docs/testing/learning-evaluation.md` and small `backend/tests/fixtures/learning/` histories; inspect `backend/app/domain/practice.py`, `backend/app/services/quiz_service.py`, `backend/app/services/learner_projection_service.py` and existing tests.
- **Expected schema/API changes:** none. Specify future metric field meanings, denominators, exclusion and missing-data rules; do not create a mastery percentage.
- **Migration:** none; historical support/context absent from records remains unknown.
- **Acceptance criteria:** independently checked fixture totals cover wrong→correct retry, hint→correct, self-rating, repeated context, delayed new context and ambiguous response. A retry never adds to independent first-attempt success. The old mixed practice score is named explicitly.
- **Tests:** a fixture consistency test checks cases/expected totals; hand-reconcile the truth table and run existing quiz/projection tests as baseline. P0-03/P0-06 later assert their outputs against the frozen fixtures.
- **Complexity:** small.
- **Risk / research uncertainty:** a defined metric can look like a validated proficiency scale; mastery thresholds and useful effect size are not established. Label fixture values as specification examples, not observed learner outcomes.

#### P0-07 — Draft the finite written pilot and holdout brief

- **Goal:** define four proposed communicative outcomes and what an unseen assessment would measure before creating content storage.
- **Why:** a finite task/rubric contract prevents a word list or technical seed from becoming an unsupported CEFR syllabus.
- **Dependencies:** P0-01.
- **Affected repository parts:** proposed `content/curricula/a1-pilot/manifest.json` and a short editorial brief; consult `backend/app/domain/curriculum.py`, `backend/app/services/curriculum_service.py`, `backend/app/seed.py` and `docs/learning/learning-model.md`.
- **Expected schema/API changes:** none; draft file format records outcome ID, CEFR edition/scale/page, written task and rubric, primary target/capability, script conditions, proposed hard/soft edges and held-out prompt family. Use soft-only edges if no hard prerequisite is defensible.
- **Migration:** none; do not replace the technical seed or publish a curriculum.
- **Acceptance criteria:** personal details, request, price information and location information each map to input, practice and a separate assessment family; no outcome implies oral or complete A1 competence. All mappings and sequencing are marked provisional pending a Serbian L2 educator's approval before P1 publication.
- **Tests:** validate unique IDs, resolvable draft references, acyclic proposed hard edges and absence of practice/holdout family overlap; editorial checklist checks each outcome's rubric and scope.
- **Complexity:** medium.
- **Risk / research uncertainty:** the four outcomes, stage order and CEFR crosswalk are product hypotheses. Draft completion needs no teacher approval; P1 publication does. Avoid treating seed edges as pedagogical evidence.

#### P0-04 — Add a minimal source and rights manifest

- **Goal:** make source identity, permitted uses and attribution reviewable before any new pilot material is published.
- **Why:** corpus/container permissions do not establish rights for every source text, translation or recording.
- **Dependencies:** none; can follow P0-07 to use its source cases.
- **Affected repository parts:** proposed `content/sources/`, one focused validator under `backend/app/`, and `backend/tests/test_content_provenance.py`; use the [resource register](serbian-resources.md).
- **Expected schema/API changes:** versioned file schema only, with source/release/checksum when applicable, item/document IDs, separate text/translation/audio rights, intended uses, attribution, evidence URL or agreement, reviewer and date. No HTTP endpoint or source database.
- **Migration:** none; do not relabel legacy or AI-generated text as approved source content.
- **Acceptance criteria:** unknown permission blocks only the relevant publication use; analysis-only material remains usable for approved analysis; authored material points to an author agreement. Attribution output is deterministic for an approved fixture pack.
- **Tests:** approved authored example, unresolved web-text rights despite corpus CC0, BY-SA adaptation, NC restriction, mismatched translation rights, changed release/checksum and missing reviewer/evidence.
- **Complexity:** small.
- **Risk / research uncertainty:** underlying web-text, translation and media rights can differ from a dataset license. Human rights review is still required for disputed uses; the validator enforces recorded permissions, not legal interpretation.

#### P0-05 — Validate pilot example and answer fixtures

- **Goal:** find the smallest stable context, target and answer contract from actual pilot examples, and decide whether embedded examples suffice.
- **Why:** the accepted catalog already embeds examples; a separate table is justified by demonstrated reuse or withdrawal, not by a design sketch.
- **Dependencies:** P0-07 and P0-04.
- **Affected repository parts:** proposed `content/curricula/a1-pilot/` fixtures/validator; inspect `backend/app/domain/catalog.py`, `backend/app/domain/practice.py`, `backend/app/services/domain_bootstrap_service.py`, `backend/app/services/catalog_mapping_service.py` and related catalog tests.
- **Expected schema/API changes:** versioned file/fixture fields for source ID, NFC text, original script, stable context-family ID, target reference/span, reviewed translation and accepted answer variants. No DB/API change. Record any demonstrated need for independent identity or retirement as a later P1 task.
- **Migration:** none. Keep raw `VocabularyItem` example/translation blobs intact; no automated line split or promotion.
- **Acceptance criteria:** a small set of reviewed or clearly draft examples covers both scripts, multi-token targets and answer variation; source and held-out families resolve. The decision note shows which fields can use existing embedded catalog values and immutable activity snapshots, with a concrete trigger for a new table.
- **Tests:** draft-fixture validation rejects missing rights/review, invalid target/span, NFC offset mismatch and duplicate or transliterated assessment leakage; unequal legacy bilingual lines remain readable but are never auto-paired. Inspect sanitized representative legacy shapes before any later schema proposal.
- **Complexity:** medium.
- **Risk / research uncertainty:** examples may be ambiguous or duplicated across holdout families; separate persistence is an unproven need. Do not design a table from fixture field count alone.

#### P0-02 — Freeze issued quiz answer keys

- **Goal:** make grading, self-check reveal and mistake corrections stable through later vocabulary edits.
- **Why:** current grading reads mutable `VocabularyItem` content, so an issued item can change meaning while a learner is answering it.
- **Dependencies:** P0-01.
- **Affected repository parts:** `backend/app/services/quiz_service.py`, `backend/app/schemas.py`, `backend/app/services/shadow_quiz_service.py`, `backend/tests/test_quizzes.py`, `backend/tests/test_quiz_shadow.py`; verify the existing quiz router response boundary.
- **Expected schema/API changes:** new private versioned answer-key fields inside each new `QuizAttempt.question_plan` JSON item; public `QuizStartRead` continues to expose only prompt/options. No new table or required public request field.
- **Migration:** leave stored plans/answers untouched. Branch explicitly on plan version; old active attempts retain legacy grading and are labelled as such. Never backfill a key from current vocabulary. Shadow mapping freshness still applies when its flag is enabled.
- **Acceptance criteria:** newly issued plans use their own keys for all three question types and for the final correction; keys never appear in unrevealed HTTP or service-level public data; old plans remain answerable under documented legacy semantics; flag-off behavior is preserved.
- **Tests:** edit the vocabulary after starting an attempt and verify new grading/reveal/mistake text; both scripts, unknown plan version, old attempt, key privacy, repeat behavior and shadow freshness/enrollment regression.
- **Complexity:** medium.
- **Risk / research uncertainty:** answer snapshots may leak through a public serializer, and old plans cannot gain historical key integrity. Valid alternative spellings still require editorial review.

#### P0-08 — Repair multiple-choice construction

- **Goal:** remove predictable answer position and duplicate choice labels without requiring a new sense inventory.
- **Why:** current forced position and repeated labels make some first-attempt answers less interpretable.
- **Dependencies:** P0-02.
- **Affected repository parts:** `backend/app/services/quiz_service.py`, `backend/tests/test_quizzes.py`, `frontend/tests/unit/quiz.test.ts` where sparse question lists are rendered.
- **Expected schema/API changes:** no new fields; new `question_plan` items may omit a multiple-choice question when fewer than two distinct labels exist. The `QuizStartRead.questions` shape stays the same; `total_questions` reflects actual issued items.
- **Migration:** no old-plan rewrite; already-issued choices remain fixed.
- **Acceptance criteria:** normalize labels for duplicate detection, never issue an empty or one-option choice, and allow the correct option in every slot across controlled fixtures. Keep valid typing/self-check questions in sparse pools and keep legacy scoring/weak-word behavior. Do not infer semantic distinctness from different strings.
- **Tests:** controlled option positions, duplicated Russian translations, single-word pool, count/score/retry consistency, and start-response privacy; no flaky random-distribution test.
- **Complexity:** medium.
- **Risk / research uncertainty:** distinct strings can denote the same meaning; this task removes mechanical cues only. Semantic distractor quality remains a P1 editorial decision.

#### P0-03 — Report first attempts, recovery and self-ratings separately

- **Goal:** show what a learner did independently while retaining the useful existing practice score and retry flow.
- **Why:** the existing mixed completion score otherwise presents recovery and subjective recall as if they were independent objective success.
- **Dependencies:** P0-01, P0-02 and P0-08.
- **Affected repository parts:** `backend/app/services/quiz_service.py`, `backend/app/schemas.py`, `frontend/src/api/client.ts`, `frontend/src/views/QuizView.vue`, `frontend/src/views/ResultsView.vue`, `frontend/src/i18n/messages.ts` and quiz tests.
- **Expected schema/API changes:** additive completion response version plus first-attempt correct/eligible counts, recovered objective items, self-report remembered/total counts, and explicit unavailable status where necessary. Preserve `score`, `total_questions`, `weak_word_ids` and `mistakes`; no DB change.
- **Migration:** do not rewrite `QuizAnswer`, `QuizAttempt.score` or old `sessionStorage` results. Old cached results show a labelled practice score and an unavailable breakdown, not a synthetic 0%.
- **Acceptance criteria:** denominator excludes self-check and unresolved items; retry success changes recovery, never independent first-attempt accuracy; zero eligible items displays “not measured.” `learned` is called a review streak where exposed. Both UI languages remain complete.
- **Tests:** frozen P0-01 mixed histories, wrong→correct, two wrong responses, self-check-only, zero questions, old cached result, and existing quiz frontend/API regression.
- **Complexity:** medium.
- **Risk / research uncertainty:** old clients may depend on the mixed score and clearer labels may change use. Measure interpretation in pilot usability work; do not imply first-attempt accuracy equals proficiency.

#### P0-06 — Classify existing evidence in read-only diagnostics

- **Goal:** expose how much existing evidence is independent, supported, repaired, self-reported, exposure or unknown before changing progression.
- **Why:** projector v1 weights a deterministic retry like a first success, and old snapshots lack enough context to safely revise progression now.
- **Dependencies:** P0-01.
- **Affected repository parts:** a small pure rule near `backend/app/domain/practice.py`, a read-only diagnostic adapter under `backend/app/services/`, `backend/tests/test_practice_contracts.py`, `backend/tests/test_projection.py` and shadow quiz fixtures.
- **Expected schema/API changes:** versioned internal classification result only. No public API, event schema, `LearnerTargetState` or scheduler change.
- **Migration:** none; old hints/context IDs absent from snapshots stay unknown. Do not infer independent occasions or backfill legacy events.
- **Acceptance criteria:** classification uses retry links, evaluation source, response and available hints; it separates an unassisted first response from confirmed independence across contexts. Existing snapshots without context IDs cannot establish the latter. Unknown is distinct from failure. Diagnostic counts reconcile with P0-01 fixtures, and v1 replay/selection output is unchanged.
- **Tests:** first answer versus retry, reveal/hint, self-report, model-only or ambiguous verdict, missing context revision, late/out-of-order event and idempotent replay; full relevant projection/selector regressions.
- **Complexity:** medium.
- **Risk / research uncertainty:** old shadow snapshots lack stable context/content revision, so independent occasions cannot be reconstructed. The proposed classification is a diagnostic hypothesis, not a validated mastery rule.

### P1 — reviewed written content and supervised practice

#### P1-03a — Curate a reviewed pilot example bank

- **Objective / why:** supply publishable, contextual Serbian/Russian material for the four P0-07 outcomes. Commissioned original sentences suffice; a Tatoeba extraction is optional only after direct-pair and item-rights checks.
- **Dependencies:** P0-04, P0-05, P0-07; qualified Serbian L2 approval of the outcome/holdout brief before approving examples.
- **Components:** `content/examples/`, `content/sources/`, P0 fixture validator and review export; consult `backend/app/domain/catalog.py`. No learner-facing service.
- **Schema/API/domain:** file-backed reviewed example revisions with original/display text, script, translation provenance, context-family/duplicate cluster, target and answer-policy references, register, reviewer decisions and source permissions. No HTTP or DB change by default.
- **Migration:** none. Keep `VocabularyItem` bilingual blobs and embedded `UsageExample` readable; do not auto-pair lines. If independent reuse/withdrawal is proven, invoke P1-03b.
- **Acceptance:** every published candidate has a traceable rights decision and Serbian/Russian review of naturalness, target alignment, answerability and variants; assessment families are isolated. Document reviewer disagreement, exclusions and editing time; source imports never become approved automatically.
- **Tests / measurement:** validator rejects missing permission/review, ambiguous target, private data, fragment, duplicate/transliteration leakage and unstable re-import IDs. Report accepted examples per review hour and reviewer agreement, with denominators.
- **Complexity:** medium. **Risk / uncertainty:** direct-pair yield and editorial cost are unknown; authored examples can cover the pilot without corpus machinery.

#### P1-03b — Persist examples independently, only if required

- **Objective / why:** allow the *same* reviewed example revision to be reused and withdrawn across multiple published targets when P0-05/P1-03a demonstrate that embedded examples plus pack files cannot do so safely.
- **Dependencies:** P1-03a; recorded evidence of cross-target reuse or independently governed withdrawal. If absent, record “not triggered” and use file-backed revisions.
- **Components:** `backend/app/domain/catalog.py`, `backend/app/domain_models/catalog.py`, catalog repository/service, Alembic migration, catalog tests and publication preflight.
- **Schema/API/domain:** one catalog-owned versioned example record with immutable text/revision/hash, source/rights reference, lifecycle state and validated target links; avoid a generic corpus ingestion framework or new service. No public API needed.
- **Migration:** additive table/indexes only; inspect sanitized populated legacy blobs/mappings first. Do not backfill by splitting legacy text. Export/restore and occupied-table downgrade policy precede migration.
- **Acceptance:** published references resolve to one approved revision; retiring a revision blocks future selection but does not rewrite issued snapshots/history; repeated publish is idempotent. Show the documented trigger in the task review.
- **Tests / measurement:** populated SQLite and disposable PostgreSQL upgrade, stale mapping, cross-target reuse, retirement, rollback/restore and old embedded-example reads.
- **Complexity:** medium. **Risk / uncertainty:** table may add more governance cost than value; skip unless the concrete case is demonstrated.

#### P1-04a — Make catalog/curriculum publication atomic

- **Objective / why:** `CurriculumService.publish` currently commits its own session; catalog writes and curriculum activation cannot be one transaction until that boundary is changed.
- **Dependencies:** P0-04, P0-05. Can run alongside P1-03a.
- **Components:** `backend/app/services/curriculum_service.py`, catalog/curriculum repositories, proposed publication orchestration under `backend/app/services/`, `backend/tests/test_curriculum.py` and publication tests.
- **Schema/API/domain:** introduce a caller-owned transaction boundary and preflight report; keep existing standalone publish behavior through an explicit wrapper if needed. No new table or public endpoint by default.
- **Migration:** none unless a revision metadata column is proved necessary. Do not activate new content in this task.
- **Acceptance:** catalog insert/revision and curriculum retirement/activation commit together or both roll back; preflight rejects unresolved source rights, refs, cycles, retired content and stale mappings before any active-version change. Existing standalone clients remain valid.
- **Tests / measurement:** inject failure before/after catalog write and at curriculum activation against populated fixtures; assert active revision and legacy mappings unchanged; concurrent/idempotent publish regression on disposable PostgreSQL.
- **Complexity:** medium. **Risk / uncertainty:** hidden callers may rely on internal commit semantics; inventory them before refactor.

#### P1-04b — Publish the reviewed written pilot pack

- **Objective / why:** connect reviewed outcomes, catalog targets, contextual input and assessment into one reproducible optional pack.
- **Dependencies:** P1-03a, P1-04a, P1-03b if triggered; educator/rights approval. P2-06/07 are not prerequisites.
- **Components:** `content/curricula/a1-pilot/`, catalog and curriculum services, publication CLI/service, `backend/tests/test_curriculum.py` and content validator.
- **Schema/API/domain:** versioned pack manifest pins outcome codes, CEFR edition/scale/page, source/example revisions, target/capability, answer policies, hard/soft edges, practice and holdout families. Use existing catalog/curriculum records and active-revision mechanism; add no manifest table without a replay need.
- **Migration:** publish additive draft/revision rows, then atomically activate. Never replace the technical seed or silently reconcile changed senses. Roll back by publishing a new reviewed revision based on the last good compatible pack, not by reviving retired rows.
- **Acceptance:** four approved written outcomes, each with multiple distinct contexts and an untouched unseen assessment family; no unresolved critical content/rights defect, stale ref or heldout-near-duplicate. Preflight lists changed and rejected IDs; old activities remain interpretable.
- **Tests / measurement:** idempotence, missing answer, invalid hard-edge cycle, stale/retired mapping, partial-failure rollback and holdout leakage. Record reviewed coverage by outcome, not a fabricated full-A1 percentage.
- **Complexity:** medium. **Risk / uncertainty:** exact content volume and target order require editorial judgment; soft-only edges are valid for pilot.

#### P1-05a — Implement a bounded deterministic answer policy

- **Objective / why:** score reviewed controlled answers without making an unbounded grammar-checking claim.
- **Dependencies:** P0-02, P0-05, P0-06, P0-08, P1-04b.
- **Components:** proposed `backend/app/services/answer_policy.py`, `backend/app/domain/practice.py`, scoring fixtures/tests; no HTTP route.
- **Schema/API/domain:** versioned reviewed answer-policy record pins accepted variants, script conditions, target span and primary capability; pure evaluator returns correct/incorrect/unresolved with bounded error category and evaluation source. Keep private key server-side and existing operation enum.
- **Migration:** no DB/API change; answer policies live in the versioned pack. Old quiz keys are unaffected.
- **Acceptance:** NFC/case/whitespace policy is documented; diacritics preserved; cross-script aliases only when reviewed and allowed; valid-looking answer outside key is unresolved, not silently wrong or auto-added.
- **Tests / measurement:** frozen human-labeled false accept/reject set, Serbian scripts/digraphs, inflection vs lexical error, alternate word order, span validation and ambiguous answer; report rates by class.
- **Complexity:** medium. **Risk / uncertainty:** finite variants cannot validate arbitrary Serbian; human review remains necessary.

#### P1-05b — Add a gated practice API and immutable snapshots

- **Objective / why:** expose contextual activity lifecycle using existing `ActivitySpec`, `PracticeService` and selector contracts, with direct-write safety.
- **Dependencies:** P1-05a.
- **Components:** `backend/app/domain/practice.py`, `backend/app/domain/selection_policy.py`, `backend/app/services/practice_service.py`, proposed `routers/practice.py`, `backend/app/main.py`, practice/selector API tests.
- **Schema/API/domain:** versioned activity snapshot pins pack/content/answer-policy revisions, context-family ID, target span, primary capability, operation and support conditions. Add minimal create/resume-run, next-activity and submit-response HTTP operations returning public DTOs; idempotency token for submit. Exposure is a non-scored presentation event, not fake success.
- **Migration:** additive API and snapshot payload version; no legacy event rewrite. Direct writes require both `local/development/test` mode and a real loopback bind/connection guard until P2-01/02, independent of shadow flag. Define local retention before human data collection.
- **Acceptance:** all four existing operations and exposure use immutable snapshots; first observation is retained; no unrevealed key in public DTO; retired content cannot be newly issued; flag-off legacy routes remain unchanged.
- **Tests / measurement:** create/resume, response privacy, idempotent double submit, unknown scorer result, retired revision, local/non-local gate and old route regressions; reconcile event fields with P0-01 fixture.
- **Complexity:** medium. **Risk / uncertainty:** route gate must enforce actual reachability, not merely read an environment flag.

#### P1-05c — Render and resume contextual practice in Vue

- **Objective / why:** make the backend's bounded activities usable without displacing legacy quiz/review.
- **Dependencies:** P1-05b.
- **Components:** `frontend/src/api/client.ts`, `frontend/src/router.ts`, proposed `frontend/src/views/PracticeView.vue` and activity components, `frontend/src/i18n/messages.ts`, frontend unit/e2e tests.
- **Schema/API/domain:** typed clients for P1-05b DTOs; local route only while pilot gate is active. Keep private answer policy absent from browser state before submission.
- **Migration:** no DB change; introduce versioned local session state if needed, with safe recovery of preexisting `sessionStorage` quiz result.
- **Acceptance:** display each existing operation and exposure, handle pending/accepted/unresolved states, resume a run and stop safely; keyboard and mobile controls work in both UI languages; legacy navigation remains available.
- **Tests / measurement:** component tests for each operation, hidden key, no-candidate and duplicate network response; e2e resume/network failure/mobile/keyboard path. Record completion and abandonment during pilot usability, not as efficacy.
- **Complexity:** medium. **Risk / uncertainty:** UI wording may imply unsupported mastery; use evidence-specific labels.

#### P1-06a — Preserve first evidence through linked repair

- **Objective / why:** useful correction must not erase what the learner knew before help.
- **Dependencies:** P1-05b, P0-06.
- **Components:** `backend/app/domain/practice.py`, practice/evaluator services, evidence classifier and projection tests.
- **Schema/API/domain:** use existing hint/reveal, first/final response, evaluation source and retry link fields where possible. Accepted activity is terminal; a repair is a separate linked activity/event. Add only bounded versioned error tag or feedback payload fields actually needed by reviewed content.
- **Migration:** no historical event reinterpretation; event payload revision only if existing fields cannot express the correction. Keep v1 projector behavior until P2-08 decision.
- **Acceptance:** a wrong first answer remains wrong after hint→repair; self-check/reveal gives no independent credit; limit immediate retries and schedule later opportunity. Duplicate submit cannot append a second event.
- **Tests / measurement:** wrong→hint→repair, reveal without answer, ambiguous verdict, already-correct alternate, repeated context, out-of-order event and idempotent replay. Later independent recurrence denominator excludes same-session repair.
- **Complexity:** medium. **Risk / uncertainty:** amount/timing of feedback is unvalidated; separate first-response evidence from UX choice.

#### P1-06b — Show reviewed feedback and a repair path

- **Objective / why:** present one actionable target correction and an honest repair opportunity.
- **Dependencies:** P1-05c, P1-06a.
- **Components:** practice Vue components, `frontend/src/i18n/messages.ts`, API client, frontend unit/e2e tests and reviewed feedback text in pilot pack.
- **Schema/API/domain:** consume feedback/retry DTOs from P1-06a; no new DB model or independent client-side scorer.
- **Migration:** none.
- **Acceptance:** distinguish first result, hint, reveal, corrected example and repair; state that assisted/repaired work is practice. An unresolved answer invites review/fallback rather than falsely marking wrong. Both scripts/UI languages render cleanly.
- **Tests / measurement:** hinted and revealed states, interrupted/lost response, duplicate click, alternate accepted answer and accessibility checks. Measure learner comprehension of score/support labels in pilot sessions.
- **Complexity:** small. **Risk / uncertainty:** correction wording may overgeneralize a form; all pilot explanations need editorial review.

#### P1-08a — Version workload and selector policy

- **Objective / why:** fit due practice, new input, repair and probes inside an explainable budget; avoid weak-item loops and invalid top-priority dead ends.
- **Dependencies:** P1-05b, P0-01.
- **Components:** `backend/app/services/next_activity_service.py`, `backend/app/domain/selection_policy.py`, profile setting adapter, selector/projection tests.
- **Schema/API/domain:** named policy version and decision reason; use current UTC day semantics until P2-03. Filter published/licensed → learner scope → prerequisites → supporting language → budget; allocate due/new/repair/probe work within limits, with deterministic tie-break. Return `no suitable activity` plus reason instead of inventing progress. Keep access monotonic and do not activate a new readiness rule.
- **Migration:** policy/config version only; no historical due-date rewrite. Existing `daily_new_word_count` remains legacy batch size unless an explicit versioned setting is added for pilot new-target budget.
- **Acceptance:** learner can stop; returning after long absence has bounded work; lower-priority valid candidate is considered when higher-priority set is empty; new input is not starved forever; diagnostic reason is recorded. Fixed allocation values are defaults to be reviewed, not research facts.
- **Tests / measurement:** 90-day absence, all weak, no reviewed content, hard prerequisite missing, zero/exhausted budget, retry idempotence and fallback. Report workload, invalid-edge attempts, context repetition and new-target opportunity on synthetic histories.
- **Complexity:** medium. **Risk / uncertainty:** allocation ratios and perceived burden need pilot calibration; no generic optimization engine.

#### P1-08b — Expose budget, stop and workload clearly

- **Objective / why:** let learners understand what remains and stop without a false completion claim.
- **Dependencies:** P1-05c, P1-08a.
- **Components:** practice/overview Vue views, API client, i18n, frontend unit/e2e tests.
- **Schema/API/domain:** consume policy version, remaining planned work and no-candidate reason; label legacy daily count as batch size where shown. No new persistence unless a user-adjustable budget is approved, then add one versioned profile field.
- **Migration:** old profile defaults preserve legacy behavior; no retroactive workload recomputation.
- **Acceptance:** stop/resume, due/new/repair distinction, no-activity state and reason visible; UI does not equate task completion with mastery. Both locales and mobile/keyboard paths work.
- **Tests / measurement:** budget-zero/exhausted, no candidate, late return, stop/resume and old profile. Pilot usability records whether learners understand remaining workload.
- **Complexity:** small. **Risk / uncertainty:** minute estimates are heuristic; show counts unless measured timing supports estimates.

#### P1-09a — Enable only a supervised loopback written flow

- **Objective / why:** exercise the optional pack end to end without opening unauthenticated histories remotely.
- **Dependencies:** P1-04b, P1-05c, P1-06b, P1-08b.
- **Components:** `backend/app/config.py`, `backend/app/main.py`, practice router, frontend routing/session, local pilot documentation and e2e tests.
- **Schema/API/domain:** explicit opt-in local pilot gate on *all* new practice reads/writes; preserve legacy fallback. No general cohort/auth API yet.
- **Migration:** none; local data retention and deletion procedure must be documented before human use. Do not toggle existing production/shadow safety flags to bypass gates.
- **Acceptance:** only an actually loopback-bound local/development/test service can accept pilot practice; remote request or production mode fails closed. Stop/resume and selection explanation work; legacy behavior when off is identical.
- **Tests / measurement:** gate matrix (mode, bind, request), flag-off parity, old route regressions, offline resume, retired content and no candidate. Instrument consented usage only; no efficacy claim.
- **Complexity:** medium. **Risk / uncertainty:** environment flag alone cannot prove local reachability; integration test must exercise network boundary.

#### P1-09b — Freeze consented delayed-probe protocol and export

- **Objective / why:** measure independent delayed recall and unseen written task transfer without contaminating live progression.
- **Dependencies:** P0-01, P0-07, P1-09a; explicit local consent/retention review before collecting human answers.
- **Components:** `docs/testing/learning-evaluation.md`, heldout pack fixtures, versioned research export utility under `backend/app/`, tests; separate restricted research dataset for human rubrics.
- **Schema/API/domain:** export only consented pseudonymous first-response, support, context, time, task-family and workload fields; 7-/28-day probes use unseen families. Human multi-dimensional ratings do **not** write `LearningEvent` or projection state. No public export endpoint for unauthenticated users.
- **Migration:** document local deletion/export and field minimization; no historical backfill. P2-02 later formalizes public lifecycle.
- **Acceptance:** protocol prespecifies recruitment, primary delayed/transfer metrics, effect and burden thresholds, missing-data treatment, sample-size rationale, blind rubric and holdout assignment *before* outcomes are viewed. Export can be reconciled to P0-01 fixtures and revoked/removed under consent policy.
- **Tests / measurement:** family leakage, wrong support classification, duplicate probe, absent consent, owner/pseudonym isolation, export deletion and no projection mutation. Dry-run human rating agreement on a small labeled set.
- **Complexity:** medium. **Risk / uncertainty:** participant availability and external review of consent are real gates; 7-/28-day timing cannot be compressed into a code test.

#### P1-09c — Run and report the written feasibility pilot

- **Objective / why:** find content, scoring and workflow defects and estimate delayed outcomes before expansion.
- **Dependencies:** P1-09b; recruited consenting participants, elapsed probe windows and blinded Serbian L2 raters. Remote enrollment additionally requires P2-01b/P2-02c.
- **Components:** consented research export/report, `docs/testing/learning-evaluation.md`, editorial defect log; no production projection mutation.
- **Schema/API/domain:** no new product API; frozen analysis script/report fields for recall, task success, target accuracy, missingness and minutes.
- **Migration:** none beyond consented research-data retention/deletion; keep baseline legacy data intact.
- **Acceptance:** report sample/attrition, content and scoring defects, delayed first-attempt recall, blinded unseen-task scores, workload and uncertainty, subgroup limitations and release/rollback recommendation. Small uncontrolled usability results cannot support a comparative efficacy claim.
- **Tests / measurement:** rerun frozen export analysis, reconcile random records to source events, check blinded rating agreement and holdout separation; report missing probes rather than imputing success.
- **Complexity:** large. **Risk / uncertainty:** human recruitment, delayed observation and effect precision are external; an inconclusive result is a valid completed study outcome.

### P2 — production obligations, useful breadth and measured alternatives

#### P2-01a — Decide production identity and legacy-linking policy

- **Objective / why:** `userId` is currently a caller-supplied identifier, not proof of ownership. A production identity mechanism and migration policy must be chosen before code integration.
- **Dependencies:** none for design; public/remote enrollment waits for P2-01b and P2-02c. Requires an explicit deployment/provider choice from the product owner.
- **Components:** identity/access ADR, `backend/app/config.py`, `backend/app/models.py`, profile/learning/quiz/practice routers, `frontend/src/stores/session.ts` review.
- **Schema/API/domain:** specify trusted subject source, session/token validation, editor role, route ownership matrix, logout and account-link proof. No runtime API yet.
- **Migration:** inventory anonymous/legacy profile IDs and associated quiz/progress/events on sanitized data; design opt-in verified linking and unclaimed-record handling. Knowing an ID alone never claims it.
- **Acceptance:** reviewed threat model includes guessed IDs, replayed/expired credentials, cross-user reads/writes and editor elevation; chosen provider/deployment is maintainable and compatible with startup gates.
- **Tests / measurement:** executable ownership matrix/test plan and migration rehearsal fixtures; no live account mutation in this design task.
- **Complexity:** medium. **Risk / uncertainty:** provider, host and operational ownership are external decisions; do not invent them in implementation.

#### P2-01b — Enforce authenticated ownership across product routes

- **Objective / why:** make profile, legacy quiz/review, curriculum progress and new practice records belong to a trusted principal before remote use.
- **Dependencies:** P2-01a and approved provider/deployment choice.
- **Components:** backend auth dependency/middleware, all user-scoped routers/services, `backend/app/config.py`, profile/account mapping, `frontend/src/stores/session.ts`, API client, auth and existing route tests.
- **Schema/API/domain:** authenticated principal resolves owner server-side; caller-supplied `user_id` becomes compatibility input checked against owner, then can be deprecated by version. Editor writes require explicit role. Session expiry/logout handled consistently.
- **Migration:** additive account↔profile mapping and verified opt-in legacy link; preserve unclaimed data and ability to export/delete under policy. Rehearse populated migration; never auto-link by matching email or guessed ID without approved proof.
- **Acceptance:** every user-scoped read/write and editor action checks authorization; non-local practice remains closed until P2-02c. Existing local legacy flow still works under documented mode.
- **Tests / measurement:** guessed ID, cross-user access to each route family, token expiry/revocation, editor denial, link collision, unclaimed profile, production startup gates and old client compatibility.
- **Complexity:** large. **Risk / uncertainty:** provider SDK behavior and legacy-claim proof depend on P2-01a; partial router coverage would expose records.

#### P2-02a — Approve a learning-history lifecycle policy

- **Objective / why:** immutable events, legacy tables, derived projections, backups and research exports need one explicit retention and deletion contract before public collection.
- **Dependencies:** P1-09b local consent/export design; can proceed alongside P2-01a. Requires product/legal/operations decision for jurisdiction and periods.
- **Components:** lifecycle ADR and record map over practice/progress repositories, legacy `backend/app/models.py`, research exports, backups and source/content storage.
- **Schema/API/domain:** define owner export scope, erasure versus anonymization, consent states, content withdrawal, pseudonymous research extracts and backup expiry. No runtime endpoint yet.
- **Migration:** classify existing rows, foreign keys and replay dependencies; specify how deleting raw events also deletes or invalidates derived state and how already-issued snapshots remain audit-safe where lawful.
- **Acceptance:** approved period/action matrix covers active, withdrawn-consent, deleted and backup copies; no derived projection can recreate deleted personal text. Local pilot policy is reconciled, not silently replaced.
- **Tests / measurement:** table-by-table deletion/export test matrix and sample populated-data drill design; no unreviewed legal defaults.
- **Complexity:** medium. **Risk / uncertainty:** legal basis, backup technology and retention durations are external, material decisions.

#### P2-02b — Implement authenticated owner export

- **Objective / why:** allow a learner to inspect all personal history governed by P2-02a before the deletion operation is enabled.
- **Dependencies:** P2-02a, P2-01b.
- **Components:** profile, legacy quiz/progress, practice/history and projection repositories; authenticated export router and frontend account control; lifecycle tests.
- **Schema/API/domain:** versioned owner-scoped export/status API and manifest with schema version, included record classes, omissions and generation time. Research extracts follow their own consent policy, not an accidental join by profile ID.
- **Migration:** additive export metadata only if needed; no source-row rewrite. Reconcile against populated representative data and document portable restore semantics.
- **Acceptance:** owner export includes every record class in the approved policy with stable IDs/versions; another principal cannot request or read it; withdrawn content is represented with permitted metadata without re-exposing restricted text.
- **Tests / measurement:** record-class completeness, pagination/large history, owner isolation, deleted/retired content representation and disposable PostgreSQL export-restore drill.
- **Complexity:** medium. **Risk / uncertainty:** exact export fields depend on P2-02a rights and research consent decisions.

#### P2-02c — Enforce deletion, retention and backup expiry

- **Objective / why:** fulfill the approved erasure/retention contract without leaving reconstructable learner state.
- **Dependencies:** P2-02b; approved backup operations and deletion policy from P2-02a.
- **Components:** practice/progress/quiz/profile repositories, projection replay, retention worker/operations, authenticated deletion API, backup and research-export procedures, frontend account control.
- **Schema/API/domain:** authenticated delete/status operation and minimal non-content tombstone/audit metadata allowed by policy; no generic analytics platform. Content withdrawal is a separate editorial procedure with consistent historical snapshot treatment.
- **Migration:** additive lifecycle metadata if required; rehearse populated row/FK deletion and projection invalidation. Document backup expiry and restore-time erasure replay; do not rely on a live DB downgrade.
- **Acceptance:** deletion is idempotent; live raw and derived personal content is removed or anonymized as approved; a backup restore cannot reintroduce it after the policy deadline; retained research data follow consent restrictions.
- **Tests / measurement:** cross-table fixture with quiz attempts, vocabulary progress, events, projections and consent; owner isolation, repeat delete, replay after delete, backup restore/expiry drill on disposable PostgreSQL.
- **Complexity:** large. **Risk / uncertainty:** irreversible deletion and backup support require staged operational verification; public enrollment waits for this task.

#### P2-03 — Use learner-local days and honest workload reporting

- **Objective / why:** a UTC date is not a learner's daily budget or promised review day.
- **Dependencies:** P1-08a; coordinate profile migration with P2-01b, but neither task's domain depends on the other.
- **Components:** `backend/app/models.py` profile, profile schemas/router, time-boundary utility, learning/quiz/selection services, Vue dashboard/i18n, migration and time tests.
- **Schema/API/domain:** additive IANA timezone preference; store instants in UTC, compute daily windows in selected zone. Define travel/change policy: a timezone change applies to future allocations only and must not reset already consumed budget for the same instant.
- **Migration:** existing profiles get an explicit UTC fallback with UI disclosure; never rewrite event timestamps or previous daily totals.
- **Acceptance:** due/new work and daily count agree for the same local day across API and UI; show review load as counts, with minutes only if measured. User can change zone without receiving duplicate quota.
- **Tests / measurement:** DST short/long day, midnight, timezone switch, simultaneous requests at boundary, old profile, malformed zone and cap consistency; compare reported vs observed workload during pilot.
- **Complexity:** medium. **Risk / uncertainty:** travel semantics and minute forecasts need usability evidence; do not silently reinterpret old timestamps.

#### P2-04a — Prepare a small rights-cleared audio comprehension pack

- **Objective / why:** written contexts do not assess listening; media needs independent permission and quality review.
- **Dependencies:** P0-04, P1-09c feasibility; licensed/commissioned speaker recordings and human Serbian review. Public playback also requires P2-01b/P2-02c.
- **Components:** `content/sources/`, new `content/audio/` or configured media store with versioned manifest, curriculum pack revisions, content validators.
- **Schema/API/domain:** file-backed media ID/hash, speaker/variety, text/transcript revision, recording permission, attribution, duration/format and context-family link. No media table unless independent lifecycle cannot be handled by the pack.
- **Migration:** versioned additive content only; keep old written pack and activities valid. Do not place unlicensed large source audio in Git.
- **Acceptance:** a reviewed bounded listening set covers selected pilot functions, with separate text/audio rights, audible quality and unseen-speaker holdout; transcript and answer variants are approved. Publication preflight rejects missing/withdrawn media rights.
- **Tests / measurement:** manifest/hash/permission checks, missing media and duplicate-source leakage; human quality ratings and reported recording/editorial cost.
- **Complexity:** medium. **Risk / uncertainty:** speaker availability and transfer beyond recorded voices are unknown.

#### P2-04b — Add listening activities and separate modality evidence

- **Objective / why:** playback and listening responses must not be counted as written recognition or pronunciation mastery.
- **Dependencies:** P2-04a, P1-05b; public rollout waits for P2-01b/P2-02c.
- **Components:** `backend/app/domain/shared.py` modality enum, `backend/app/domain_models/curriculum.py`, Alembic successor to `20260826_0005`, practice DTO/evaluator/projection/selector, Vue audio controls and tests.
- **Schema/API/domain:** versioned `audio` input modality with written response for bounded comprehension; target keys keep modality separate. Activity snapshot pins media/transcript revisions and records transcript reveal as support. Extend the existing SQL `modality IN ('written')` constraint, serializers and replay compatibility together. No speech-production score.
- **Migration:** additive enum/constraint migration after populated-row inspection; old written rows/events replay unchanged. Media withdrawal blocks new selection but preserves lawful issued snapshots/history.
- **Acceptance:** audio task can be played and answered accessibly; transcript is hidden until requested and that request is evidence support; listening success updates only listening target; playback failure offers an honest skip/fallback.
- **Tests / measurement:** SQLite/disposable PostgreSQL migration, old-event replay, transcript leakage, text/audio isolation, alternate speaker, failed playback, keyboard controls and unseen-speaker human comprehension.
- **Complexity:** large. **Risk / uncertainty:** recording quality and modality transfer are empirical; audio does not establish spontaneous speech skill.

#### P2-05a — Publish a routines/past outcome pack

- **Objective / why:** address a measured routine/past communication gap with reviewed aspect/time usage, not a broad vocabulary dump.
- **Dependencies:** P1-04b, P1-09c showing this gap; P2-04b only if the pack makes a listening claim. If the gap is absent, record not triggered.
- **Components:** new `content/curricula/` revision and reviewed `content/examples/`, existing catalog constructions/forms, P1 publication validator.
- **Schema/API/domain:** versioned outcomes, target/capability mappings, reviewed past/aspect answer variants, input/practice/heldout families and declared unassessed skills; no new engine.
- **Migration:** additive catalog/curriculum revision; semantic-change links only after reviewed mapping, no old event rewrite.
- **Acceptance:** educator-approved crosswalk, multiple contexts per target, unseen written assessment and spaced reuse; known Russian→Serbian interference is addressed where pilot records it. Activation is atomic and rollbackable via new revision.
- **Tests / measurement:** content quality/rights/holdout validation, publication/replay regressions and delayed transfer by relevant target; report coverage and unresolved errors.
- **Complexity:** medium. **Risk / uncertainty:** pilot may rank this below another gap; order is empirical.

#### P2-05b — Publish a travel/location outcome pack

- **Objective / why:** address measured place/movement tasks with reviewed preposition/case contrasts.
- **Dependencies:** P1-04b, P1-09c showing this gap; P2-04b only for listening claims. Independent of P2-05a content, but activate against the then-current revision. If the gap is absent, record not triggered.
- **Components:** versioned curriculum/content pack, existing `Construction`/`Form` catalog records, P1 publication tests.
- **Schema/API/domain:** reviewed location and movement targets, senses, contextual variants, input/practice/holdout families and scope; no graph or general case generator.
- **Migration:** additive revision and explicit reviewed semantic mappings where needed; old examples/events remain pinned.
- **Acceptance:** educator approves target/rubric and source rights; test contexts cannot be solved by identical prompt recall; list unassessed oral/navigation skill. Atomic activation and safe fallback work.
- **Tests / measurement:** preposition/case answer fixtures, near-duplicate leakage, publication/replay, error recurrence and delayed unseen-location task rating.
- **Complexity:** medium. **Risk / uncertainty:** corpus forms may be ambiguous; review actual communicative contexts.

#### P2-05c — Publish a comparison/arrangements outcome pack

- **Objective / why:** address measured comparison/planning needs with bounded agreement, clitic or number patterns where useful.
- **Dependencies:** P1-04b, P1-09c showing this gap; P2-04b only for listening claims. Independent of P2-05a/b content, but activate serially. If the gap is absent, record not triggered.
- **Components:** curriculum pack revision, reviewed examples/assessments, existing catalog pattern records and publication validator.
- **Schema/API/domain:** explicit outcome rubrics and target scopes; reviewed answer variants for selected constructions, with unchanged four controlled operations unless a separate future contract is approved.
- **Migration:** additive content revision; no inferred remapping of old evidence or seed replacement.
- **Acceptance:** educator-approved crosswalk, contextual input/practice, unseen written assessment, source rights and explicit unassessed skills. Publish/rollback retains older versions.
- **Tests / measurement:** agreement/variant fixtures, holdout leakage, publication/replay and delayed transfer/recurrence; report defect counts by target.
- **Complexity:** medium. **Risk / uncertainty:** stage order and pattern difficulty are not validated for this audience.

#### P2-06 — Trial a bounded srLex form-candidate import, if needed

- **Objective / why:** fill a documented inflection-candidate gap from a pinned lexicon release rather than LLM guesses.
- **Dependencies:** P0-04, P0-05, P1-09c documented gap. If no gap, record not triggered. No dependency on CLASSLA.
- **Components:** proposed `backend/app/content_pipeline/srlex.py`, CLI, file-backed draft output, `backend/tests/test_srlex_import.py`, small licensed fixtures.
- **Schema/API/domain:** candidate form records retain release/checksum, lemma+POS, original tag, normalized form, all analyses, confidence/ambiguity and license. Approved catalog `Form` records are never overwritten automatically.
- **Migration:** no core DB change by default; reviewed candidates may enter later draft catalog revisions through existing publication flow. Bulk source outside Git unless its license/size allow fixture use.
- **Acceptance:** bounded approved lemma list streams reproducibly; rerun is idempotent; malformed/ambiguous rows are counted and preserved for review, not silently selected. Human editor approves any promotion.
- **Tests / measurement:** homographs, duplicate analyses, missing features, NFC/scripts, changed checksum, interrupted resume; report accepted forms and editorial minutes per useful candidate versus manual baseline.
- **Complexity:** medium. **Risk / uncertainty:** lexicon analyses may not match intended sense or actual usage; a failed yield trial ends without integration.

#### P2-07 — Trial bounded CLASSLA 2.0 candidate evidence, if needed

- **Objective / why:** test whether authentic frequency/context evidence improves teacher shortlists enough to justify corpus cost.
- **Dependencies:** P0-04, P0-07, P1-09c documented gap; P2-06 may supply lemmas but is not required. If no gap/budget, record not triggered.
- **Components:** proposed `backend/app/content_pipeline/classla.py` and `frequency.py`, source manifest, tiny actual-schema fixture, offline report; bulk files outside Git.
- **Schema/API/domain:** analysis artifact stores release/checksum, sample frame/denominator, token/form and lemma+POS counts, document/domain dispersion, ambiguous analyses and concordance IDs. It is candidate evidence, not a sense/CEFR label or learner API.
- **Migration:** none unless reviewed results later enter a content revision; never overwrite catalog or infer full-corpus estimates from a sample.
- **Acceptance:** approved bounded download/compute budget and output-rights check; compare teacher-only and corpus-informed shortlists blind where possible; record accepted useful candidates and outcome coverage per review hour. Stop before full-corpus processing if no measured gain.
- **Tests / measurement:** compressed streaming, pinned release fixture, duplicate/syndicated documents, mixed scripts, bad language label, unknown sense, reproducible counts and sample-denominator report.
- **Complexity:** medium. **Risk / uncertainty:** web-domain bias, annotation error, licensing and multi-gigabyte cost may defeat A1 utility.

#### P2-08a — Compare readiness rules in shadow

- **Objective / why:** one deterministic success and a permanent peak are weak competence evidence, but a stricter checklist might block learners unnecessarily.
- **Dependencies:** P0-06, P1-06a, P1-09c. Use stable context/content revisions from P1 practice.
- **Components:** `backend/app/domain/progress.py`, `curriculum_policy.py`, `services/learner_projection_service.py`, replay/selector diagnostics tests.
- **Schema/API/domain:** versioned shadow readiness projection compares v1 to independent-first-response, distinct-context/day and delay checklist from `learning-model.md`. Keep current access/frontier untouched; report recognized versus productive evidence separately and unknown legacy context.
- **Migration:** no live state rewrite; optional additive shadow summary only if replay alone is impractical. Rebuild from immutable events with exclusions; preserve v1 replay.
- **Acceptance:** compare unlock timing, cold-start access, false dead ends, error/transfer and workload against baseline. A later failure changes shadow current readiness but cannot erase historic access. Document reviewed decision including no-change option.
- **Tests / measurement:** three same-day repeats, same-context duplicates, self-report, delayed contexts, later failure, corrected revision, out-of-order replay and v1 parity; report subgroup/unknown counts.
- **Complexity:** medium. **Risk / uncertainty:** three successes/two contexts/two days is an unvalidated hypothesis; pilot may lack power.

#### P2-08b — Activate reviewed readiness/access rule, if justified

- **Objective / why:** use stronger evidence for future hard prerequisites only if P2-08a shows an acceptable unlock/error/workload tradeoff.
- **Dependencies:** P2-08a and explicit reviewed threshold/rollout decision; public rollout also requires P2-01b/P2-02c. If the decision is no-change or inconclusive, record not triggered and keep soft-only edges.
- **Components:** `curriculum_policy.py`, `learner_projection_service.py`, selector, progress ORM only if summary required, rollout config and tests.
- **Schema/API/domain:** new policy version separates monotonic `ever_met_introduction` access from reversible current readiness; explicit recognition prerequisites may introduce productive practice without claiming productive competence. Old v1 projection remains replayable.
- **Migration:** additive projection policy and event replay into a new version; no mutation of old events/peak. Dry-run comparison and rollback config before enabling; never relock a previously opened unit.
- **Acceptance:** no learner dead end on sparse/legacy history, monotonic access, explainable current status, safe fallback for unknown evidence; monitored rollout meets prespecified P2-08a tradeoff.
- **Tests / measurement:** v1 parity, event-order invariance, content correction, old/unknown history, later failure, access retention and rollback; monitor unlock distribution and workload after release.
- **Complexity:** medium. **Risk / uncertainty:** stricter rule may reduce learning opportunity; retain rollback to v1/soft edges.

### P3 — optional measured experiments

P3-01a, P3-02a/b and P3-03a are **implementation-ready as bounded experiments**, once their stated data and review gates are met. P3-01b and P3-03b require a favorable preliminary result plus a prespecified prospective protocol. None authorizes automatic product adoption.

#### P3-01a — Compare fitted memory models offline

- **Objective / why / hypothesis:** test whether a fitted HLR/FSRS-style interval predictor is better calibrated for *defined next unaided responses* than the current transparent interval baseline, with a plausible burden benefit.
- **Dependencies:** P1-09c longitudinal data, P2-02a consent/lifecycle approval and enough independent observations demonstrated by learning curves/uncertainty, not an invented event count.
- **Components:** existing `MemoryPolicy` seam, offline fit/evaluation script, frozen event export, model/parameter manifest and tests. No live scheduler switch.
- **Schema/API/domain:** model version, target/capability, prediction horizon, training cutoff and parameter hash in offline artifacts; no learner-facing API or mutation of original events.
- **Migration:** none for offline run. If later trialed, parameters/projection policy are additive and versioned; cold-start uses baseline.
- **Acceptance / evaluation:** audit leakage and split chronologically with learner and target holdouts; compare baseline, HLR and FSRS-style candidates on Brier/log loss and calibration by delay/capability, then simulate due load. Calibrate a probability for the current interval baseline on training data only; raw `peak` is not a probability. Before unblinding, prespecify minimum useful predictive gain and maximum burden; success requires both and no subgroup harm beyond the guardrail. Failure means no improvement or worse calibration; inadequate sample is inconclusive. Record all three outcomes.
- **Tests:** deterministic replay, sparse/cold-start learners, long absence, failures, corrupted parameters and split leakage. Report denominators and confidence intervals, not just best aggregate score.
- **Complexity:** medium. **Risk / uncertainty:** sparse biased histories may make any fit unreliable. **Rollback/abandon:** discard offline candidate if criteria fail; keep baseline untouched.

#### P3-01b — Run a prospective memory-policy trial, only if justified

- **Objective / why / hypothesis:** test whether the offline winner improves delayed correct retrieval *per practice minute* at acceptable review burden in actual use; offline next-answer accuracy is insufficient.
- **Dependencies:** favorable P3-01a, P2-01b/P2-02c for remote participants, approved consent and prespecified sample/power/stop rules. If offline fails or data are insufficient, record not triggered.
- **Components:** versioned `MemoryPolicy` adapter/config, stable cohort assignment, due-time logging and analysis protocol; baseline remains selectable.
- **Schema/API/domain:** additive policy version/assignment metadata and parameter hash in events/decision logs; no replacement of event source data or target identity.
- **Migration:** versioned projection/schedule recomputation only for enrolled future decisions; preserve existing due state and a rollback path to baseline. No retroactive reinterpretation of old events.
- **Acceptance / evaluation:** equal planned practice time, randomized assignment, prespecified missing-data handling; primary delayed unaided recall per measured minute, secondary 7-/28-day recall, transfer and burden distribution. Success requires the prespecified minimum gain with workload below cap and no systematic subgroup harm; otherwise fail or report inconclusive. Engagement alone is not success.
- **Tests:** stable assignment, no cross-policy leakage, idempotent scheduling, cold-start fallback, replay/rollback and production gate. Monitor stop conditions during trial.
- **Complexity:** large. **Risk / uncertainty:** effect may disappear prospectively. **Rollback/abandon:** switch new decisions to baseline and retain versioned trial records under consent policy when harm, invalid scoring or burden cap occurs.

#### P3-02a — Trial LLM editorial enrichment offline

- **Objective / why / hypothesis:** determine whether model drafts/triage reduce human minutes per *approved* example/answer while maintaining human-rated quality and rights compliance.
- **Dependencies:** P1-03a, P0-01 frozen evaluation conventions, consent/rights-cleared examples and human gold decisions. No runtime provider is required for the product.
- **Components:** offline queue and replaceable model adapter, prompt/model/version/cost log, human review export, adversarial tests; do not overload the existing learner-facing word-generation endpoint.
- **Schema/API/domain:** draft proposal with provenance and status only; deterministic IDs, offsets, normalization, license facts and corpus counts remain outside model authority. No public API or automatic publication.
- **Migration:** additive file-backed experiment records; no catalog overwrite. If later adopted, reviewed output enters P1 publication exactly like authored content.
- **Acceptance / evaluation:** compare manual baseline vs small-model draft and optional stronger-model triage on reviewer time per approved item, blind quality disagreement, critical defects and cost. Prespecify useful time/cost saving with **zero unresolved critical rights/meaning defects**; failure is no saving or worse quality, inconclusive if sample/raters inadequate.
- **Tests:** prompt injection in source text, fabricated URL/license/stress, mistranslation, regional form, provider outage, cache/version mismatch and correlated model disagreement. Human approval remains mandatory.
- **Complexity:** medium. **Risk / uncertainty:** model agreement is correlated, not validation. **Rollback/abandon:** stop queue/provider spend and retain manual editorial flow if criteria fail.

#### P3-02b — Trial LLM review of unresolved answers offline

- **Objective / why / hypothesis:** test whether model triage helps human reviewers resolve valid-but-unlisted Serbian answers with fewer false rejections, without allowing model verdicts to change learner state.
- **Dependencies:** P1-05a deterministic scorer, P0-01 labeled answer cases, P2-02a approval for use of consented response text, independent human gold set. A live open-response product is outside this task.
- **Components:** offline answer-review queue/model adapter, frozen human-labeled variants, adjudication report, provider failure tests.
- **Schema/API/domain:** model output is a suggestion with reason/version/cost; unresolved product answer remains unresolved until a human-approved policy revision, which applies prospectively. No model-only `LearningEvent` success or gate unlock.
- **Migration:** file-backed consented experiment data only; accepted new variants enter a later versioned answer policy, never retroactive grading.
- **Acceptance / evaluation:** compare deterministic-only and triage-assisted human review for false accept/reject, unresolved rate, reviewer minutes and cost, stratified by script, inflection and register. Prespecify minimum useful reduction in unresolved/false reject with no increase beyond false-accept guardrail; report fail/inconclusive otherwise.
- **Tests:** valid regional alternative, hallucinated morphology, answer-key leakage, prompt injection in response, outage/timeouts, duplicate answer, reviewer disagreement and no state mutation.
- **Complexity:** medium. **Risk / uncertainty:** rare valid answers and correlated model errors may limit usefulness. **Rollback/abandon:** disable adapter; deterministic unresolved path and human review continue.

#### P3-03a — Simulate one sequencing alternative offline

- **Objective / why / hypothesis:** test whether purposeful interleaving of already introduced contrasts could improve coverage without adding workload or violating prerequisites. Keep support fading and readiness strictness out of this comparison.
- **Dependencies:** P1-08a stable selector/logs, P1-09c measured pilot and enough reviewed contrast contexts.
- **Components:** versioned `selection_policy.py` variant, replay/simulation script, decision-reason report and selector tests. No live cohort assignment yet.
- **Schema/API/domain:** policy-versioned decisions only; content/target/event schemas unchanged. Baseline due/new budget and stop rules stay equal.
- **Migration:** none; simulate from frozen histories without changing projections.
- **Acceptance / evaluation:** prespecify feasible contrast opportunities, repeated-context cap and workload/prerequisite guardrails; show variant and baseline on same histories. Success for advancing to a trial means valid exposure and no guardrail breach, **not** demonstrated learning gain. Failure/insufficient eligible contrasts ends the experiment.
- **Tests:** deterministic replay, hard-edge respect, no cross-policy data leak, no-candidate fallback, 90-day backlog and equal budget; report opportunity counts and simulation limitations.
- **Complexity:** medium. **Risk / uncertainty:** offline replay cannot infer counterfactual learning. **Rollback/abandon:** discard variant if feasibility or invariants fail.

#### P3-03b — Compare sequencing prospectively, only if justified

- **Objective / why / hypothesis:** test whether purposeful interleaving improves delayed unaided recall or unseen-context transfer per equal practice time compared with P1-08a policy.
- **Dependencies:** feasible P3-03a, P2-01b/P2-02c for remote use, approved experimental protocol, enough reviewed contrasts and participants. If infeasible, record not triggered.
- **Components:** one versioned selector variant, stable cohort assignment, reason logs, consented probe analysis; do not add bandits, RL or deep knowledge tracing.
- **Schema/API/domain:** additive experiment assignment/policy-version record; no new learner-state truth. Keep current readiness/access policy identical across arms.
- **Migration:** no historical rewrite; rollout flag can return new decisions to baseline while preserving issued snapshots.
- **Acceptance / evaluation:** one factor, randomized equal-time comparison with prespecified minimum useful delayed recall/transfer gain, permitted burden, attrition/missingness and subgroup checks. Report primary delayed outcomes, workload, frustration and prerequisite violations; retention/click rate alone cannot justify adoption. Fail/inconclusive if learning criterion is not met or measurement invalid.
- **Tests:** assignment stability, no policy bleed, budget/prerequisite invariants, replay and rollback, missing probe handling and flag-off parity.
- **Complexity:** large. **Risk / uncertainty:** audience/content interaction may negate benefit. **Rollback/abandon:** disable variant on guardrail breach or failed/inconclusive result; retain baseline.

## Migration and data-preservation strategy

1. **Before each schema/API change:** inventory real callers, old payload versions and sanitized representative populated rows. P0 quiz key/result changes are additive JSON/API versions; old `question_plan`, `QuizAnswer`, score and cached frontend result remain readable and explicitly legacy. Do not derive keys from edited vocabulary.
2. **Content:** keep raw legacy bilingual strings and embedded examples. File-backed pilot manifests are the default. P1-03b adds storage only after its trigger; publication preflight checks source permissions, references, mappings, answer revision and holdout families. Never silently remap a sense or copy evidence to a revised meaning. Withdrawal stops future selection, while issued snapshots/history retain their legally permitted revision.
3. **Transactions and rollback:** P1-04a establishes caller-owned atomic publication. Activation changes one compatible catalog/curriculum revision together. A correction is a new reviewed revision; do not resurrect retired rows. A policy rollback changes future selection while preserving event/policy versions.
4. **Identity and deletion:** P2-01b uses verified account linking, preserves unclaimed profiles, and is independent of knowing an ID. P2-02b exports and P2-02c erases according to the approved table/backup map. Deleting personal events also invalidates derived projections and research extracts under consent; test restore/expiry behavior. Production access remains shut until both are complete.
5. **Modalities/time:** P2-03 adds zone preference without rewriting UTC instants. P2-04b changes the actual `written`-only DB constraint together with enums/serializers/replay; no old written target/event is reclassified. Model/readiness trials add policy versions and derived projections, not replacements for immutable history.
6. **Rehearsal:** for every Alembic change, test empty and representative populated upgrades on SQLite and disposable PostgreSQL, verify indexes/checks and old reads, and document export/restore plus occupied-table downgrade limitations. Never downgrade a live DB or treat dropping populated new tables as harmless. Stage only intentional files.

## Testing and measurement strategy

- **Contract tests:** use P0-01 frozen histories across quiz reporting, evidence classification, scorer and replay. Test old/new payload versions, server-only answers, no false evidence from exposure/hints/retries and immutable first response.
- **Content tests:** validate source-specific rights, reviewer approvals, Unicode/script/spans, answer ambiguity, source-family and transliteration-near-duplicate holdouts, hard-edge cycles, stale mappings, atomic publication and withdrawal. Human linguistic review is separate from passing schema tests.
- **Safety and ownership tests:** gate every new direct practice route in local/non-local modes; later test every user-scoped route against another principal. Exercise deletion, export, backup and projection replay from populated fixtures.
- **Product tests:** run focused backend `pytest` and Ruff, frontend unit/build/e2e for touched views, then full affected stack before release. README commands are `cd backend && .venv/bin/ruff check . && .venv/bin/pytest -v` and `cd frontend && npm run test:unit && npm run build && npm run test:e2e`; PostgreSQL migration tests use the repository's disposable `SLOVNIK_TEST_POSTGRES_ADMIN_URL` setup. Browser mocks do not validate database, rights or linguistic correctness.
- **Learning measurement:** report delayed unaided first responses at 7/28 days with invited/completed denominators; productive recall by capability/modality; blinded unseen-task meaning and target accuracy separately; later independent error recurrence; false accept/reject and unresolved answers; critical content defects; minutes and workload distribution. Record version, source/context family, support and missingness. Do not score current heuristic `peak` as a calibrated probability.
- **Comparison discipline:** freeze analysis and thresholds before outcome review, randomize where possible, account for within-learner dependence/attrition, and distinguish feasibility from efficacy. P3 model calibration uses Brier/log loss at a declared horizon; prospective adoption uses delayed learning per minute and burden, not merely click or next-answer accuracy.

## Checkpoints and external decisions

| Checkpoint | Required evidence and release decision |
|---|---|
| **After P0** | All eight contracts/fixes and focused regressions pass; quiz key/privacy and first-attempt semantics are stable; source/rights and draft holdout validators work. P0-07 remains explicitly provisional. Begin P1 only with documented editorial review route. |
| **Before P1 publication** | Serbian L2 educator signs off outcome/CEFR crosswalk, examples, variants and holdout separation; rights owner resolves permitted uses; P1-03b trigger is decided; transaction rollback passes populated-db tests. |
| **Before human local pilot** | Reviewed pack/scorer/feedback/stop behavior pass; true loopback gate is tested; consent, local retention, probe protocol and data minimization approved; no hard mastery edge without a reviewed policy. |
| **After P1 pilot** | Report content/scoring defects, 7-/28-day missingness and outcomes, transfer and workload. Decide whether each P2 content/corpus lane has a measured gap. An inconclusive study does not become an efficacy claim. |
| **Before remote/public history** | P2-01b trusted ownership plus P2-02b export and P2-02c deletion/retention/backup work pass. P2-08b is additionally needed if the wider curriculum relies on hard mastery unlocks. |
| **Before P2 breadth or audio claims** | Each pack/audio asset has rights, educator review, unseen assessment and replay-safe publication. State unassessed oral/listening skills explicitly; only P2-04b supports listening evidence. |
| **Before each P3 trial/adoption** | Data sufficiency, consent, baseline, primary metric, minimum useful effect, burden/safety guardrails, sample/power and rollback are frozen before looking at test outcomes. A separate reviewed decision is needed to adopt any winner. |

## Experimental-task rules

Every P3 task records a hypothesis, exact variant, immutable baseline, eligible population/data, exclusion and missingness rules, primary metric, effect threshold, burden/quality guardrails, analysis version and stop condition *before* evaluation. Choose numeric thresholds from the approved pilot variance, operational cost and product tolerance, not from an unsupported research claim; if they cannot be set, do not launch the trial. A task can finish **successful**, **failed** or **inconclusive**. Failure or inconclusiveness keeps the baseline; a successful offline result only permits the named prospective trial. A successful prospective result still needs human review of quality, access and operational cost before adoption. Prompt/model versions, source snippets and human labels are retained only under approved rights/consent. Model-only judgments never publish, score, unlock or rewrite history. P2-06/07 and P2-08b use the same recorded trigger/no-go discipline even though they are P2.

## Final completion criteria for the roadmap

The roadmap is complete when every listed parent is accounted for by its child task results: all required P0/P1 contracts and pilot deliverables pass; P2 production identity/lifecycle and any claimed timezone/listening/breadth capabilities pass their release gates; optional P2 resource/readiness branches have a measured adoption or documented no-go decision; and all P3 experiments have valid success/failure/inconclusive reports or a documented data/feasibility no-go. The active product has replayable versioned content, answer and policy decisions; old learner/content records remain readable or are removed only under the approved lifecycle; rights, scoring and ownership regressions pass; and product-state documentation reflects what actually shipped. Claims are limited to measured written outcomes and modalities. A general Serbian or CEFR attainment claim remains outside this roadmap without broader aligned assessment.
