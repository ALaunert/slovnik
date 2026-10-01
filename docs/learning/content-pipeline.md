# Proposed authentic-content pipeline

Status: design proposal, 2026-09-24; not implemented. Resource versions, access methods and
licenses are investigated in [serbian-resources](serbian-resources.md). Pedagogical requirements
come from [learning-model](learning-model.md); current ingress is described in [audit](audit.md).

## Product decision

Use authentic usage to discover common senses, forms, collocations, constructions and register.
Publish only examples whose quality and reuse rights have been reviewed. A frequent web sentence
is neither automatically good beginner input nor automatically safe to redistribute. When suitable
authentic examples are unavailable, commission reviewed instructional examples informed by usage
evidence and label them as authored. Do not pass off an LLM paraphrase as an attested quotation
or assume that paraphrasing removes all rights issues.

Start with one source release, one narrow set of communicative goals and a bounded sample. Do
not download every corpus, generate thousands of examples, or build a public import UI first.
The pipeline is an offline editorial tool in the existing repository; it publishes versioned packs
through catalog/curriculum services. Learner requests never crawl the web or wait for a bulk LLM job.

## Source policy

The [CLASSLA-web 2.0 release](https://www.clarin.si/repository/xmlui/handle/11356/2079)
is the preferred large-scale **usage analysis** candidate; its Serbian data are offered as JSONL,
annotated JSONL and VERT. The release advertises CC0, while third-party rights require separate
attention. Use the resource register's distinction between corpus access/analysis and permission
to display selected text. Preserve release and source-document identifiers so that the permission
decision can be changed without losing lineage.

| Input | First use | Publication constraint |
|---|---|---|
| CLASSLA-web 2.0 Serbian | Lemma/form counts, dispersion, register/context discovery; candidate retrieval | Record corpus terms and the basis for reuse of each selected occurrence; unresolved web-text rights block publication |
| srLex, reviewed dictionary information | Candidate form/lemma analyses and editorial reference | Preserve source license/attribution; dictionary entry text is not free to copy merely because lookup is possible |
| Tatoeba reviewed Serbian sentences | A small source of self-contained examples and candidate direct translations | Keep sentence IDs, contributor attribution, license and translation-link provenance; not all linked pairs are direct or reliable |
| Reviewed, permissioned authentic material | Notices/dialogues/messages suited to the selected task | Document consent/license, attribution, personal-data handling and withdrawal process |
| Commissioned educational examples | Fill verified coverage gaps with natural, level-appropriate material | Original author agreement; mark authored/adapted provenance; linguistic review remains mandatory |
| UD/treebank data | Annotation fixtures and parser evaluation | Keep release/license; news-domain examples do not supply a balanced beginner course |

No source is enabled merely by appearing in the register. The first source manifest distinguishes
`analysis_allowed`, `redistribution_allowed`, `adaptation_allowed`, `attribution_required` and
`share_alike_required`, with the evidence and reviewer/date behind each decision. `unknown`
fails closed for the relevant use. A domain-level permission may cover many occurrences if its
scope is demonstrable; do not require fictitious per-sentence legal opinions.

## End-to-end stages and ownership

| Stage | Method and responsibility | Output / rejection behavior |
|---|---|---|
| 0. Select and approve source | Human decision from release metadata/license or author agreement and intended use; deterministic manifest validation | Pinned release/checksum when there is a downloaded release, permitted purposes and attribution template; prohibit unapproved acquisition |
| 1. Ingest | Deterministic streaming reader for a documented release schema | Immutable source ID, URL/document ID where supplied, byte checksum, capture/release dates; reject malformed records with reason |
| 2. Normalize | Deterministic NFC, whitespace/HTML cleanup under versioned rules; preserve original text | Canonical display text plus original-to-normalized mapping; quarantine broken encoding, mixed-script anomalies and unsafe markup |
| 3. Language and variety filtering | Retain corpus labels; versioned classifier only as a candidate filter; manual ambiguous cases | Serbian-confidence signal, likely variety and script; do not classify nationality from names or assume Cyrillic means Serbian |
| 4. Segment and deduplicate | Versioned sentence segmentation, exact hashes, near-duplicate clusters | Stable sentence IDs with source occurrences retained; flag fragments, boilerplate and syndicated copies |
| 5. Linguistically annotate | Reuse pinned corpus annotation or run a pinned Serbian NLP model; lexicon cross-check | Token spans, lemma candidates, POS/features/dependencies with tool version; uncertain analyses remain candidates |
| 6. Analyze frequency/context | Deterministic aggregation of corpus-derived observations | Form/lemma counts, denominator, document/domain dispersion and genre distribution; distinguish homographs and unresolved senses |
| 7. Select quality candidates | Deterministic screening and manual review; classifier/LLM triage only in a later measured experiment | Remove personal data, spam, unsafe content, context-dependent fragments, bad translations and target leakage; store reasons |
| 8. Estimate learning burden | Deterministic measured features + editor level/rubric judgment | Length, unfamiliar supporting items, construction burden, context independence, tentative CEFR envelope with rationale |
| 9. Enrich, if measured useful | An optional small model drafts translation, gloss, sense suggestion or explanation within a bounded schema; lexicon/corpus candidates come first | Non-authoritative suggestions with provider/model/prompt/version; missing information stays null |
| 10. Verify | Deterministic checks and qualified human adjudication; a stronger-model check is an optional evaluated aid | Reviewed target/sense/form alignment, naturalness, answer variants, level and rights; unresolved cases quarantined |
| 11. Publish | Human approval + deterministic catalog/curriculum publication transaction | Immutable pack manifest and compatible activity snapshots; no hidden provider calls in the transaction |
| 12. Observe and revise | Error reports and versioned editorial correction | Retire or replace defective content explicitly; preserve historical evidence and trace affected activities |

Annotation is **not deterministic linguistic truth**. A pipeline can reproducibly produce the same
wrong lemma. Deterministic operations are suitable for hashes, offsets, feature validation and
counts; empirical corpus counts are evidence about that sample; a lexicon/parser supplies candidate
analyses; editors resolve contextual linguistic truth. In particular, the Serbian UD guidelines
do not encode every pedagogically important distinction. Never convert an absent aspect tag or
ambiguous *se* analysis into a negative linguistic claim.

### Serbian normalization and annotation rules

Keep original script, diacritics, capitalization and punctuation as source facts. A separate
canonical search key may merge known Cyrillic/Latin correspondences for counting, but it must not
replace attested text or conflate inflected forms. Latin digraphs and names require explicit
handling; script conversion is not proof of lexical identity. Maintain offsets on a declared
representation (proposed: Unicode code-point offsets in NFC display text) and token IDs for
multi-token/discontinuous targets. If normalization changes offsets, rebuild alignment explicitly.

Do not rewrite Ekavian/Ijekavian, Croatian or Bosnian forms to Serbian and retain an “authentic”
label. Keep dialect/standard variation as metadata; filter the first pilot to its chosen scope and
add reviewed variants later. Language identification among closely related varieties has limits;
sample retained and rejected records to measure them. Set-derived balanced counts cannot repair
an incorrect language filter.

Retain ambiguous morphological analyses until context review. Define a small versioned feature
schema covering the forms actually taught: POS, lemma link, case, gender, number, animacy where
applicable, person/tense/mood, degree, and separately curated aspect. Store original tags and the
mapping version. Validate government and agreement only within the supported reviewed templates;
do not advertise a universal Serbian grammar validator.

### Frequency and context are different from curriculum priority

Compute both token/form and lemma+POS counts. Keep the corpus denominator and tokenization
policy; “per million” is meaningless without them. Add number of distinct documents/domains and
genre dispersion so one copied news story cannot dominate. Frequency by **sense** requires
disambiguated evidence or a human sample; do not inherit a lemma's entire count for every sense.
For chunks, use support and dispersion along with association measures; rare pairs can have high
association scores. Publish uncertainty and corpus coverage, not universal usage probabilities.

Candidate ranking should combine task utility, learner need, reviewed sense frequency, domain
dispersion, register, morphological usefulness, content quality and annotation confidence. Keep
the components inspectable; initially use an editor-visible tuple rather than a learned magic
score. A web corpus overrepresents some writing genres, so compare a frequency-driven shortlist
with a teacher shortlist and practical task coverage. Measure useful candidates per hour and
coverage gain before deciding to process the full release.

For example, a future query for a location construction should retrieve a target lemma plus a
contextual preposition/case candidate, then inspect concordances. Exact lemma matching alone
cannot prove the intended sense or government. Save query specification, source version, counts
and reviewed concordance IDs; corpus evidence is separate from the example eventually displayed.

## Minimal useful example contract

These are logical groups, not a demand for one database table per field. Small optional groups
can be JSON with versioned validation. Required-on-publication differs from required-on-ingestion.

| Group | Fields and purpose |
|---|---|
| Identity and lifecycle | `example_id`, `revision`, content hash, draft/reviewed/published/retired state; explicit replacement/derivation links |
| Text | Original Serbian text, NFC display text, original script, reviewed alternate orthography if any; context window or document reference for editor use |
| Translation | Language, text, translator/model provenance and review state; store sense-conditioned translation, not a parallel newline array |
| Target annotation | Stable token IDs/spans, lexical unit/sense/form/construction references, primary-target eligibility; supporting items and discontinuous chunks permitted |
| Linguistics | Token lemma/POS/morphology candidates, selected reviewed analysis, parser/lexicon versions; annotation confidence with documented meaning |
| Pedagogy | Communicative function, topic/register/variety, linked outcomes, CEFR estimate + assessor/method/version, difficulty feature vector |
| Corpus evidence | Release, query, observed form/lemma counts, dispersion, denominator, evidence context IDs; null when unavailable, not fabricated zero |
| Source and rights | Source record/URL/document ID, acquisition date, dataset license, text rights basis, permitted uses, required attribution, transformation chain |
| Quality | Naturalness/clarity/level/translation/answerability rubric ratings, reviewers, decision, reason codes, timestamps; keep original disagreements |
| Activity answers | Reference to reviewed answer-policy revision, accepted variants and error categories **per activity**, not a universal sentence answer |

Corpus frequency belongs primarily to a lexical/query evidence record; many examples may reference
it. Learner-relative unfamiliarity belongs to selection-time metadata, not a permanent sentence
CEFR label. “Naturalness confidence 0.97” from an LLM is not a calibrated probability; retain a
categorical decision and actual reviewer agreement instead. No need for embeddings or a graph
database in the first pipeline.

## LLM responsibilities and cost control

Use the existing AI adapter pattern as a precedent for typed results, timeout handling, validation,
cache versions and backend secrets. Keep the bulk editorial workflow separate from the existing
single-word endpoint and its reservation contract; do not overload a learner-facing request.

| Deterministic / resource-derived | Small model may propose | Stronger model may check | Human must approve initially |
|---|---|---|---|
| Source/license manifest facts, content IDs, hashes, offsets, tag mapping, counts, duplicate IDs, published references | Russian translation, sense match candidates, register triage, short feedback explanation, level rationale | Translation entailment, ambiguity, clitic/aspect plausibility, distractor conflicts; disagreements and a stratified audit sample | Rights decision, pedagogical target, unresolved morphology, naturalness, allowed answer variants, CEFR mapping, every pilot publication |

Do not ask either model to invent a license, source URL, corpus frequency, lemma ID, attestation,
stress pattern or proficiency certificate. Model-produced stress/linguistic candidates need an
independent reference or qualified review. A stronger model reviewing a weaker model is still a
correlated automatic judgment. Compare both with held-out human decisions; do not call agreement
between models “validated.” Source text is untrusted input: instructions in it must not direct
the pipeline or tools; use bounded fields, no tool access and no secrets in enrichment prompts.

Cache by source-content hash + relevant annotation/prompt/model versions. Retry only transient
failures with a bounded budget; schema/semantic failures go to quarantine with a reason. Persist
partial editorial work without allowing partial publication. Measure tokens/cost per candidate,
cost per approved example, rejection rate by stage, human minutes per accepted item and queue
age. If a stronger-model check is later tested, trigger it by disagreement/risk plus a random
accepted sample to catch systematic blind spots. Do not choose providers/models based on
unverified current prices.

## Repository integration, migration and publication

Extend the existing catalog only when pilot fixtures establish a need the embedded examples and
versioned files cannot meet. The P0 deliverables are a source manifest, pilot brief and minimal
example/answer fixtures. A later demonstrated need for independent reuse or withdrawal may justify
`backend/app/domain/content.py`, `backend/app/domain_models/content.py` and
`backend/app/repositories/content.py`; corpus adapters belong in an offline package only if a
bounded source trial is approved. These remain inside Language Catalog's ownership. `content/`
can hold small reviewed manifests/packs and attribution files; bulk corpora and provider artifacts
belong in configured storage outside Git. Names are proposed, not existing capabilities.

If new tables are justified, add an additive Alembic migration after the current head, rehearse
it against a representative populated database, and define safe downgrade behavior. Dropping a
populated new table is data loss, even if the migration technically has a `downgrade` function.
Keep legacy text blobs and APIs readable. An optional read adapter can expose legacy example
lines as `legacy_unverified` while preserving the raw payload; unequal line counts or absent
source/translation cannot be silently repaired.
Unknown rights/annotation prevent their promotion into the new published pack, not their erasure.
Bootstrap remains creation-only; preserve the current stale-fingerprint rejection.

Publish a pack with pinned source manifests, catalog revisions, outcome metadata, curriculum
version, answer keys, pipeline/reviewer versions and attribution output. A preflight should show
insert/update/retire counts, unresolved records and affected legacy mappings. Validate all links
before a transaction activates the pack. Repeating the same manifest must be idempotent. Failed
publication must leave the active pack intact. The existing curriculum publication service commits
and retires its predecessor; cross-catalog atomic activation requires explicit transaction
composition. Keep the prior compatible manifest for rollback by publishing a **new** curriculum
revision reproducing its permitted content, not by reactivating retired rows. Do not mutate
already-issued activity snapshots or revive withdrawn content.

Content correction is separate from history rewriting: retire a faulty example for future
selection, link its replacement, and define whether affected evidence is excluded by a new
projection policy. For withdrawal/privacy requests, respect the future lifecycle policy for raw
source text and response data; immutability does not mean indefinite retention of personal data.
The public shadow gates remain closed until that policy and trusted identity exist.

## Reproducibility, scale and evaluation gates

Use resumable stages with per-record status, source cursor, input/output checksums and versioned
rejection codes. Stream compressed JSONL/VERT and bound batch memory. Each job has input caps,
storage/cost limits and counters. A changed release/schema requires a new adapter/version and
contract fixtures; fail on unknown fields that alter interpretation, rather than quietly dropping
provenance. No full-corpus scan is part of this research task.

Before expanding beyond the pilot, require:

1. **Lineage:** every publishable example has a resolvable source/derivation and permission record;
   no unsupported license assumptions. Attribution export matches the active pack.
2. **Integrity:** text/target offsets reconstruct exactly; IDs resolve; source reruns are idempotent;
   Unicode, both scripts, ambiguous forms and malformed source fixtures are covered.
3. **Language quality:** all pilot examples reviewed by a qualified Serbian reviewer, with an
   independent overlapping review set and adjudication. Zero unresolved critical errors in the
   published pilot; report uncertainty rather than presenting a small sample as a population guarantee.
4. **Answer quality:** frozen positive and negative answer fixtures, including natural alternatives,
   achieve the predeclared false-accept/reject limits from the evaluation protocol. Unresolved cases
   are not silently scored wrong.
5. **Difficulty:** teacher estimates are compared with actual first-attempt performance and hint
   use, split by prior knowledge and script. CEFR estimates remain estimates.
6. **Scalability:** record accepted examples per source sample, memory/storage, throughput and
   editorial cost. Expand only if the added source improves task coverage or review cost.

Split evaluation by source document and near-duplicate cluster; where testing generalization,
also hold out domains, targets or construction families as appropriate. Do not let a translation,
transliteration or paraphrase of a test sentence enter practice. Human naturalness and learner
learning outcomes are different metrics: this pipeline can produce good materials, but only the
delayed/transfer study in [research](research.md) can test whether using them improves learning.
