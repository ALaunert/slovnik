# Provisional Serbian written pilot: AI linguistic and pedagogical review

Review date: **2026-09-25** (Europe/Belgrade).
Reviewer: **Codex, GPT-6**; AI linguistic/pedagogical review, **not a credentialed Serbian L2 educator**. The exact serving variant/snapshot is not exposed in this session; the requested “astra” filename is not independent evidence of a model variant.
Reviewed branch: `codex/learning-roadmap-implementation`.
Reviewed commit: `1721cf4f6d7d8c8c92ce21d7f1e2b34e39c82908`.
Existing worktree: `/Users/aleksei/.codex/worktrees/learning-roadmap/slovnik`.

**Overall decision: revise.** The four-outcome design is a useful provisional editorial contract, but the current files are not a learner-ready local pack. **Reject the eight synthetic records for learner use, publication, or use as unseen assessment.** Retain them as structural test fixtures. This report does not approve them, change their status, activate content, alter learner progression, clear rights, or establish proficiency.

**This AI review does not satisfy the plan’s human sign-off requirement.** Qualified Serbian L2 approval, bilingual item/answer review and documented rights remain required under [P1-03a/P1-04b](implementation-plan.md#p1-03a--curate-a-reviewed-pilot-example-bank). Local-only use does not waive those project gates.

## Evidence and decision conventions

Read first: [AGENTS.md](../../AGENTS.md), [README](../../README.md), [product state](../product-state.md), and relevant learning design, pipeline, resource, review, implementation and evaluation documents. Audit order: outcome/crosswalk and split design first; synthetic examples second; primary-reference checks and validator verification thereafter.

- **Critical:** blocks learner use or valid independent assessment.
- **High:** materially compromises target coverage, answerability or interpretation.
- **Medium:** needs a contextual/editorial decision to avoid misleading instruction or scoring.
- **Low:** no specific defect identified within AI review; not an approval.
- **Verified** means inspected source/code or reproduced check. **AI judgment** means a reasoned provisional linguistic/pedagogical assessment. **Unresolved** means the needed primary evidence or human decision was not obtained.

Item decisions use **suitable for a provisional local pilot**, **revise**, or **reject**. No present learner item receives “suitable.” “Reject” below concerns promotion of synthetic fixtures, not deletion of useful tests. Suggested Serbian/Russian wording is review material only, not approved replacement content.

Repository evidence:

- [M: pilot manifest](../../content/curricula/a1-pilot/manifest.json)
- [B: editorial/holdout brief](../../content/curricula/a1-pilot/editorial-brief.md)
- [X: all eight synthetic examples and answer policies](../../content/curricula/a1-pilot/examples.synthetic.json)
- [D: example-contract decision](../../content/curricula/a1-pilot/example-contract-decision.md)
- [V: example validator](../../content/curricula/a1-pilot/validate_examples.py)
- [S: real-source manifest](../../content/sources/manifest.json)
- [E: evidence definitions](../testing/learning-evaluation.md)

## 1. Four-outcome CEFR crosswalk

All three cited **printed page** locators are correct for the linked 2020 edition. The scale introductions begin earlier; that does not make the manifest’s A1-row locators wrong. CEFR descriptions below are brief paraphrases; proposed corrections are this review’s local design judgments.

| Finding / outcome | Severity; decision | Primary-reference check | Target, language and task findings; proposed correction |
|---|---|---|---|
| O1 — `A1.PERSONAL_DETAILS` | High; **revise** | **Verified:** A1 Notes, messages and forms, printed p. 84, includes entering personal particulars; very simple registration also appears at Pre-A1. [CEFR p. 84](https://rm.coe.int/common-european-framework-of-reference-for-languages-learning-teaching/16809ea0d4#page=84) | Form completion is plausibly aligned; reading a profile and composing a self-description need separately justified receptive/production mappings. `personal.fields` is a task bundle, not yet a specified grammatical construction. The rubric mentions the copula, but neither associated fixture contains it. Define a fictional role, required fields, viewpoint and one elicited construction per scored activity. Form-field meaning success must not require a sentence when a name/city suffices. Treat reading, fields and copula coverage separately. Serbian naturalness, register, script and Russian wording of the actual task instructions remain unresolved because no instructions are authored. |
| O2 — `A1.SIMPLE_REQUEST` | High; **revise** | **Verified:** A1 Obtaining goods and services, printed p. 78, includes basic requests for food/drink; it is in oral interaction. [CEFR p. 78](https://rm.coe.int/common-european-framework-of-reference-for-languages-learning-teaching/16809ea0d4#page=78) | The existing “written rehearsal” caveat is necessary. Suitability as a written outcome remains an educator decision, not verified oral achievement. Specify addressee, service situation, item/quantity and whether the form target is a particular request pattern or any polite request. `molim` and `želim … molim` are not identical form targets. Require item-specific register and translation review; do not add conditional forms solely to imitate Russian wording. |
| O3 — `A1.PRICE_INFO` | High; **revise** | **Verified:** Reading for orientation, printed p. 56, includes simple information/costs at A1; price-finding also occurs at Pre-A1, while broader menu/list scanning appears at A2. [CEFR p. 56](https://rm.coe.int/common-european-framework-of-reference-for-languages-learning-teaching/16809ea0d4#page=56) | A bounded price task is plausible; a price label alone is not diagnostic of A1. `price.item-link` requires distinguishing the requested item from other lines. Both fixtures have only one line and no query. Add several distinct item-price pairs and an explicit requested item; vary layout and position without adding unfamiliar language burden. Define currency/number response conventions. Do not make numeral inflection a hidden production target in a recognition activity. |
| O4 — `A1.LOCATION_INFO` | High; **revise** | **Verified:** A1 Notes, messages and forms, printed p. 84, includes simple messages about whereabouts/return time. [CEFR p. 84](https://rm.coe.int/common-european-framework-of-reference-for-languages-learning-teaching/16809ea0d4#page=84) | A static place-location statement is a local adaptation, not an exact reproduction of the illustrated activity. The optional return-time target is never exercised. Define a recipient and a fictional arrangement that makes the message useful; author a separately reviewed return-time activity or explicitly remove that coverage claim in a future revision. Distinguish `u + locative` from `kod + genitive`; static meaning does not imply one case construction. Define landmark reference and acceptable spatial precision. The actual message cue, register and Russian instructions remain unresolved. |

Across all four: both scripts are declared, but no equivalent-condition task set exists; no item demonstrates an Ekavian/Ijekavian contrast. Do not fabricate a variant list or infer variant coverage from these strings. Acceptable spelling, word order, script and register alternatives require item-level decisions. Three soft edges express editorial suggestions; there is no evidence for turning them into mastery prerequisites. [M, B; Novi Sad’s own beginner syllabus covers both scripts and several case uses, but does not validate this sequence](https://www.srpski-strani.com/pocetninivo1_eng.php).

## 2. Input, practice and holdout design

| Finding | Severity; decision | Evidence and proposed correction |
|---|---|---|
| H1 — Named families are not authored coverage | High; **revise** | M names 4 input, 8 practice and 4 assessment families. X contains **0 input, 4 practice and 4 assessment records**, covering only four of six target handles. No `personal.copula` or `location.return-time` example exists. Create a coverage matrix by outcome, target, role, script and context before counting a pack complete. |
| H2 — Cosmetic differences do not establish transfer | High; **revise** | The personal pair swaps person/city and residence synonym; the price pair swaps item/number in the same one-line layout. Request and location pairs lack enough situation/context to establish genuinely distinct tasks. V blocks declared groups and exact normalized text/translation reuse, not these semantic similarities. Cluster by source and task template before split allocation; author a different communicative situation within the same taught target. Shared target vocabulary/constructions are expected and are not, by themselves, leakage. |
| H3 — Script is confounded with role | High; **revise** | Personal/price practice is Latin and assessment Cyrillic; request/location do the reverse. An observed practice-to-assessment difference could reflect script. Prepare reviewed orthographies and an assignment design that separates script access from target performance. Two transliterations of one task remain one family; never count both as independent transfer. |
| H4 — Exposed synthetic “holdouts” | Critical; **reject** | D explicitly says repository fixtures/keys are not deployable unseen holdouts. Do not promote, lightly paraphrase or rename these four assessment records as fresh tests. Keep real assessment prompts, translations, keys and close paraphrases out of learner input, practice, feedback and demonstration material; track per-learner exposure. No live leakage was observed or alleged: this is an editorial release blocker. |
| H5 — Delayed probes lack reserved independent families | High; **revise** | One named assessment family per outcome cannot supply repeated independent immediate/7-/28-day probes to the same learner. B already acknowledges this. Allocate distinct unseen families for each planned occasion, and replacement families if exposure occurs; transliterations and name/number substitutions are not replacements. Freeze assignments before observations under E. |
| H6 — Stimulus, instruction and private key are not distinguished | Critical if deployed as-is; **revise** | X stores a sentence plus variants, without an eliciting instruction, response field or visibility contract. Displaying a model answer before a production attempt would make it assisted/copying. Reading price labels is legitimate stimulus, but displaying the Russian price translation would bypass Serbian reading. Author separate public stimulus/instruction and private policy/rubric, with reveal timing and support recorded. |
| H7 — Positive strings are not a scoring policy | High; **revise** | Each item has only two positive variants; there are no item-specific negative/borderline labels, punctuation/case rules, partial-credit dimensions or output-script rules. V accepts an unrelated nonempty answer in an in-memory diagnostic. Use frozen human-labeled correct/incorrect/unresolved cases; preserve meaning success separately from the primary form target. Never convert a plausible unlisted answer directly to “wrong.” |

## 3. Item-by-item synthetic language review

All eight entries retain `draft_unreviewed` status and the test-only source `synthetic-p0-05`; **text and Russian-translation rights are pending for every item**. Each decision is **reject for learner use**. Corrections describe what a separately authored candidate would need; none authorizes changing these fixtures to approved content.

All eight stored target spans reconstruct exactly and the existing NFC checks pass. Serbian letters in the current stimuli are consistent with their declared script on inspection. This does not prove reviewed paired orthography or output-script policy. The assessments below are **AI judgments**, except where independently verified evidence is identified.

### X1 — `ex-personal-practice` / `ap-p1`

**High; reject.** Text: “Mila živi u Nišu.” Russian: “Мила живёт в Нише.” [X]

Natural neutral residence statement; third-person `živi` and proposed locative analysis of `u Nišu` are plausible. Latin diacritics are intact; Cyrillic counterpart is absent. The Russian sentence preserves the residence meaning. `stanuje` is plausible in this specific residence context, not an unrestricted synonym for every sense of `živi`.

The span `živi u Nišu` excludes the name and represents neither requested form fields nor copula use. Without a prompt, third-person description cannot establish first-person fictional form completion. Specify the role and response task; elicit a separate identity/copula pattern if retained. Review contextual alternatives such as subject omission only when the cue makes the referent clear. Treat its shared residence template with X2 as a near-duplicate risk. Exact lexical interchangeability and Russian stylistic approval remain unresolved.

### X2 — `ex-personal-holdout` / `ap-p2`

**High; reject.** Text: “Јован станује у Ужицу.” Russian: “Йован живёт в Ужице.” [X]

A plausible neutral residence statement; `станује` is third-person singular. **Verified attestation:** the city authority itself uses `у … Ужицу`; do not “correct” Serbian `Ужицу` merely to match the Russian place-name form. [City of Užice](https://uzice.rs/javne_ustanove/gradska-uprava-za-finansije/) This is usage evidence, not a complete normative paradigm or a Russian transliteration ruling.

Serbian Cyrillic is consistent; no Latin counterpart is reviewed. Russian meaning is plausible, but Russian name/toponym convention has not been independently verified here. The accepted `живи` alternative needs the same contextual constraint as X1. There is no registration form, requested field set or copula; the name is outside the target span. Replace this assessment candidate with a genuinely new registration task and private key. Names/city, synonym and script changes alone do not establish independence from X1.

### X3 — `ex-request-practice` / `ap-r1`

**Medium language concern; high task ambiguity; reject.** Text: “Молим једну воду.” Russian: “Пожалуйста, одну воду.” [X]

Plausible service-order shorthand. AI morphological analysis: `једну воду` is feminine singular accusative; the whole request lies in the annotated span. Cyrillic is consistent, including the reordered variant “Једну воду, молим.” Both word orders are plausible in an order context, but politeness depends on addressee and setting; no primary source inspected here settles their exact register.

The Russian is understandable as a café order but awkward without a serving context. “Одну воду, пожалуйста” is a possible review candidate, not an approved translation. Specify a menu serving or bottle only if the scenario actually establishes it; adding “бутылку” otherwise invents information. Ask reviewers about `Молим вас, једну воду` and other equivalents instead of making `вас` universally mandatory or optional by model fiat. Provide a prompt that requires a request, not reproduction of the displayed answer. Re-evaluate the shared order template with X4.

### X4 — `ex-request-holdout` / `ap-r2`

**High; reject.** Text: “Želim jedan čaj, molim.” Russian: “Я хотел бы чай, пожалуйста.” [X]

Understandable request; AI analysis identifies present first-person `želim` and masculine inanimate accusative `jedan čaj`, whose form does not distinguish accusative from nominative. It cannot alone demonstrate productive case discrimination. Latin diacritics are consistent.

The Russian uses a masculine conditional politeness formula and leaves “one” implicit; Serbian `želim` does not encode speaker gender or conditional morphology. This can be a pragmatic translation, but is a misleading one-to-one cue for a narrow form exercise. Prefer a reviewed gender-neutral order rendering (candidate: “Один чай, пожалуйста”) with an explicitly communicative task, or supply an accurate explanatory gloss. Do not force a Serbian conditional to repair a Russian cue.

The span excludes final `molim`, while the outcome requires politeness. The second variant drops `želim`: fine for meaning if approved, not evidence of that verb construction. Define the target accordingly and review `Molim jedan čaj` and `Jedan čaj, molim vas` as candidates. Formality and relative naturalness remain unresolved. No independently specified service-note context separates this from X3; the fixture is already exposed.

### X5 — `ex-price-practice` / `ap-c1`

**High; reject.** Text: “Čaj — 120 dinara.” Russian: “Чай — 120 динаров.” [X]

Plausible price-label register; AI morphological analysis finds `dinara` appropriate after 120, and the Russian amount/currency match. Serbian Latin is consistent, but accepted “120 дин.” is Cyrillic while the other answer is Latin. That need not be a language error: it is an unresolved **response-script policy**, since `script` currently labels the stimulus.

The full span contains item and price, but copying the only number does not show item-price linkage. Create a multi-item notice plus a requested item. Specify whether currency is supplied by the response field, must be typed, or may use reviewed abbreviations; decide treatment of “120”, `120 din.`, and `120 RSD` rather than globally adding them. Normative abbreviation choices remain unresolved. Its template overlaps X6. `čaj` also occurs in X4; shared vocabulary alone is not assessment leakage, but inspect cross-outcome feedback before allocating real holdouts.

### X6 — `ex-price-holdout` / `ap-c2`

**High; reject.** Text: “Сок — 90 динара.” Russian: “Сок — 90 динаров.” [X]

Plausible neutral label; AI analysis finds `динара` appropriate after 90. Russian amount, commodity and currency align. Both accepted variants use Cyrillic; no Latin response condition is specified. The `дин.` abbreviation still needs a reviewed orthographic policy.

No requested item or competing line is supplied, so the only number is sufficient regardless of comprehension. Its declared board family does not make the one-line stimulus a different task from X5. Author a new multi-line board and query, preserve recognition rather than numeral-production scoring, and review currency omission and wrong-line/wrong-amount negative cases. Do not reuse this exposed answer as a fresh probe.

### X7 — `ex-location-practice` / `ap-l1`

**High target/context concern; reject.** Text: “Библиотека је у центру.” Russian: “Библиотека находится в центре.” [X]

Plausible neutral static statement; AI analysis: `је` is the copula and `у центру` is locative. Cyrillic is consistent and Russian meaning is plausible. “Centre” needs an established town/building reference; neither string specifies which.

The target span includes only the prepositional phrase; it cannot establish copula placement if the rest is supplied. “У центру је библиотека” is grammatically plausible but can present a library’s existence/location rather than answer the same discourse question with identical emphasis. Do not reject it categorically or accept all word orders blindly. Supply a cue, specify whether a short phrase is sufficient, and have reviewers adjudicate discourse equivalence. The cited clitic paper could not be retrieved, so exact normative support remains unresolved. There is no return-time content; X8 adds a different preposition/case, which must be taught before it is assessed as transfer.

### X8 — `ex-location-holdout` / `ap-l2`

**High; reject.** Text: “Pošta je kod parka.” Russian: “Почта находится у парка.” [X]

Plausible neutral static-location statement; Latin diacritics are consistent. AI analysis: `kod parka` is genitive government, not locative despite static meaning. [UD guidance](https://universaldependencies.org/sr/index.html) confirms the general need to distinguish governed case, but does not supply this exact normative example; an accessible primary grammar citation for this specific analysis remains unresolved.

The Russian conveys proximity, not necessarily “inside” or “immediately adjacent.” “Рядом с парком” is a possible contextual clarification, not automatically an equivalent key for every map. Establish which park and how precise the relationship must be. “Kod parka je pošta” requires the same discourse review as X7. Short `Kod parka`, full copular and `nalazi se` answers may be candidates if the task permits; do not auto-approve them. The phrase-only span does not test the copula. There is no return time despite the family’s name. A new scenario and explicit government coverage are needed; changing a library/centre to a post office/park does not itself validate a holdout.

## 4. Primary-reference verification and unresolved register

Sources accessed or attempted on **2026-09-25**:

| Reference / claim | Result and limit |
|---|---|
| [Council of Europe 2020 Companion Volume](https://rm.coe.int/common-european-framework-of-reference-for-languages-learning-teaching/16809ea0d4), printed pp. 56, 78, 84 | Relevant A1/adjacent-level rows and page locators verified from the official PDF text. Supports the bounded crosswalk checks above; does not establish this pack’s difficulty, task validity or Serbian grammar choices. No official descriptor text is reproduced in the pack by this review. |
| [University of Novi Sad Centre, A1 syllabus](https://www.srpski-strani.com/pocetninivo1_eng.php) | Verified institutional coverage of both scripts, present tense, relevant basic cases, introductions and shopping/restaurant topics. Does not verify any of the eight sentences, their level, stage order or answer equivalence. |
| [Universal Dependencies, Serbian/Croatian guidance](https://universaldependencies.org/sr/index.html) | Verified case inventory, agreement features and preposition government as annotation concepts. It is neither an item-level grammar authority nor a Russian translation review. |
| [City of Užice, finance administration](https://uzice.rs/javne_ustanove/gradska-uprava-za-finansije/) | Official usage attests the Serbian city form in a locational phrase. Does not settle Russian spelling/declension, register or reuse rights. |
| [Đorđević 2015 clitic-ordering paper](https://ltc.amu.edu.pl/a2015/book/papers/PAR-4.pdf), cited by learning-model S8 | Direct retrieval failed, including retry. No claim of consulting full text. Exact contextual equivalence/neutrality of the reordered copular answers remains unresolved. |
| [Novi Sad genitive-study volume](https://digitalna.ff.uns.ac.rs/sites/default/files/db/books/978-86-6065-432-0.pdf) and [university-hosted spatial-construction thesis](https://remaster.ff.uns.ac.rs/materijal/punirad/Master_rad_20230913_rus_350004_2020.pdf) | Full retrieval failed (size limit / HTTP 502). Search snippets are insufficient to close a normative claim; not used as proof. Obtain a lawfully accessible grammar passage and qualified adjudication for the specific government/variant questions. |

**Still unresolved:** educator acceptance of all four mappings and their difficulty; exact item-level grammar/naturalness and word-order adjudication; request politeness in a specified service context; bilingual register and Russian name/toponym conventions; currency abbreviation/output conventions; Ekavian/Ijekavian and alternate-script eligibility; independent holdout quality; rights.

The [Matica dictionary publisher reference in the resource register](serbian-resources.md#published-dictionaries--reference-use-not-a-bulk-import) is a route for later lawful consultation, not evidence that dictionary entries were read here. No unverified web phrasebook, machine translation or search snippet was used to certify a disputed answer.

**Rights finding R1 — Critical; reject promotion.** S is exactly a schema version plus an empty `sources` list. X has only a synthetic test-source declaration. There is no real author/translator agreement, license evidence, item permission decision or attribution package. All Serbian text and Russian translation rights remain **pending**, not “approved,” “public domain” or automatically exempt for local use. External pages consulted for linguistic evidence are not licenses for the fixture text. A structurally valid empty manifest approves zero items.

## 5. Verification performed

All commands ran against the requested worktree. Used the existing Python environment at `/Users/aleksei/projects/slovnik/backend/.venv/bin/python` only as an interpreter; imports/tests came from this branch. Bytecode writes and pytest cache were disabled. No database, migration, seed, publication service or learner endpoint was invoked.

| Check | Fresh result |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 python3 content/curricula/a1-pilot/validate.py` | **Passed**, exit 0. Four-outcome draft references, declared family separation, target/capability and graph/rubric structure validate. |
| `PYTHONDONTWRITEBYTECODE=1 python3 content/curricula/a1-pilot/validate_examples.py` | **Passed**, exit 0. Synthetic structural contract validates. |
| Same command with `--publish` | **Expected rejection**, exit 1: draft pack plus synthetic-source, unreviewed-item and unreviewed-answer-policy errors for all eight. This flag performs validation, not publication. |
| From `backend/`: `PYTHONDONTWRITEBYTECODE=1 /Users/aleksei/projects/slovnik/backend/.venv/bin/python -m pytest -p no:cacheprovider tests/test_pilot_manifest.py tests/test_pilot_examples.py tests/test_content_provenance.py tests/test_learning_evaluation_fixtures.py -q` | **29 passed**, 2 dependency deprecation warnings (Starlette/httpx and anyio portal alias); no failures or skips. |
| Read-only coverage/span diagnostic | 0 input / 4 practice / 4 assessment; all 8 spans reconstruct; no copula or return-time target record. |
| Temporary in-memory validator probes; no files changed | Replacing X4’s variants with an unrelated sentence still returned no errors. Replacing Cyrillic X3’s initial `М` with Latin `M` and updating its span also returned no errors. These reproduce validator limitations, not newly approved examples. |
| Documentation checks | Local Markdown file targets and whitespace checked; report covers all 4 outcome IDs and all 8 example IDs. |

**Verification finding V1 — High; revise before a real pack.** V verifies structural spans/IDs and some duplicate signals, not natural Serbian, translation entailment, semantic answer correctness, paired-script equivalence, mixed-script exclusion in Cyrillic items, source-document ancestry, meaningful task coverage or private-key visibility. Its successful result must retain “publication not implied.” Existing tests pass because these linguistic/assessment questions are outside their present assertions. Add relevant checks with future pack/scorer work; no validator behavior was changed in this review.

The full backend, frontend, PostgreSQL integration and end-to-end suites were **not rerun** for this documentation-only review. Earlier full-suite results remain historical, not results of this task.

## 6. Exact next steps for a provisional local-only pack

1. **Resolve the brief with a qualified Serbian L2 educator (P0-07 → P1-03a).** Record reviewer, date, revision and decisions on O1–O4, written-request alignment, target definitions, field-versus-sentence responses, location government and optional return-time scope. Preserve soft sequencing and separate meaning/form rubrics.
2. **Create a separate authored candidate pack; retain X unchanged as tests.** Supply real stimulus, instruction, fictional role, expected response type, supporting-language inventory, private key and per-item target. Fill every retained input/practice/assessment and target coverage gap. Prepare paired reviewed scripts and an assignment matrix that avoids role/script confounding.
3. **Resolve rights with real evidence.** Record source/item IDs and separate Serbian author and Russian translator permissions for intended uses, evidence/agreement reference, reviewer/date, attribution and pinned artifacts where applicable. Keep missing decisions pending; placeholders and model-generated approvals do not count.
4. **Complete bilingual item/answer review.** Address X1–X8’s lessons in the new material, with independent overlapping human ratings and adjudication. Freeze permitted variants, numeric/currency and script rules plus negative/borderline cases. Unlisted plausible responses remain unresolved. Approve no item with an unresolved critical defect.
5. **Reserve and protect new holdouts.** Review source/template/semantic clusters across every outcome, feedback and translation. Allocate untouched families for each planned immediate and delayed occasion; maintain exposure records and private keys. Keep this report and all fixture answers out of learner assessment materials.
6. **Run content/rights/scorer preflight without activation.** Re-run the existing manifest/example/provenance suites on the new revision, extend validation for actual pack requirements, and review the rejection/change report. P1-03b stays conditional unless independently governed example reuse is demonstrated. P1-04a infrastructure alone does not clear P1-04b.
7. **Only in separately authorized implementation work, meet the local runtime gates.** Follow P1-04b and P1-05a–c, feedback/selection dependencies, then P1-09a’s opt-in local/development/test and actual loopback enforcement; test flag-off parity, remote/production refusal, snapshot privacy and stop/resume. Do not substitute the shadow flag for a direct-practice gate or alter progression based on this report.
8. **Before human participation, complete P1-09b.** Approve consent, retention/deletion, pseudonymous export, blinded rubrics, missingness and probe windows; freeze the protocol before answers are collected. Human research ratings remain separate from learner projections. Describe results as bounded written feasibility observations; make no oral, full-A1 or proficiency claim.

This task leaves those gates pending. It delivers a review artifact and a linked product-state audit note only.
