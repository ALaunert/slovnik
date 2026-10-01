# Learning-system repository audit

Audit date: 2026-09-24. Scope: current repository implementation and its pedagogical implications; no product changes. Recommendations below are proposals for research synthesis and design, not accepted implementation requirements or measured learning effects.

## Evidence and status boundary

The canonical implementation inventory is [product-state](../product-state.md). This audit cross-checks it against services, ORM/schema, frontend views and tests. The [accepted domain ADR](../adr/ADR-language-assistant-domain-model-2026-08-26.md) describes the architectural direction; the [implementation ledger](../progress/PROGRESS.md) records its backend foundation. The older [domain-model progress page](../progress/domain-model-v0.1.md) still says implementation had not started in its historical milestone table; it must not override the newer ledger or actual code.

There are three distinct statuses:

1. **Public and authoritative:** vocabulary cards, per-word progress, independent new-word/review/quiz modes, editor and AI vocabulary drafts.
2. **Implemented internally:** separate catalog/curriculum/practice/progress modules, immutable evidence, replayable projections, technical A1 pilot, deterministic selector, optional shadow writes and diagnostics. These do not select the learner's public activities.
3. **Deferred:** curated A1 coverage, a public unified assistant, validated proficiency measurement, calibrated forgetting/difficulty models, listening/speech, production learning-history lifecycle and trusted identity.

This is source inspection, not an audit of a deployed database or learners. Content coverage cannot be inferred from local seed size; only three sample entries are supplied by the repository.

## Architecture and persistence inventory

| Layer | Current responsibility and evidence | Learning implication |
|---|---|---|
| Vue routes/views | [router](../../frontend/src/router.ts), [DashboardView](../../frontend/src/views/DashboardView.vue), new/review/quiz views | Learner chooses modes; no public orchestrated path. |
| HTTP/application | [main](../../backend/app/main.py), [routers](../../backend/app/routers/), [learning_service](../../backend/app/services/learning_service.py), [quiz_service](../../backend/app/services/quiz_service.py) | Legacy rules remain authoritative. |
| Shared content | [VocabularyItem](../../backend/app/models.py), [schemas](../../backend/app/schemas.py), [vocabulary_service](../../backend/app/services/vocabulary_service.py) | Flat bilingual card, one translation field and optional descriptive material. |
| Learner persistence | `UserProfile`, `UserWordProgress`, `QuizAttempt`, `QuizAnswer` in [models](../../backend/app/models.py) | Word-level schedule/status and partial quiz history, not measured general language proficiency. |
| Catalog foundation | [catalog domain](../../backend/app/domain/catalog.py), [catalog ORM](../../backend/app/domain_models/catalog.py) | Separate lexical unit, sense, written form, construction; grammatical activity support exists as a foundation. |
| Curriculum foundation | [CurriculumService](../../backend/app/services/curriculum_service.py), [frontier policy](../../backend/app/domain/curriculum_policy.py) | Published versions, target nodes, hard/soft prerequisites, CEFR outcome envelope. |
| Practice/progress foundation | [practice ORM](../../backend/app/domain_models/practice.py), [event service](../../backend/app/services/learning_event_service.py), [projection service](../../backend/app/services/learner_projection_service.py) | Immutable evidence and replay enable future correction without inventing missing history. |
| Internal selection | [NextActivityService](../../backend/app/services/next_activity_service.py), [validity/provider policies](../../backend/app/domain/selection_policy.py) | Deterministic, explainable internal policy; no public next-activity endpoint. |
| Editorial LLM | [AI service](../../backend/app/services/ai_vocabulary_service.py), [OpenAI client](../../backend/app/services/openai_vocabulary_client.py) | Produces editor drafts; does not teach, grade learners or control progression. |

Legacy schema: `vocabulary_items` stores both Serbian scripts, Russian translation, CEFR, theme, register, stress, meaning notes and two example text blobs. `user_profiles` stores chosen level, batch-size preference and UI language. The unique learner/word `user_word_progress` row combines exposure/quiz timestamps, answer counters, weak flag, lifecycle status and review schedule. `quiz_attempts` retains a serialized question plan; `quiz_answers` stores prompt, submitted answer and correctness. Generation-cache/reservation tables support editorial AI, separately from learning evidence.

The [domain migration](../../backend/alembic/versions/20260826_0005_domain_foundation.py) adds eleven tables: four catalog, three curriculum, three practice/history and one target-state projection. Domain targets distinguish sense recognition, sense-to-form retrieval and construction application in **written** modality. Form-specific targets require an explicit condition. `PracticeRun`/`ActivityInstance` retain lifecycle, retry links and snapshots; `LearningEvent` retains evidence and provenance; `LearnerTargetState` separates baseline, competence, memory and evidence cursor. These are real implementations, not grounds to claim a working grammar course.

## Learner flow and exact public semantics

### Entry and acquisition

Profile access uses a remembered `userId`, not authentication. The [dashboard](../../frontend/src/views/DashboardView.vue) permits manually choosing A1–C2, 1–50 new words, and Russian/Serbian UI. There is no placement assessment. The level is a preference, not an attained qualification.

`get_daily_new_words` selects unseen entries at exactly that level, ordered by vocabulary ID, limited to the configured count. It does **not** subtract words acquired earlier today: completing one batch and reopening can select another. Thus the current “daily count” acts as a per-session cap. `NewWordsView` displays both Serbian scripts and Russian together, permits previous/next, and completes the batch at the end. There is no elicited recall response; completion is exposure. `complete_new_words` records `seen`, timestamps and a review due one day later. See [service](../../backend/app/services/learning_service.py) and [view](../../frontend/src/views/NewWordsView.vue).

`WordCard` displays meaning notes and examples inside expandable details. It splits the two example blobs on newlines, removes empty lines, and pairs by index. This is presentation, not sentence annotation, graded contextual practice or comprehension evidence. Structured stress emphasizes a syllable in each script; it is not audio or a pronunciation assessment. See [WordCard](../../frontend/src/components/WordCard.vue) and [StressText](../../frontend/src/components/StressText.vue).

### Review

[ReviewView](../../frontend/src/views/ReviewView.vue) initially reveals only Russian cue, level and theme. Serbian answer/details appear after reveal; the learner then supplies Again/Hard/Good/Easy. Saving must finish before advancing, and a precise status endpoint reconciles a lost response. This is a useful retrieval opportunity, but the product observes a self-rating rather than the actual attempted Serbian answer.

`apply_review_rating` implements:

| Rating | Next interval | Other changes |
|---|---|---|
| Again | 10 minutes; stored days = 0 | Reset streak; mark weak. |
| Hard | 1 day | Reset streak; preserve weak state. |
| Good | 2 days if previous interval <2; otherwise ×2, cap 180 | Increment streak; clear weak. |
| Easy | 4 days if previous interval <4; otherwise ×3, cap 365 | Increment streak; clear weak. |

Three consecutive Good/Easy ratings set legacy `status=learned`; Hard/Again reset it to reviewing. This label records a rule, not demonstrated durable mastery. `grade_review` locks the owned progress row and rechecks due state before mutation. Queue SQL includes seen/reviewing/learned rows due at `next_review_at <= now`; null-schedule fallback admits weak rows or rows whose first and last exposures are both absent/before today. It orders weak first, then due time/null first, last exposure/null first, stable ID, capped at twenty. A future scheduled weak item remains future-due. The compatibility batch completion endpoint remains and schedules one day ahead without a rating. All semantics are in [learning_service](../../backend/app/services/learning_service.py).

### Quizzes and feedback

[Quiz selection](../../backend/app/services/quiz_service.py) differs from review scheduling. Daily quizzes consider all previously touched/weak words, prioritizing weak, touched today, latest exposure, then ID; cap twenty words. Weekly quizzes select current UTC calendar-week exposures plus weak words; cap forty. Neither is a delayed-retention sample selected from review due times.

Question types cycle by selected-word position: Serbian→Russian multiple choice, Russian→Serbian typing, Serbian→Russian remembered/forgot self-check. If a nonempty small selection lacks a type, the first word receives additional types so all three appear. A word therefore does not routinely receive balanced coverage of recognition and production.

`_distractors` takes up to three other entries, favoring matching level then theme, deterministically shuffles with word ID, and swaps the correct translation away from position one if needed. Thus position one is never correct when there are multiple choices. The code neither requires distinct translations nor establishes semantic plausibility; a sparse pool can provide fewer than four choices. These are item-quality limitations visible directly in code.

`_is_correct` trims/casefolds the submitted answer. Typing accepts exact current Latin or Cyrillic spelling; it does not model alternate valid forms, sense-conditioned synonyms, diacritic errors, morphology errors or Unicode NFC equivalence. Choice compares the Russian translation. Self-check calls “remembered” correct in the public score. The API response schema hides its answer until the dedicated reveal route; the frontend requires reveal before rating. Public grading reads the current `VocabularyItem`, whereas prompts are stored in the plan: a later editorial change can therefore alter the answer key relative to the presented prompt.

An incorrect answer increments an error counter, marks the word weak and clears its schedule, making it immediately eligible. Correct answers leave the schedule unchanged; correct weekly answers additionally clear weakness. Each failed question is repeated once at the queue's end; completion rejects unanswered required repeats. Final score counts a question correct if **either** attempt succeeded. Consequently score is eventual within-session success across mixed evidence types, not first-attempt accuracy or delayed retention. Mistakes retain incorrect attempts even if the repeat succeeds.

[FeedbackPanel](../../frontend/src/components/FeedbackPanel.vue) supplies correctness/repeat feedback, not an error explanation or corrected typing answer. Corrections appear in [ResultsView](../../frontend/src/views/ResultsView.vue), whose latest result is kept in sessionStorage; backend attempts exist, but no longitudinal analytics UI is implemented.

## Internal foundation: strengths and limits

[Catalog bootstrap](../../backend/app/services/domain_bootstrap_service.py) creates stable mappings and preserves legacy examples without fabricated annotation. It distinguishes words/MWEs conservatively and records source fingerprints. [Mapping resolution](../../backend/app/services/catalog_mapping_service.py) rejects missing, ambiguous and stale mappings before shadow evidence writes. This preserves evidence integrity, while automatic reconciliation remains deferred.

The [seed](../../backend/app/seed.py) supplies `hvala`, `molim`, `voda`, lexical recognition/retrieval targets, one demonstration hard edge and one soft edge. It supplies no construction pack. The technical A1 pilot tests mechanics; it cannot establish A1 communicative coverage.

[Projection](../../backend/app/services/learner_projection_service.py) credits competence only for deterministic evaluated responses. Correct adds one success; incorrect adds one failure. `peak = max(previous_peak, (1+success)/(2+success+failure))` after success; `uncertainty = 2/(2+success+failure)`. Self-reports/exposures do not increase competence. [Memory-v1](../../backend/app/domain/memory_policy.py) separately schedules deterministic success at one day initially, then doubles to 180 days; deterministic failure is due immediately. Self-rating uses the public rating intervals; first exposure schedules one day. This differs from legacy quiz schedule semantics and is intentionally non-authoritative.

The [frontier](../../backend/app/domain/curriculum_policy.py) requires a prerequisite state, native evidence, at least one deterministic success, and peak ≥0.6. A first clean success gives 2/3 and passes. Once achieved, historical peak does not fall on failure; this preserves curriculum availability. Neither peak nor its uncertainty has an empirical calibration in this repository. They must not be presented as probability of current recall, a confidence interval or CEFR attainment.

[NextActivityService](../../backend/app/services/next_activity_service.py) restricts candidates to published/ready targets within requested-level envelope, then chooses intent in order: due review, strengthen where failures exceed successes, acquire without deterministic evidence and without a future schedule, assess existing deterministic evidence. Acquisition has an actual UTC daily distinct-target budget. Ranking uses due date/weakness/priority/uncertainty according to intent, seven-day activity repetition where applicable, and stable tie-breaks. Higher-priority intent with no valid candidates returns `NO_VALID_CANDIDATE`; it does not silently fall through.

[ActivityValidityPolicy](../../backend/app/domain/selection_policy.py) checks target/operation/scorer/modality/response shape, recognition cue/options and non-target burden. Lexical candidates permit no unknown non-target items; constructions permit at most one unknown lexical/form item, with a soft prerequisite and gloss. Curated candidates report `non_target_item_count` as difficulty metadata. Metadata is preserved, but there is no fitted item difficulty or general difficulty-mismatch ranking. Construction completion/transformation are internal candidate shapes, not implemented learner-facing modes.

[Shadow quiz mapping](../../backend/app/services/shadow_quiz_service.py) correctly maps self-check to self-report/unknown rather than deterministic success; retries become separate activities. Nevertheless the projector gives deterministic retry successes unit weight, as it does initial responses; representable provenance alone does not solve evidence dependence. [Shadow runtime](../../backend/app/services/shadow_selection_runtime.py) is diagnostic. [Configuration](../../backend/app/config.py) defaults shadow off and requires lifecycle/trusted-identity gates outside local environments. Accepted writes are atomic with shadow evidence; failures in diagnostic selection comparison are isolated. Preserve these distinctions when planning public rollout.

## Content ingress and AI boundary

Manual editor create/update and AI fill are password-gated. [AI fill](../../backend/app/services/ai_vocabulary_service.py) checks existing vocabulary, then normalized generation cache, then provider; it supports partial drafts and does not publish a learner exercise. [WordEditorView](../../frontend/src/views/WordEditorView.vue) applies a patch with in-memory undo and explicit save. The [prompt/schema](../../backend/app/services/openai_vocabulary_client.py) requests null for uncertainty and controlled fields, including a CEFR label and stress. Structural validation, cache/provenance and concurrent-request fencing are well developed. They cannot establish linguistic truth, sense coverage, level appropriateness or accent accuracy. No editor review queue, resource citations, curated coverage matrix or learner-facing LLM evaluator is implemented. The importer documents are plans, not evidence of a public bulk-import capability.

## Gap analysis: proposed changes

Each benefit below is an intended design benefit requiring evaluation; the learning-research synthesis determines pedagogical priority.

| Current → problem | Repository evidence | Proposed change → benefit | Cost/risk and trigger |
|---|---|---|---|
| Three-rating `learned`; mixed quiz score → overinterpretable success labels | `apply_review_rating`, `complete_quiz` above | Describe observed exposure, self-rating, first response and retry separately; show delayed performance only when observed → interpretable progress | UI/schema compatibility; before public mastery/proficiency reporting. |
| One success can unlock a hard edge; peak is permanent → weak evidence may satisfy a strong-looking rule | `_project_competence`, `_unready_reason` | Preserve monotonic access as a curriculum policy, explicitly separate it from competence claims; pilot readiness criteria using independent occasions and held-out transfer → testable readiness | Stricter gates can frustrate/block learners; compare policies before public frontier rollout. |
| Fixed card intervals and arbitrary confidence formula → no calibrated retention estimate | `MemoryPolicyV1`, projection formulas | Keep deterministic baseline; collect lawful longitudinal first-response/delay data and compare prospective prediction/workload before replacing policy → measurable scheduler value | Cold-start and biased data; do not add FSRS/BKT merely for sophistication. |
| Flat translation/examples; no taught construction corpus → vocabulary cannot substantiate general Serbian ability | `VocabularyItem`, `WordCard`, seed | Curate a small outcome-linked A1 pack with senses, forms, constructions, contextual examples and answer variants → meaningful, bounded activity coverage | Editorial expertise/licensing and ongoing quality ownership; before A1 claims. |
| Fixed quiz-type rotation, biased choices, exact mutable answer key → avoidable measurement artifacts | `_distractors`, `_is_correct`, `start_quiz` | Version answer keys, curate distinct distractors, balance answer positions, classify acceptable variants and error types → more defensible correctness | Variant false positives and migration effort; prioritize before treating quiz results as assessment. |
| Immediate retry and self-check contribute to aggregate score → supported success obscures unaided performance | `complete_quiz`, `ShadowQuizService.record_answer` | Keep retry practice but report/interpret its provenance separately; add a later independent probe → separate practice recovery from retention evidence | More learner time; confirm feedback/probe policy in research synthesis. |
| Wrong typing gets binary feedback, corrected answer only at results → no targeted repair during the attempt sequence | `FeedbackPanel`, `ResultsView` | Provide a bounded correction and, where useful, one contrastive explanation before an appropriate follow-up → actionable feedback | Explanations require validated content; disclosure changes evidence interpretation. |
| “Daily” new count is per fetch; review/quiz calendars differ → unclear workload promises | `get_daily_new_words`, `_source_progress`, selector UTC bounds | Define a shared daily workload policy and honest labels, preserve user control, introduce timezone only with a concrete scenario → predictable plan | Avoid silently changing existing pacing; before reminders/multi-region scheduling. |
| Strong infrastructure tests, no demonstrated learning-outcome evaluation → functional correctness can be mistaken for teaching efficacy | Test inventory below | Evaluate held-out delayed recall, new-context transfer, first-response accuracy by capability, workload and abandonment; preregister comparison questions → evidence for changes | Needs sufficient learners, privacy design and content validity; avoid raw score/time-on-app as sole success. |
| AI structural validation/cache without linguistic ground truth → polished drafts may remain wrong | `RawAiVocabulary`, editor workflow | Add editorial source/provenance and reviewed sample rubrics for senses, examples, stress, level and variants → auditable content quality | Reviewer time; before expanding content volume or automatic publication. |

## Verification, preservation and deferred triggers

Existing [learning tests](../../backend/tests/test_learning.py) verify queue SQL/order/caps, interval transitions, row locking, status reconciliation and three-rating status. [Quiz tests](../../backend/tests/test_quizzes.py) verify ownership, repeats, week boundaries and reveal hiding. Notably `test_multiple_choice_does_not_always_put_correct_answer_first` validates only a narrow positional property; it does not establish unbiased options. [Projection tests](../../backend/tests/test_projection.py), [selector tests](../../backend/tests/test_next_activity.py), [curriculum tests](../../backend/tests/test_curriculum.py), [shadow tests](../../backend/tests/test_domain_shadow_integration.py) and [migration tests](../../backend/tests/test_migrations.py) cover durable foundation invariants. [Review unit tests](../../frontend/tests/unit/review.test.ts) and [active-recall e2e](../../frontend/tests/e2e/active-recall.spec.ts) protect reveal/save/focus/layout behavior. AI tests use mocks, and e2e uses mocked backend responses.

These are substantial engineering assets to retain. They do not evaluate learner retention, communicative transfer, accent accuracy, prerequisite validity, answer-variant coverage or calibration of numerical estimates. Prior full-suite results in product-state remain historical. On 2026-09-24 this audit reran the targeted learning, quizzes, projection, curriculum, next-activity, domain-catalog, domain-contract and practice-contract suites: **312 passed, 5 skipped**. The five PostgreSQL cases require `SLOVNIK_TEST_POSTGRES_ADMIN_URL`; the full backend, frontend and PostgreSQL suites were not rerun. Documentation links and whitespace were checked. No production database was accessed and no runtime code changed.

The [research synthesis](research.md) supplies the pedagogical evidence for these proposals.
In the [reviewed roadmap](roadmap.md), assessment defects map to P0-01–03 and P0-08;
provenance/content contracts to P0-04–05 and P1-03–04; evidence dependence to P0-06;
curriculum to P0-07; practice/feedback to P1-05–06; workload to P1-08 and P2-03;
outcome evaluation to P1-09; and optional resource imports/readiness changes to P2-06–08.
Fitted models/AI remain P3 experiments. See [review](review.md) for corrected dependencies and
scope, and [implementation plan](implementation-plan.md) for the P0 sequence. These are
recommended priorities, not completed changes or measured benefits.

Honor the accepted [deferred log](../progress/domain-model-v0.1.md): curated content before public A1/unified-flow claims; privacy lifecycle and trusted identity before production shadow history; independent corpus only when examples need reuse/governance; morphology entities when productive scenarios need them; audio state only when real audio observations exist; model-assisted scoring only for a defined otherwise-unscorable response class with validation/fallback; fitted memory/IRT/BKT when adequate data exposes baseline limitations; bandits/RL only with valid delayed outcomes and controlled experiments. The existing four-context monolith, stable identities, honest unknowns, immutable evidence and replaceable policies already provide the appropriate foundation for these decisions.
