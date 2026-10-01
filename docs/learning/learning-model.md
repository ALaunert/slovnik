# Proposed learning model

Status: research proposal, 2026-09-24. No runtime behavior is changed by these documents.
Read [the current-system audit](audit.md) before this proposal, and [research](research.md)
for evidence strength. Implementation work is split in [the roadmap](roadmap.md).

## Decision and scope

Evolve the existing modular monolith into a **task-led curriculum with spaced, target-specific
practice**. A learner should be able to explain what an activity helps them do, why it is due,
and what evidence supports their progress. Preserve the catalog, curriculum graph, immutable
events, replay, and deterministic selection boundaries already implemented. Improving content
and observation quality is more urgent than replacing the scheduler with a sophisticated model.

Assumptions for the first release: adult Russian-speaking learners, everyday life in Serbia,
Serbian standard with an initially Ekavian editorial baseline, both scripts, and a small A1
pilot. These are product defaults inferred from the repository, not user research findings.
Ijekavian Serbian remains valid; variety, register, script and learner preference are separate
attributes. A written pilot can measure written skills only. Listening and speaking need their
own material, activities and evidence before any claim of complete A1 competence.

Three approaches were considered:

| Approach | Advantage | Limitation / decision |
|---|---|---|
| Improve isolated cards and substitute a new SRS | Small change; useful for lexical retention | Does not establish communicative goals, morphology transfer or production in context; keep as a component |
| Task-led, curated curriculum + bounded practice + corpus-informed content | Fits existing four contexts; inspectable selection and scoring; measurable transfer | Requires editorial work and an honest pilot scope; **recommended** |
| Open-ended AI tutor and generated curriculum | Broad surface coverage | Unreliable linguistic truth, attribution and progression; optional later experiment, not the foundation |

## Serbian evidence and its limits

CEFR descriptors specify what people can do under particular conditions; they do not assign
Serbian cases, words or verb aspects to universal levels. Use the descriptor edition, scale,
level and locator to ground each outcome, then have a Serbian L2 educator map constructions
and tasks to it. Store a paraphrase separately from official wording and its reuse permissions.
See the framework evidence in [research](research.md).

Local teaching sources help constrain that mapping. The Novi Sad Centre's published A1 syllabus
includes both scripts, present/past, several basic case uses and everyday transactions; its A2
syllabus extends case functions, future, conditional and imperative. These are institutional
choices, not proof of a unique acquisition order. [S1, S2]

Marinković's dissertation analyzes textbook distribution and proposes a grammatical minimum;
it is not a randomized curriculum comparison. Lompar's chapter preview argues that beginner
L2 explanations cannot depend on native-speaker intuitions or prior mastery of grammatical
terminology. These support explicit, accessible patterns with meaningful tasks, not copying
an L1 school grammar. Only the dissertation metadata/abstract and chapter preview were used
here. [S3, S4]

Aspect requires both lexical and contextual treatment. Krajišnik discusses limitations of
prefix-based rules. Rađenović's beginner study measures choices between aspect alternatives;
it does not establish free-production mastery or the best teaching sequence. We therefore
propose early recurring exposure to relevant contrasts, followed by increasingly independent
use, rather than delaying all aspect until an advanced level. [S5, S6]

### Linguistic requirements that change the design

The linguistic facts below are supported by the cited references; the teaching and data choices
are proposals. This is a dependency/coverage inventory, **not a list to teach in this order**.

| Feature | Consequence for content, practice and scoring |
|---|---|
| Gender, animacy, adjective agreement | Three genders and agreement features must be represented; masculine animacy can affect forms. Teach a noun in a meaningful phrase and test transfer to a new noun, not only a gender label. [S7] |
| Seven cases: nominative, genitive, dative, accusative, vocative, instrumental, locative | Model a construction's function and governed form. The same surface string can support several analyses; never equate an ending with one case. [S7] |
| Prepositions and government | Prepositions select case, so store target spans and government constraints. Contrast location and destination in a bounded task before broad paradigm drills. [S7, S2] |
| Present, perfect, future and conditional | Use person/number and relevant participial agreement in reviewed constructions. Begin frequent functional patterns before exhaustive tense tables. Conjugation, agreement and clitic position can be distinct primary targets. [S1, S2, S7] |
| Aspect | Store lexical aspect and curated sense-specific relations; do not treat an aspect partner as just another inflected form or assume every verb has one. Never infer aspect solely from a prefix or tense. [S5, S6] |
| Clitics and order | Serbian second-position placement is sensitive to phrase/prosodic structure; it is not simply “the second whitespace token.” Cluster ordering requires constrained templates and accepted alternatives. Early chunks can contain clitics before explicit cluster manipulation. [S8] |
| Word order | Teach a neutral pattern first, then information-structure choices. A valid alternative order should not fail a meaning task; a clitic-placement task may require narrower constraints. [S8] |
| Negation | Separate polarity, negative forms and negative-pronoun constructions. Test meaning reversal, not mere presence of a character sequence; curated contrasts are needed. [S7] |
| Motion | Avoid one-to-one transfer from Russian motion verbs. Okano documents differences between Serbian *ići* and Russian *идти*, including use with transport. Use destination/path contexts and sense-specific Russian glosses. [S9] |
| Comparatives/superlatives | Store reviewed irregular and alternating forms; ask learners to compare choices in a situation. Adding a suffix mechanically is not a sufficient evaluator. [S4, S7] |
| Numbers and agreement | Price/time chunks can precede general numeral agreement. Later vary quantities within curated noun phrases; do not generate every numeral combination from a single singular/plural toggle. Quantification can govern case. [S2, S7] |
| Reflexive verbs | Retain *se* with the lexical entry/construction when required; distinguish functions editorially. A generic parser's reflexive/expletive label is not a complete teaching analysis. [S7] |
| Latin/Cyrillic | Reuse the same lexical identity with multiple orthographies. Assess reading in each script when relevant; do not award two lexical acquisitions for transliterated duplicates. Both occur in local beginner teaching. [S1] |
| Pronunciation and stress | The current stressed-syllable marker cannot encode the interaction of tone, stress and length. Keep it as a limited cue; use reviewed audio before listening claims. Regional realizations vary. Do not gate beginner progress on automated pitch judgments. [S10] |
| Register and BCMS variation | Label source variety and context rather than “correcting” every regional variant. Expert review decides whether an answer is acceptable for the task and chosen Serbian norm. A BCMS reference identifies differences but is not an open content license. [S11] |

Russian knowledge may help comprehension while hiding productive gaps. The size of this effect
for Slovnik is unknown. Diagnose it with separate comprehension, inflection and construction
tasks; do not skip Serbian practice merely because words look familiar. Keep contrastive notes
brief and keyed to observed errors. The motion comparison above is evidence for one specific
contrast, not a universal account of Russian-speaking learners.

## Proposed curriculum progression

Progression is a spiral of communicative functions. These stages are a proposed editorial
sequence, not CEFR-mandated units or a promise that finishing them awards A1/A2. Each stage
reuses earlier language in new contexts and returns to it after delays. The **first funded
content milestone should cover only stages 0–2**, followed by evaluation before expansion.

| Stage / intended envelope | Communicative outcome and material | Focus to introduce or revisit | Evidence required |
|---|---|---|---|
| 0 / entry and Pre-A1 support | Identify a name, read a sign, greet and ask for repetition | Script contrasts, sound–spelling through reviewed recordings when available; fixed repair/greeting chunks | Separate script recognition from word meaning; prior knowledge can bypass instruction after a probe |
| 1 / selected A1 goals | Give basic personal details; understand a short profile | Copula/personal forms, noun gender in phrases, simple agreement, questions and negation; frequent *se* chunks | Read an unseen profile and write relevant details with support removed |
| 2 / selected A1 goals | Request an item, understand a simple price, ask where a place is | Frequent present forms; accusative object and locative location constructions; numbers as practical chunks; politeness | Interpret a new short notice/menu and produce a bounded request/location response |
| 3 / broaden A1 | Describe routines, family and a recent event | More agreement and case functions, possession/origin genitive, perfect, recurring aspect contrasts, more clitic patterns | Delayed recall plus unseen-context comprehension and constrained production |
| 4 / A1–A2 bridge | Arrange a visit, describe a journey, give or receive something | Destination vs location, source, instrumental means/company, dative recipient, vocative address, future, imperative and polite conditional chunks | Complete new travel/message tasks; no requirement to recite all seven paradigms first |
| 5 / selected A2 | Compare options, resolve a simple problem, narrate a short sequence | Numeral agreement, comparative/superlative forms, broader perfect/aspect distinctions, pronoun/clitic clusters, simple connected clauses | Several task contexts, delayed production, and human-rated samples; add audio before oral claims |
| 6 / later B1+ design | Connected narratives, explanations, repair and register choices | Aspect/discourse, subordination, richer word order and register variation | Separate future specification and external proficiency alignment; no invented B1–C2 coverage now |

An outcome record should connect `function → CEFR scale/locator → communicative task →
target set → controlled practice → unseen assessment`. A grammar feature alone is not an
outcome. Use hard prerequisites only when an activity cannot be attempted meaningfully;
use soft prerequisites for helpful background. Allow a short diagnostic to demonstrate
readiness. Repeated failure should offer easier input or a repair activity, not a permanent lock.

### Initial pilot alignment

The following is a proposed crosswalk for educator review, not an official Serbian syllabus.
Locators use printed pages in the [2020 CEFR Companion Volume](https://rm.coe.int/common-european-framework-of-reference-for-languages-learning-teaching/16809ea0d4).
Outcome IDs are local identifiers; the tasks and grammar selections are our proposals.

| Local outcome | CEFR A1 scale and locator | Proposed unseen task / assessment boundary |
|---|---|---|
| `A1.PERSONAL_DETAILS` | Notes, messages and forms, p. 84 | Complete a fictional registration form and short profile; score requested information separately from targeted copula/agreement forms. |
| `A1.SIMPLE_REQUEST` | Obtaining goods and services, p. 78 | Compose a bounded request for an item. This written rehearsal prepares for an oral descriptor; it cannot establish oral achievement. |
| `A1.PRICE_INFO` | Reading for orientation, p. 56 | Find a requested price on an unfamiliar simple notice; avoid requiring broader menu comprehension. |
| `A1.LOCATION_INFO` | Notes, messages and forms, p. 84 | Write a short location/return-time message; assess a reviewed location construction separately from successful communication. |

Script access, hints and response constraints belong in each rubric. These four outcomes do
not establish complete A1 coverage; [P0-07](roadmap.md#p0-07--specify-the-small-communicative-pilot-and-assessment-holdout)
must specify a draft mapping and separate assessment family before content production. A Serbian
L2 educator must approve the mapping before pilot publication.

For example, a location/destination contrast can progress from a short contextual encounter,
to meaning discrimination, to completing one form, to writing a new route message. The
illustrative strings *u školi* / *u školu* are author-written sketches, not corpus quotations
or publication-ready examples. Production content must pass [the content pipeline](content-pipeline.md).

## Minimal purposeful data model

Use the four contexts from the [accepted ADR](../adr/ADR-language-assistant-domain-model-2026-08-26.md).
Names in the left column below describe pedagogical concepts; the implementation should reuse
the existing names in the middle column. Proposed additions are not already implemented.

| Concept | Existing home / smallest proposed change | Concrete purpose |
|---|---|---|
| Lexeme / lexical item / chunk | `LexicalUnit`, `EntryKind.WORD/MWE` in [catalog.py](../../backend/app/domain/catalog.py) | Stable identity across senses and written forms; fixed chunks use MWE, productive slot patterns use Construction |
| Lemma | Citation `Form`, plus POS/disambiguation metadata | Corpus lookup/grouping; lemma string alone is not a unique lexeme ID |
| Word form | Existing `Form` + typed subset of `morph_features` | Curated inflected answers and agreement; no whole-language paradigm generator |
| Sense | Existing `Sense` + gloss language | Separate polysemy, contextual translations and acceptable answers |
| Sentence/context | **New** catalog-owned example record, source occurrence and target-link metadata | Reuse an example across targets, preserve exact text and license, independently review/retire it; embedded legacy examples remain readable |
| Grammar concept | Existing `Construction` with constrained slots and morph features | Practice a meaningful pattern and diagnose a targeted error; add standalone government/aspect relation entities only when multiple uses require independent versions |
| Function, topic, register | Versioned controlled metadata in the curriculum/content pack initially | Select task-relevant material and filter inappropriate register; do not create a service for every label |
| CEFR descriptor / outcome | Versioned outcome metadata keyed by current `outcome_code`, linked to `CurriculumNode` | Cite framework scale and define a task/rubric; keep requested level distinct from assessed performance |
| Prerequisite | Existing hard/soft curriculum edges | Explain availability and avoid graph duplication |
| Frequency | Versioned corpus summary attached to lexeme/form or query result | Rank useful candidates with dispersion and register; frequency is not a level or acquisition order |
| Receptive/productive evidence | Existing `TargetSpec` capability + modality + bounded conditions | Distinguish recognizing a sense, retrieving a form and applying a construction |
| Memory / competence | Existing `LearnerTargetState`, with versioned projection refinements | Keep due-time scheduling separate from demonstrated skill and confidence |
| Exposure/error history | Existing immutable `LearningEvent`; structured error tags as bounded extension when used | Preserve first attempt, support, correction and repeated errors without a second mutable history store |

`UsageExample` currently has text, translation and a free-text target annotation; it does not
implement the proposed corpus. Rights and provenance need a pilot contract, but independent
example persistence remains conditional on demonstrated reuse or withdrawal needs under
[the prior domain decision log](../progress/domain-model-v0.1.md). Likewise richer morphology,
audio and open response remain separately scoped extensions, not reasons to replace that design.

Maintain a deliberately small target vocabulary. A `condition` may constrain a morphology bundle
or script when that is what is assessed; do not put sentence IDs, prompt wording or every context
feature in the target key. Those belong to the activity snapshot. Otherwise one skill fragments
into hundreds of sparse learner states. Keep separate context coverage in the evidence projection.

There is no need for independent “recognition strength,” “receptive mastery,” and “recall strength”
tables: these are views of capability-specific evidence and memory. A later calibrated probability
must state its event definition and prediction horizon; it is not a general “knows Serbian” score.

## Exposure to independent use

1. **Encounter:** a short, comprehensible context with a communicative purpose; optionally show
   a gloss or translation. Record exposure only, not success.
2. **Understand:** a meaning decision that cannot be answered from position, length or repeated
   surface clues. Give corrective feedback. Recognition updates recognition evidence only.
3. **Retrieve:** remove the answer; request a word/chunk or bounded form from an unambiguous cue.
   Offer an explicit hint when needed and record it. Self-rating remains useful for scheduling,
   but is not interchangeable with a scored answer.
4. **Use a pattern:** a short completion or transformation with one primary target and familiar
   supporting language. Separate case selection from spelling and lexical choice where possible.
5. **Vary and delay:** change nouns, speaker or situation, then return on another day. Copying a
   revealed answer is repair, not an independent retrieval success.
6. **Transfer:** an unseen message/sign/dialogue and a goal-directed response. Score the intended
   meaning and primary construction with an explicit rubric. Use human review for early open
   responses; do not force them through a single exact string.

This is not a mandatory six-screen funnel for every word. Existing evidence can skip supports;
failed retrieval can return to input. Mix due retrieval with new meaning-focused material within
the learner's budget. Interleave previously introduced contrasts deliberately; do not randomly
mix every new word or grammar form. Research supports the principles more strongly than this
particular product sequence; measure its value against an equal-time baseline.

## Exercise and evaluator contract

| Exercise | Evidence it can support | Main validity constraint |
|---|---|---|
| Glossed reading / listen-and-read later | Exposure | No mastery credit for merely displaying or advancing |
| Meaning choice / contextual selection | Receptive knowledge for that target and modality | Plausible, non-overlapping distractors; balanced answer position; enough options or suppress the item |
| Cue-to-form typing | Bounded productive retrieval | Cue identifies a sense; accept reviewed Serbian orthographies/variants as task permits |
| Contextual cloze | Form or construction use under support | Store exact target spans; context must disambiguate intended answer; support counts toward evidence conditions |
| Transformation | Controlled construction application | Reviewed input/output constraints and multiple accepted variants, no general syntax checker claim |
| Short communicative response | Task success and potential transfer | Rubric, unseen context, evaluator reliability; production operation needs a deliberate contract extension |
| Self-rated reveal | Subjective recall and workload scheduling | Preserve as self-report; never relabel as objectively correct |

Keep [the existing four operations](../../backend/app/domain/practice.py) for the controlled pilot.
Adding independent comprehension/production or listening requires versioning enums, payloads,
SQL constraints, evaluators, frontend and replay tests together. A text box alone does not add
validated communicative assessment.

Deterministic scoring means a bounded answer policy, not “linguistically infallible.” Normalize
NFC, documented whitespace and case policy. Preserve diacritics; distinguish orthographic slips
from a wrong target form. Permit cross-script answers when script is not the target; handle
Latin digraphs, names and mixed-script ambiguities conservatively with curated aliases. Store
acceptable variants with task/content revision, not a global fuzzy edit-distance threshold.
If a natural answer is outside the key, report uncertainty/route for review; avoid penalizing
the learner and expanding the answer key automatically from an LLM suggestion.

Feedback should identify the target error, provide a concise explanation and a usable corrected
example, then give a later opportunity to retrieve. Preserve the original response separately from
repair. Once an answer has been accepted, the current service terminalizes its activity and
records one immutable event; a subsequent repair therefore uses a linked retry activity/event.
Do not append a repaired response to an already accepted event. First/final fields within a
single event describe observations collected before that event was finalized. Correcting every
incidental error at once is a proposed UX policy
to avoid overload, not a proven optimum. Safety-critical misunderstanding in a real-world
scenario should still be made clear. The first pilot should use ordinary everyday scenarios.

## Learner state, scheduling and readiness

The foundation supports first/final response, hint history, latency, evaluation source,
confidence and policy-version fields; current shadow adapters leave unavailable observations
unknown. Populate those fields faithfully before adding more fields.
Latency includes device/typing/accessibility effects; it should not initially penalize competence.

| Observation | Competence/readiness consequence | Memory consequence |
|---|---|---|
| Exposure or answer shown before response | Evidence of contact only | May schedule a first retrieval; cannot establish successful recall |
| Correct first answer, unassisted, unambiguous | Positive evidence for the primary capability | Eligible to extend the target's review interval |
| Incorrect first answer, then repaired | Retain failure; repair is a distinct result | Shorter revisit; do not erase first failure |
| Hinted answer or repeated same prompt | Supported success, not independent proof | Conservative practice scheduling; no multiplication of evidence from retries |
| Self-rating | No objective competence update | Keep current scheduling role, labeled as subjective |
| Ambiguous / model-only verdict | Unknown until validation; no automatic gate unlock | Offer fallback practice; do not invent success or failure |
| Success on unseen context after delay | Stronger coverage of the intended use | Evidence for interval/difficulty calibration, not universal mastery |

Evaluate a replacement for the weak peak threshold before public curriculum rollout, while
preserving the accepted ADR's **monotonic curriculum access**: once opened, material remains
accessible despite forgetting. Keep access achievement distinct from reversible readiness and
current memory risk. Historical `competence.peak` can remain for compatibility. Readiness should be an
explainable, policy-versioned checklist rather than a falsely precise probability:

- **Encountered:** one valid exposure.
- **Practicing:** at least one scored attempt with its support conditions recorded.
- **Demonstrated in this mode:** proposed pilot rule of three independent first-attempt successes
  across at least two contexts and two days, including one delayed by at least 24 hours; exclude
  repair, self-report and ambiguous judgments. A new independent failure returns this status to
  practicing until a later unassisted success. This is a conservative operational hypothesis,
  **not an empirically established mastery threshold**.
- **Transfer checked:** a separate unseen task observation; describe its scope and date.

If pilot evidence supports a revised rule, implement readiness as a replayable projection from
eligible evidence and stable context IDs. A supervised local pilot can avoid mastery-based hard
edges while comparing the proposed rule in shadow; the three-success checklist is not a release
gate by itself.
Record whether the introduction criterion has ever been achieved for a prerequisite; use that
monotonic achievement for access and current readiness for recommended practice. Do not relock
old units after a new failure. An explicitly authored recognition prerequisite can permit
introducing a production activity; it does not establish productive competence.
Do not silently reinterpret legacy streaks or manufacture dates, contexts and hints for old
answers. Keep a legacy baseline with unknown competence. The exact readiness checklist and the
thresholds used for hard prerequisites need pilot calibration; “demonstrated” can still decay in
recall probability, so it must not remove an item permanently from review.

Retain a transparent interval policy as the experimental baseline. Put new scheduling behind
the existing `MemoryPolicy` seam, version it, and compare delayed recall per minute and review
burden. Later fit a memory model only when longitudinal retrieval data permit held-out evaluation.
Use separate parameters/evidence for recognition and production where data support them. Do not
claim that the existing doubling/tripling intervals or a proposed desired-retention percentage
are validated for Serbian. No scheduling algorithm compensates for an invalid cue or wrong answer.

The selector should apply gates in this order: published and licensed content → learner/profile
scope → prerequisites → suitable supporting language → budget → due review/new/repair/assessment
allocation → deterministic ranking with stable tie-breaks. Log the reason and policy. Cap new
work when review burden is high, provide an explicit stop, and avoid endless weak-item loops.
“No suitable activity” must be a valid result with an understandable next step.

## Validation and architectural boundaries

Until an explicit production/human-evaluation contract extension exists, the pilot's human-rated
communicative transfer tasks belong to a separate consented research dataset. They may have
multi-dimensional rubrics but do not become `LearningEvent` records or update learner projections.
The current evaluator-source enum has no human-scoring category. Preserve one primary elicited
target per in-product activity.

Use the metrics and evaluation design in [research](research.md) and release gates in
[roadmap](roadmap.md). Measure delayed first-attempt recall, unseen-context transfer, error
recurrence, calibration and review burden. A learner finishing a unit or feeling familiar with a
word is not sufficient evidence. Test language validity and measurement validity independently
from software correctness.

Publish catalog and curriculum revisions together; activity snapshots keep the content and
answer-policy revision used at response time. Editorial correction must not rewrite history or
silently carry evidence across changed senses. Preserve strict stale-mapping checks; introduce
explicit reviewed reconciliation only for identified semantic changes. Keep history inside the
current data-lifecycle and trusted-identity release gates.

## Serbian references consulted

- **S1:** University of Novi Sad Centre for Serbian as a Foreign Language,
  [A1 syllabus](https://www.srpski-strani.com/pocetninivo1_eng.php), accessed 2026-09-24.
- **S2:** Same Centre, [A2 syllabus](https://www.srpski-strani.com/pocetninivo2_eng.php).
- **S3:** Marinković, N. (2016), *Grammatical minimum of Serbian as a foreign language*,
  [University of Belgrade dissertation metadata/abstract](https://eteze.bg.ac.rs/application/showtheses?thesesId=3957).
  The dissertation is CC BY-NC-ND 3.0 Serbia; consultation is not permission to embed its material commercially.
- **S4:** Lompar, V., *Applied Grammar of Serbian as a Foreign Language at Levels A1 and A2*,
  [publisher preview and DOI](https://doi.org/10.1007/978-3-658-49579-4_2), pp. 17–30.
  Publisher citation says 2025; first-online metadata says 2026-01-02. Full chapter not accessed.
- **S5:** Krajišnik, V. (2023), *Glagolski vid u nastavi srpskog kao stranog jezika*, pp. 93–107,
  [full text](https://doi.fil.bg.ac.rs/pdf/eb_ser/ssjtip/2023-5/ssjtip-2023-5-ch8.pdf),
  DOI 10.18485/ssjtip.2023.5.ch8. Linguistic/pedagogical analysis, not intervention evidence.
- **S6:** Rađenović, A. (2023), *Kategorija glagolskog aspekta u srpskom kao stranom jeziku*, pp. 83–92,
  [full text](https://doi.fil.bg.ac.rs/pdf/eb_ser/ssjtip/2023-5/ssjtip-2023-5-ch7.pdf),
  DOI 10.18485/ssjtip.2023.5.ch7. Small descriptive learner study.
- **S7:** Universal Dependencies, [Serbian/Croatian annotation guidelines](https://universaldependencies.org/sr/index.html).
  Engineering reference for represented features, not a complete grammar or curriculum; notably
  these guidelines do not include lexical Aspect in the language-specific features.
- **S8:** Đorđević, B. (2015), *Formal Representation of Clitic Ordering in Serbian*, LTC,
  [conference paper](https://ltc.amu.edu.pl/a2015/book/papers/PAR-4.pdf).
  Indexed paper text was accessible; direct PDF fetch timed out. No broad theoretical claims inferred.
- **S9:** Okano, K. (2015), *Lexico-Semantic Features of Verbs of Motion in Serbian and Russian*,
  pp. 203–218, [Hokkaido University full text](https://src-h.slav.hokudai.ac.jp/coe21/publish/no28_ses/Chapter4_2.pdf).
- **S10:** Zsiga, E. & Zec, D. (2025), *Culminativity and the Neutralization of Vowel Length in Four
  Neo-Štokavian Dialects*, [ISCA proceedings abstract](https://www.isca-archive.org/tai_2025/zsiga25_tai.html).
  Phonetic evidence, not an L2 teaching trial.
- **S11:** Vrabec, Ž., *Bosnian, Croatian, Montenegrin and Serbian: An Essential Grammar*,
  [publisher description](https://www.routledge.com/Bosnian-Croatian-Montenegrin-and-Serbian-An-Essential-Grammar/Vrabec/p/book/9780367723637).
  Used only to establish scope as a comparative reference; search-indexed publisher description
  accessible, direct page returned 403, book text not consulted.
