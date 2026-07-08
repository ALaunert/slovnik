# Vocabulary Importer Design

Date: 2026-07-06
Last updated: 2026-07-08

## Goal

Build a v1 end-to-end importer that turns Russian-Serbian sentence-pair TSV data into live Slovnik vocabulary records.

The heavy processing must run locally because the VPS is not suitable for LM Studio or large local LLM inference. The server side should only need a prepared import artifact and database access.

## Current Product Context

Slovnik currently stores vocabulary in `vocabulary_items` with these live fields:

- `serbian_cyrillic`
- `serbian_latin`
- `russian_translation`
- `cefr_level`
- `theme`
- optional `usage_register`
- optional `stress_marker`
- optional `meaning_notes`
- optional `example_sentences`
- optional `example_translations`

The MVP has manual vocabulary CRUD, a tiny seed corpus, and no bulk import, AI generation, import staging, source provenance, lemma field, or duplicate-detection model.

## Scope

In scope for v1:

- Parse Tatoeba-style TSV rows with Russian sentence id, Russian sentence, Serbian sentence id, and Serbian sentence.
- Normalize Serbian sentences with CLASSLA.
- Group candidate vocabulary by Serbian lemma.
- Keep all source examples in local staging artifacts.
- Enrich candidates through LM Studio using an OpenAI-compatible chat completions API.
- Batch LLM requests with configurable batch size, timeout, retry count, and low concurrency.
- Use schema-constrained structured LLM output when the LM Studio model supports it.
- Trust the LLM semantically for v1.
- Deterministically validate output shape and app compatibility.
- Retry structurally invalid candidates individually once when useful.
- Write a portable import artifact.
- Import that artifact into the app database on the server without requiring CLASSLA or LM Studio.
- Support an import dry-run mode that validates and reports without writing database rows.

Out of scope for v1:

- Verifier-model stage.
- Human review UI or terminal approval flow.
- Backend upload endpoint.
- API push to the deployed server.
- Live `lemma` column migration.
- Semantic guarantees beyond LLM output plus deterministic validation.
- Updating existing live vocabulary rows with new examples or improved translations.

## Architecture

The importer has two environments.

### Local Enrichment

A CLI runs on the developer's machine, where CLASSLA and LM Studio are available.

The local pipeline:

```text
source.tsv
  -> normalized-candidates.jsonl
  -> llm-enriched.jsonl
  -> import-ready.jsonl
```

It parses source rows, normalizes Serbian text, groups by lemma, accumulates sentence examples, calls LM Studio in batches, validates LLM output, retries structurally invalid candidates once when useful, and writes files that can be moved to the server.

### Server Import

A lightweight command runs on the VPS or any machine with database access. It reads `import-ready.jsonl`, validates each row against the current app schema, skips obvious duplicates, writes accepted records directly through SQLAlchemy, and emits an import report.

This command does not require CLASSLA, LM Studio, or access to the original TSV.

### Future API Path

The artifact should keep each accepted row shaped like the existing vocabulary API payload plus metadata. A later version can add API push to send the same artifact to the deployed FastAPI app instead of copying files to the VPS.

## Source Data

The first supported input is a TSV file where each row has:

```text
Russian sentence id <tab> Russian sentence <tab> Serbian sentence id <tab> Serbian sentence
```

The Serbian sentence may be Cyrillic or Latin. Duplicate Russian sentences with different Serbian variants are allowed.

Malformed rows are recorded in a parse report. Valid rows continue.

## Candidate Model

The importer creates one candidate per Serbian lemma, not one candidate per raw token occurrence.

Each candidate includes:

- stable `candidate_id`, using a SHA-style identifier.
- `lemma`.
- CLASSLA part of speech when available.
- observed surface forms.
- all collected sentence-pair examples.
- optional fingerprint/provenance metadata.

The `candidate_id` should be deterministic across reruns. For v1, compute it from a canonical payload containing normalized lemma, POS, normalized script-independent lemma form when available, and source name. Do not include the full example list in the primary id, because adding more source rows should enrich an existing candidate instead of changing its identity. If two candidates still collide, include a deterministic disambiguator in the hash input.

Repeated occurrences of the same lemma do not create new candidates. They add examples to the existing candidate.

The target vocabulary unit is useful learning vocabulary, not every mechanical lemma. The importer should use a hybrid filter:

- Deterministically discard only obvious mechanical noise before LLM enrichment, such as punctuation-only tokens, empty tokens, pure numbers, and technical artifacts.
- Send ambiguous cases to the LLM, including function words, short high-frequency words, and semantically ambiguous lemmas.
- Let the LLM decide whether each candidate is useful learning vocabulary. A candidate is either accepted as a ready vocabulary item or rejected with a controlled reason.

## Artifacts

Each stage writes a durable file artifact so the pipeline can resume without repeating expensive earlier work.

### `normalized-candidates.jsonl`

One row per lemma candidate.

Example:

```json
{
  "candidate_id": "sha256:...",
  "lemma": "радити",
  "pos": "VERB",
  "forms_seen": ["radiš", "радиш"],
  "examples": [
    {
      "source": "tatoeba",
      "ru_sentence_id": "5411",
      "sr_sentence_id": "2332057",
      "ru": "Что ты делаешь?",
      "sr": "Šta radiš?"
    }
  ]
}
```

### `llm-enriched.jsonl`

One row per LLM decision. Accepted rows include a live vocabulary payload plus importer metadata. Rejected rows include a controlled rejection reason.

Example accepted row:

```json
{
  "candidate_id": "sha256:...",
  "status": "accepted",
  "vocabulary": {
    "serbian_cyrillic": "радити",
    "serbian_latin": "raditi",
    "russian_translation": "делать, работать",
    "cefr_level": "A1",
    "theme": "daily-life",
    "usage_register": null,
    "stress_marker": null,
    "meaning_notes": "Глагол употребляется для действий и работы.",
    "example_sentences": "Šta radiš?",
    "example_translations": "Что ты делаешь?"
  },
  "metadata": {
    "lemma": "радити",
    "pos": "VERB",
    "confidence": 0.91,
    "selected_example_count": 1
  },
  "rejection_reason": null,
  "note": null
}
```

Example rejected row:

```json
{
  "candidate_id": "sha256:...",
  "status": "rejected",
  "vocabulary": null,
  "metadata": {
    "lemma": "...",
    "pos": "PUNCT",
    "confidence": null,
    "selected_example_count": 0
  },
  "rejection_reason": "punctuation",
  "note": "Punctuation-only candidate."
}
```

The accepted and rejected shapes must be mutually exclusive:

- `status = accepted` requires a non-null `vocabulary`, non-null `metadata`, and null `rejection_reason`.
- `status = rejected` requires null `vocabulary`, a non-null `rejection_reason`, and may include `metadata` and a short note.

Allowed rejection reasons:

- `not_serbian`
- `punctuation`
- `proper_name`
- `too_ambiguous`
- `bad_source`
- `not_useful_learning_vocabulary`

### `import-ready.jsonl`

Contains only accepted rows that passed deterministic validation and are ready for server import.

### Side Files

The pipeline writes side files as applicable:

- `rejected-candidates.jsonl`: valid LLM rejections with candidate id, lemma, reason, and optional note.
- `invalid-llm-output.jsonl`: candidates that still failed structural/schema/app-contract validation after repair retry.
- `duplicate-skips.jsonl`: import-stage duplicate skips with candidate id, reason, existing word id when available, and normalized Serbian headwords.
- `parse-errors.jsonl`: malformed source TSV rows.
- `import-report.json`: import or dry-run counts.
- `run-summary.json`: pipeline-stage summary counts.

## LLM Enrichment

The first LLM provider is LM Studio through its OpenAI-compatible chat completions API.

Local testing on 2026-07-08 confirmed that LM Studio structured output works with `google/gemma-4-26b-a4b-qat` through `/v1/chat/completions` and `response_format.type = json_schema`. The test also showed that schema design matters: a permissive schema allowed a contradictory rejected row with filled vocabulary fields. V1 should therefore use a stricter schema that makes accepted and rejected rows mutually exclusive, for example through `oneOf` or an equivalent application schema.

### Structured Output Schema Requirements

The enrichment schema should be revised around the importer contract, not just around field types.

- Batch responses should use a predictable envelope, such as `{ "results": [...] }`, so the response can be parsed uniformly even for one candidate.
- Each result item should be constrained as exactly one of two shapes:
  - accepted result: `status = accepted`, non-null `vocabulary`, non-null `metadata`, null `rejection_reason`, optional `note`.
  - rejected result: `status = rejected`, null `vocabulary`, non-null `rejection_reason`, optional `metadata`, optional `note`.
- `additionalProperties: false` should be used for the envelope and nested objects where practical.
- Enums should be encoded in the schema for `status`, `rejection_reason`, `cefr_level`, and `theme`.
- Nullable fields should be explicit. Do not allow rejected rows to carry populated vocabulary fields.
- App-level validation must still re-check the parsed result after schema-constrained generation.

The prompt shape should be:

```text
Task instructions and output schema.

List of candidate lemma records with examples.
```

Candidate inputs must include lemma, forms seen, POS when available, and example sentence pairs. Bare word lists are not enough because the model needs context to avoid bad translations.

The LLM returns structured output aligned by `candidate_id`.

The enrichment request should use schema-constrained structured output whenever supported by the active LM Studio model. Plain JSON prompting is only a fallback. Even with structured output enabled, deterministic validation remains mandatory because the importer must still enforce app-level constraints and semantic contract rules such as status/payload consistency.

Each accepted output should provide:

- Serbian Cyrillic headword.
- Serbian Latin headword.
- Russian translation.
- CEFR level.
- Theme.
- Optional usage register.
- Optional stress marker.
- Optional meaning notes.
- Selected example sentences and translations for the live app.

When multiple examples are selected for the live app, the LLM should choose up to three best examples. Serialize `example_sentences` and `example_translations` as newline-separated strings in matching order. The first Serbian example line corresponds to the first Russian translation line, and so on. The importer should preserve this convention until the app has a richer examples table. All source examples remain available in staging artifacts.

The LLM may reject candidates only with the controlled reasons listed above.

### Theme Classification

The LLM must choose exactly one `theme` from this controlled enum. Free-form themes are not allowed.

- `greetings`
- `personal-info`
- `family-relationships`
- `home`
- `daily-life`
- `food-drink`
- `shopping-money`
- `travel-transport`
- `places-directions`
- `health-body`
- `education`
- `work`
- `free-time`
- `nature-weather`
- `services`
- `language-communication`
- `technology-media`
- `emotions-qualities`
- `time-numbers`
- `grammar-functions`
- `other`

The prompt should tell the LLM to use `other` only when none of the specific themes fit.

### CEFR Classification

`cefr_level` is an LLM-estimated learning level, not an official Serbian CEFR lexical annotation. CEFR is a cross-language proficiency framework for learner abilities, while individual word-level labels are heuristic unless backed by a language-specific lexical profile.

The prompt should guide the LLM with CEFR-style usefulness:

- `A1`/`A2`: basic everyday survival vocabulary, greetings, personal information, family, food, travel, common verbs, and basic function words.
- `B1`/`B2`: broader everyday vocabulary, work/study topics, opinions, common abstractions, and less immediate but still general-purpose vocabulary.
- `C1`/`C2`: rare, literary, highly abstract, formal, specialized, or idiomatic vocabulary.

## Batching and Retry

The enrichment stage uses simple configurable batches for v1.

Configuration should include:

- LM Studio base URL.
- Model name.
- Temperature.
- Batch size.
- Timeout.
- Repair retry count, defaulting to one individual retry.
- Max concurrency.

Recommended default concurrency is low, likely one request at a time, to avoid overloading the local model.

If a batch response is structurally invalid, valid candidates from that batch are kept where possible. Invalid candidates are retried individually once with a repair prompt that states the exact validation failure. Retry is only for structural, schema, or app-contract failures, not for semantic disagreement with a valid LLM decision. Candidates that still fail after retry are written to `invalid-llm-output.jsonl` and are not included in `import-ready.jsonl`.

## Deterministic Validation

Validation is mechanical. It does not decide whether the vocabulary content is semantically correct.

Validation checks:

- Response parses as structured JSON.
- Every requested `candidate_id` has exactly one output row.
- `status` is `accepted` or `rejected`.
- Accepted and rejected rows follow mutually exclusive shapes.
- Rejection reason is one of the allowed enum values and is present only for rejected rows.
- Accepted rows include required vocabulary fields and rejected rows do not include a vocabulary payload.
- `cefr_level` is one of `A1`, `A2`, `B1`, `B2`, `C1`, `C2`.
- `theme` is one of the controlled theme enum values.
- Bounded fields fit current database/API limits:
  - `serbian_cyrillic` <= 160.
  - `serbian_latin` <= 160.
  - `russian_translation` <= 240.
  - `theme` <= 80.
  - `usage_register` <= 80 when present.
  - `stress_marker` <= 160 when present.
- Example fields are present for accepted rows where examples are expected.
- Example sentence and translation line counts match when both are present.
- Cyrillic and Latin fields are present.
- Deterministic transliteration checks or fixes obvious Cyrillic/Latin mismatches where practical.
- No malformed encoding, control characters, or duplicate candidate rows in the artifact.

## Duplicate Handling

Local duplicate handling:

- One candidate per lemma.
- Later occurrences of the same lemma add examples only.
- All examples remain available in staging artifacts.
- The LLM selects up to three best examples for the live vocabulary item.

Server duplicate handling:

- V1 does not add a live `lemma` column.
- The import command performs best-effort duplicate checks against existing live vocabulary using normalized Serbian Cyrillic/Latin values.
- Existing live words are skipped as new imports.
- Duplicate skips are counted and written to `duplicate-skips.jsonl` with the candidate id, reason, existing live word id when available, and normalized Serbian headwords.
- The artifact keeps lemma metadata so a future migration can backfill a real lemma column.

Rerunning the same artifact should not create obvious duplicate live records.

## Commands

The CLI should expose resumable commands:

### `normalize`

Reads TSV input, runs CLASSLA, groups candidates by lemma, and writes `normalized-candidates.jsonl`.

### `enrich`

Reads normalized candidates, calls LM Studio, writes `llm-enriched.jsonl`, `import-ready.jsonl`, and rejection/error reports.

### `import-artifact`

Runs on the server or anywhere with database access. Reads `import-ready.jsonl`, validates rows, skips duplicates, inserts accepted rows, and writes `import-report.json`. With `--dry-run`, it performs the same validation and duplicate checks but does not insert rows.

### `run-local`

Convenience command for local processing only. Runs `normalize` and `enrich`. It does not import into production by default.

### `run-all`

Convenience command for local/dev use against the configured database. Runs `normalize`, `enrich`, and `import-artifact`.

## Configuration

Configuration should support:

- TSV path.
- Output directory.
- Source name.
- CLASSLA settings.
- LM Studio base URL.
- LM Studio model.
- LLM temperature.
- LLM timeout.
- LLM repair retry count.
- LLM batch size.
- LLM max concurrency.
- Dry-run mode for import.
- Candidate/sample limit for test runs.

Secrets and machine-specific settings should use environment variables or a local ignored config file, not committed code.

## Import Behavior

V1 imports directly into the live `vocabulary_items` table in Postgres through SQLAlchemy and existing backend model/service conventions. It does not require the FastAPI app to be running. There is no human review gate or staging database table in v1; the LLM result is considered ready to import after deterministic validation.

The import command must support a dry-run mode that validates the artifact, checks duplicates, and reports `would_import`, `duplicate_skips`, and `invalid_rows` without changing the database.

The import artifact should remain compatible with a future API-based importer by keeping accepted `vocabulary` payloads aligned with the current vocabulary API schema.

## Testing and Verification

Implementation should include tests for:

- TSV parser handling the four-column sentence-pair format.
- Parser handling malformed rows without dropping valid rows.
- Normalization grouping repeated lemma occurrences into one candidate.
- Example accumulation across repeated lemma occurrences.
- Enrichment client parsing valid LM Studio structured output.
- Structured output schema rejecting contradictory accepted/rejected shapes.
- Deterministic validation accepting valid rows.
- Deterministic validation rejecting malformed rows.
- Structurally invalid batch candidates being retried individually once.
- Import artifact validation preventing rows that cannot fit `vocabulary_items`.
- Server import skipping obvious duplicates when rerunning the same artifact.
- Import dry-run reporting would-be inserts without writing rows.

Manual verification should include a small sample run, such as the first 10 or 100 candidates, before running the full file through LM Studio.

## Operational Notes

Every run should produce a clear output directory with stage artifacts and summaries.

The CLI should support a sample or limit option so local LLM behavior can be tested cheaply before a large run.

The import report should include counts for:

- parsed rows.
- parse errors.
- unique candidates.
- accepted LLM outputs.
- rejected LLM outputs.
- invalid outputs.
- duplicate skips.
- would-import rows for dry runs.
- imported rows.

## Deferred Improvements

Potential follow-up work:

- Add a verifier stage using two smaller models after enrichment.
- Add a human review UI.
- Add backend upload/import endpoints.
- Add local API push to the deployed FastAPI app.
- Add a live `lemma` column and backfill from artifact metadata.
- Add richer provenance tables for source sentences and import runs.
- Add update candidates for existing live words.
