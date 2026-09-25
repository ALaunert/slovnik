# Provisional written A1 pilot: editorial and holdout brief

Status: **draft for Serbian L2 educator review** (P0-07). This is a finite task contract, not published curriculum, approved language material, a CEFR syllabus, or evidence of learner proficiency. The companion [manifest](manifest.json) is a file-backed proposal; its target IDs are draft semantic handles, not published catalog UUIDs. The technical seed in `backend/app/seed.py` remains unrelated and its prerequisite edges provide no pedagogical evidence.

## Learner and assessment boundary

The proposed learners are adults with Russian as a strong language, learning everyday Serbian in Serbia. Prior Serbian knowledge and reading ability in each script need a separate entry probe. Standard Ekavian is the initial editorial baseline; a qualified reviewer must specify acceptable Ijekavian, spelling, order and politeness variants per item. Content is written only, with Latin and Cyrillic as separate presentation/response conditions. A transliteration of the same prompt is the **same family**, never independent transfer. No listening, speaking, broad A1, or oral service-encounter result follows from this pilot.

The crosswalk uses the [Council of Europe 2020 CEFR Companion Volume](https://rm.coe.int/common-european-framework-of-reference-for-languages-learning-teaching/16809ea0d4), **printed pages**. Its scales describe activities under conditions; the following Serbian targets and stage order are product/editorial hypotheses. Paraphrases below are local task designs, not official descriptors.

| Outcome / stage | CEFR A1 scale, printed page | Primary target and capability | Input → practice → held-out assessment family |
|---|---|---|---|
| Personal details / 1 | Notes, messages and forms, p. 84 | `personal.fields` / apply construction | `profile.example-cards` → `profile.guided-form`, `profile.short-bio` → `profile.unseen-registration` |
| Simple request / 2 | Obtaining goods and services, p. 78 | `request.item` / apply construction | `request.model-dialogue` → `request.counter-card`, `request.shop-note` → `request.unseen-service-note` |
| Price information / 2 | Reading for orientation, p. 56 | `price.item-link` / recognize meaning | `price.annotated-sign` → `price.market-tag`, `price.cafe-board` → `price.unseen-service-board` |
| Location information / 2 | Notes, messages and forms, p. 84 | `location.static` / apply construction | `location.annotated-message` → `location.meeting-note`, `location.place-card` → `location.unseen-return-note` |

Each row's secondary target IDs, bounded written task, script conditions, scope note and separate meaning/form rubric are in the manifest. For personal details, use fictional data only. The price task asks for one item's amount and currency, not full menu understanding. The location task asks for a static place and optional return time, not directions or a full case paradigm. The request task is a **written rehearsal** aligned to an oral interaction scale; the educator must judge whether that crosswalk is appropriate before publication.

## Scoring and family separation

For every outcome, the rubric reports **communicative success** (did the response convey the requested information?) separately from **primary target accuracy** (was the reviewed construction or item-price link used correctly?). The latter never substitutes for the former. Approved alternatives are item-specific; an unreviewed but plausible response remains unresolved for human adjudication. Record the first unaided scored response before hint, reveal or correction. Label assisted responses, retries and self-ratings separately. A repeated prompt or translation can yield another first attempt, but cannot establish a new independent context occasion. These distinctions follow the [P0-01 measurement contract](../../../docs/testing/learning-evaluation.md).

The family IDs are editorial placeholders, not authored prompts. P1 content work must assign source/near-duplicate families **before** examples are exposed. Keep assessment prompts, translations, answer keys and close paraphrases out of input, practice, demonstrations and feedback. Script variants of one item share a family. Use a new held-out family for unseen transfer and for 7- and 28-day delayed probes; record invitations, completions, misses, support, source/context family, content and policy revisions, target, capability and modality. A learner who has seen a held-out family does not provide an independent transfer observation for that family. Reserve more than one distinct unseen family before a delayed protocol is approved; this draft names one assessment family per outcome but contains no actual tasks.

The three manifest edges are **soft suggestions** for editorial sequence only. There are no hard mastery gates: current frontier evidence is uncalibrated, and each proposed task can be attempted from its own context or an entry probe. Stage 0 script support may precede these tasks but is not a prerequisite node here. Do not infer readiness or lock progress from the technical seed's hard edge.

## Publication review checklist

- A qualified Serbian L2 educator approves or revises all four outcome-to-scale mappings, written-task boundaries, target/capability choices, stage sequence and rubrics; specifically resolves the oral-scale/written-request mismatch.
- The reviewer checks natural Serbian, sense, case/form use, Ekavian/Ijekavian and both scripts, register, answer variants and genuinely different input/practice/holdout families for every authored item. Record reviewer, revision and decision.
- A rights owner verifies each future source and permitted use; P0-04 provenance and P0-05 answer fixtures must pass before publication. This draft grants no rights and includes no publishable Serbian examples.
- Deterministic validation passes with `python3 content/curricula/a1-pilot/validate.py`. It checks IDs, references, rubric/coverage fields, target-kind/capability pairs, hard-edge cycles and family-ID disjointness. Human review must additionally catch transliterations, translations and semantic near duplicates that IDs cannot detect.
- Before a human pilot, approve consent, local retention and deletion, blinded assessment, 7-/28-day invitation windows, missing-data treatment, useful-effect/burden thresholds and sample rationale. Do not set proficiency cutoffs from this draft.

The educator approval and rights decisions are **external P1 publication gates**, not prerequisites for completing this P0 draft. There is no activation, migration or learner-facing behavior here.
