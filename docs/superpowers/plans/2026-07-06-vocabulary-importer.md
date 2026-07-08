# Vocabulary Importer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working v1 CLI importer that turns Russian-Serbian sentence-pair TSV data into live Slovnik `vocabulary_items` rows through a portable, validated `import-ready.jsonl` artifact.

**Architecture:** Add a bounded `backend/app/importer/` package with local-only normalization/enrichment stages and a lightweight server import stage. The artifact contract is the boundary: CLASSLA and LM Studio are required only before `import-ready.jsonl`; `import-artifact` must work with database access only. Structured LM Studio output is the first defense, while deterministic validation enforces the app contract before anything reaches the live DB.

**Tech Stack:** Python 3.12, Pydantic v2, SQLAlchemy, pytest, optional CLASSLA, httpx, LM Studio OpenAI-compatible `/v1/chat/completions`, JSONL artifacts, existing Slovnik backend models/services.

---

## Source Documents

- Design spec: `docs/superpowers/specs/2026-07-06-vocabulary-importer-design.md`
- Product audit: `docs/product-state.md`
- Setup and verification: `README.md`
- Existing DB model: `backend/app/models.py`
- Existing API schema: `backend/app/schemas.py`
- Existing vocabulary service: `backend/app/services/vocabulary_service.py`

## Scope Check

The agreed v1 is intentionally pragmatic:

- Vocabulary unit: useful learning vocabulary, not every mechanical lemma.
- No human review gate.
- LLM decisions are trusted semantically after deterministic structural/app validation.
- Duplicate live vocabulary rows are skipped.
- Import writes directly into the live `vocabulary_items` table.
- `--dry-run` is required for import validation without DB writes.
- Success means a working end-to-end path; quality refinements are deferred.

Do not implement verifier models, review UI, backend upload endpoints, API push, a live `lemma` migration, update-in-place behavior for existing vocabulary, or provenance DB tables in v1.

## File Structure

Create a focused importer package inside the backend:

```text
backend/app/importer/
├── __init__.py
├── artifacts.py
├── classla_normalizer.py
├── cli.py
├── config.py
├── enrich.py
├── ids.py
├── import_service.py
├── lm_studio.py
├── normalize.py
├── schemas.py
├── transliteration.py
├── tsv.py
└── validation.py
```

Responsibilities:

- `schemas.py`: artifact contracts, controlled enums, accepted/rejected LLM result models, reports.
- `artifacts.py`: JSON/JSONL read-write helpers, including `TypeAdapter` support for union models.
- `tsv.py`: four-column sentence-pair TSV parser.
- `ids.py`: stable candidate id generation.
- `normalize.py`: pure normalization orchestration through a small protocol; no direct CLASSLA import.
- `classla_normalizer.py`: lazy CLASSLA adapter for local runs.
- `transliteration.py`: Serbian Cyrillic/Latin normalization and equivalence helpers.
- `validation.py`: deterministic checks for LLM output and import-ready rows.
- `lm_studio.py`: OpenAI-compatible LM Studio client using structured output schema.
- `enrich.py`: batch enrichment, app validation, one repair retry, artifact assembly.
- `import_service.py`: dry-run/live DB import, duplicate skip reporting.
- `config.py`: CLI config dataclasses or Pydantic settings.
- `cli.py`: argparse entrypoint for `normalize`, `enrich`, `import-artifact`, `run-local`, `run-all`.

Tests live under:

```text
backend/tests/importer/
├── test_artifacts.py
├── test_cli.py
├── test_enrich.py
├── test_ids.py
├── test_import_service.py
├── test_lm_studio.py
├── test_normalize.py
├── test_transliteration.py
├── test_tsv.py
└── test_validation.py
```

Documentation changes after implementation:

- Modify `README.md` with importer install, local LM Studio setup, commands, and dry-run flow.
- Modify `docs/product-state.md` because product behavior/setup/deferred scope changes once importer code exists.

Dependency approach:

- Keep the base server install light.
- Add optional extra `importer-local` in `backend/pyproject.toml` for `classla` and `httpx`.
- Tests must mock CLASSLA and LM Studio. Test runs must not require model downloads.

---

### Task 1: Importer Schemas and Artifact IO

**Files:**
- Create: `backend/app/importer/__init__.py`
- Create: `backend/app/importer/schemas.py`
- Create: `backend/app/importer/artifacts.py`
- Test: `backend/tests/importer/test_artifacts.py`
- Test: `backend/tests/importer/test_validation.py`

- [ ] **Step 1: Write failing schema/artifact tests**

Create tests proving:

- JSONL round-trips Pydantic models and ends with a newline.
- JSON writer creates parent directories.
- `Theme` allows only the controlled enum.
- `AcceptedEnrichment` cannot include `rejection_reason`.
- `RejectedEnrichment` cannot include populated `vocabulary`.
- `not_useful_learning_vocabulary` is a valid rejection reason.
- `invalid_output` is not a valid rejection reason.

Example assertions:

```python
import pytest
from pydantic import ValidationError

from app.importer.schemas import (
    AcceptedEnrichment,
    EnrichmentMetadata,
    RejectedEnrichment,
    RejectionReason,
    Theme,
    VocabularyPayload,
)


def valid_payload() -> VocabularyPayload:
    return VocabularyPayload(
        serbian_cyrillic="радити",
        serbian_latin="raditi",
        russian_translation="делать, работать",
        cefr_level="A1",
        theme="daily-life",
    )


def test_theme_is_controlled_enum():
    assert Theme("daily-life") == "daily-life"
    with pytest.raises(ValueError):
        Theme("free-form")


def test_invalid_output_is_not_a_rejection_reason():
    with pytest.raises(ValueError):
        RejectionReason("invalid_output")


def test_rejected_result_cannot_carry_vocabulary():
    with pytest.raises(ValidationError):
        RejectedEnrichment(
            candidate_id="sha256:x",
            status="rejected",
            vocabulary=valid_payload(),
            rejection_reason="proper_name",
        )


def test_accepted_result_requires_vocabulary_and_no_rejection_reason():
    result = AcceptedEnrichment(
        candidate_id="sha256:x",
        status="accepted",
        vocabulary=valid_payload(),
        metadata=EnrichmentMetadata(lemma="радити", pos="VERB", confidence=0.9, selected_example_count=0),
        rejection_reason=None,
    )
    assert result.vocabulary.theme == "daily-life"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_artifacts.py tests/importer/test_validation.py -v
```

Expected: FAIL because importer modules do not exist.

- [ ] **Step 3: Implement schema constants and models**

Create `backend/app/importer/__init__.py`:

```python
"""Vocabulary importer utilities."""
```

Create `backend/app/importer/schemas.py` with these contract decisions:

```python
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class CEFRLevel(StrEnum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class Theme(StrEnum):
    greetings = "greetings"
    personal_info = "personal-info"
    family_relationships = "family-relationships"
    home = "home"
    daily_life = "daily-life"
    food_drink = "food-drink"
    shopping_money = "shopping-money"
    travel_transport = "travel-transport"
    places_directions = "places-directions"
    health_body = "health-body"
    education = "education"
    work = "work"
    free_time = "free-time"
    nature_weather = "nature-weather"
    services = "services"
    language_communication = "language-communication"
    technology_media = "technology-media"
    emotions_qualities = "emotions-qualities"
    time_numbers = "time-numbers"
    grammar_functions = "grammar-functions"
    other = "other"


class RejectionReason(StrEnum):
    not_serbian = "not_serbian"
    punctuation = "punctuation"
    proper_name = "proper_name"
    too_ambiguous = "too_ambiguous"
    bad_source = "bad_source"
    not_useful_learning_vocabulary = "not_useful_learning_vocabulary"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SentencePair(StrictModel):
    ru_sentence_id: str
    ru: str
    sr_sentence_id: str
    sr: str


class ParseError(StrictModel):
    line_number: int
    reason: str
    raw_line: str


class CandidateExample(StrictModel):
    source: str
    ru_sentence_id: str
    sr_sentence_id: str
    ru: str
    sr: str


class NormalizedCandidate(StrictModel):
    candidate_id: str
    lemma: str
    pos: str | None = None
    forms_seen: list[str] = Field(default_factory=list)
    examples: list[CandidateExample] = Field(default_factory=list)


class VocabularyPayload(StrictModel):
    serbian_cyrillic: str = Field(min_length=1, max_length=160)
    serbian_latin: str = Field(min_length=1, max_length=160)
    russian_translation: str = Field(min_length=1, max_length=240)
    cefr_level: CEFRLevel
    theme: Theme
    usage_register: str | None = Field(default=None, max_length=80)
    stress_marker: str | None = Field(default=None, max_length=160)
    meaning_notes: str | None = None
    example_sentences: str | None = None
    example_translations: str | None = None


class EnrichmentMetadata(StrictModel):
    lemma: str
    pos: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    selected_example_count: int = Field(default=0, ge=0, le=3)


class AcceptedEnrichment(StrictModel):
    candidate_id: str
    status: Literal["accepted"]
    vocabulary: VocabularyPayload
    metadata: EnrichmentMetadata
    rejection_reason: None = None
    note: None = None


class RejectedEnrichment(StrictModel):
    candidate_id: str
    status: Literal["rejected"]
    vocabulary: None = None
    metadata: EnrichmentMetadata | None = None
    rejection_reason: RejectionReason
    note: str | None = None


EnrichedCandidate = Annotated[AcceptedEnrichment | RejectedEnrichment, Field(discriminator="status")]


class EnrichmentBatch(StrictModel):
    results: list[EnrichedCandidate]


class InvalidLLMOutput(StrictModel):
    candidate_id: str
    lemma: str
    errors: list[str] = Field(default_factory=list)
    raw_output: dict | str | None = None


class DuplicateSkip(StrictModel):
    candidate_id: str
    reason: str
    existing_word_id: int | None = None
    serbian_cyrillic: str
    serbian_latin: str


class ImportReport(StrictModel):
    parsed_rows: int = 0
    parse_errors: int = 0
    unique_candidates: int = 0
    accepted_llm_outputs: int = 0
    rejected_llm_outputs: int = 0
    invalid_outputs: int = 0
    duplicate_skips: int = 0
    invalid_rows: int = 0
    would_import: int = 0
    imported_rows: int = 0
    dry_run: bool = False
```

- [ ] **Step 4: Implement artifact helpers**

Use `TypeAdapter` so JSONL can read both concrete models and `EnrichedCandidate` union rows:

```python
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, TypeAdapter

ModelT = TypeVar("ModelT")


def write_jsonl(path: Path, rows: Iterable[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(row.model_dump_json(exclude_none=False))
            file.write("\n")


def read_jsonl(path: Path, model: Any) -> Iterator[ModelT]:
    adapter = TypeAdapter(model)
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield adapter.validate_json(stripped)
            except ValueError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL row") from exc


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
```

- [ ] **Step 5: Run focused tests and lint**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_artifacts.py tests/importer/test_validation.py -v
.venv/bin/ruff check app/importer tests/importer
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/importer backend/tests/importer
git commit -m "feat: add importer artifact contract"
```

---

### Task 2: TSV Parser, Candidate IDs, and Pure Normalization

**Files:**
- Create: `backend/app/importer/tsv.py`
- Create: `backend/app/importer/ids.py`
- Create: `backend/app/importer/normalize.py`
- Test: `backend/tests/importer/test_tsv.py`
- Test: `backend/tests/importer/test_ids.py`
- Test: `backend/tests/importer/test_normalize.py`

- [ ] **Step 1: Write failing TSV parser tests**

Cover:

- UTF-8 BOM and CRLF are accepted.
- Exactly four tab-separated columns are required.
- Empty fields are rejected into `ParseError`.
- Non-numeric sentence ids are rejected.
- Bad rows do not drop later valid rows.

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_tsv.py -v
```

Expected: FAIL.

- [ ] **Step 2: Implement `parse_sentence_pairs`**

Implementation shape:

```python
from pathlib import Path

from pydantic import BaseModel, Field

from app.importer.schemas import ParseError, SentencePair


class ParseResult(BaseModel):
    pairs: list[SentencePair] = Field(default_factory=list)
    errors: list[ParseError] = Field(default_factory=list)


def parse_sentence_pairs(path: Path) -> ParseResult:
    result = ParseResult()
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for line_number, raw_line in enumerate(file, 1):
            line = raw_line.rstrip("\n").removesuffix("\r")
            fields = line.split("\t")
            if len(fields) != 4:
                result.errors.append(ParseError(line_number=line_number, reason="expected 4 tab-separated columns", raw_line=raw_line))
                continue
            ru_id, ru, sr_id, sr = fields
            if not all(fields):
                result.errors.append(ParseError(line_number=line_number, reason="empty field", raw_line=raw_line))
                continue
            if not ru_id.isdigit() or not sr_id.isdigit():
                result.errors.append(ParseError(line_number=line_number, reason="sentence ids must be numeric", raw_line=raw_line))
                continue
            result.pairs.append(SentencePair(ru_sentence_id=ru_id, ru=ru, sr_sentence_id=sr_id, sr=sr))
    return result
```

- [ ] **Step 3: Write failing candidate id tests**

Cover:

- Same source/lemma/POS/normalized lemma returns same `sha256:` id.
- Case and surrounding whitespace do not change ids.
- POS or source changes ids.
- Full example list is not part of the id.

- [ ] **Step 4: Implement candidate id helper**

Use canonical JSON with sorted keys:

```python
import hashlib
import json


def candidate_id_for(
    *,
    source: str,
    lemma: str,
    pos: str | None,
    normalized_lemma: str | None = None,
    disambiguator: str | None = None,
) -> str:
    payload = {
        "source": source.strip().casefold(),
        "lemma": lemma.strip().casefold(),
        "normalized_lemma": (normalized_lemma or lemma).strip().casefold(),
        "pos": (pos or "").strip().casefold(),
        "disambiguator": (disambiguator or "").strip().casefold(),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

- [ ] **Step 5: Write failing pure normalization tests**

Use a fake normalizer. Cover:

- Repeated lemma occurrences merge into one candidate.
- `forms_seen` is de-duplicated in first-seen order.
- Examples accumulate for every source sentence where the lemma appears.
- Obvious mechanical junk is filtered before LLM: empty lemmas/forms, punctuation-only tokens, pure numbers, technical artifacts.
- Function words and short words are not filtered only because they are short.

- [ ] **Step 6: Implement `normalize.py`**

Use a protocol and a simple token model:

```python
from dataclasses import dataclass
from typing import Protocol

from app.importer.ids import candidate_id_for
from app.importer.schemas import CandidateExample, NormalizedCandidate, SentencePair


@dataclass(frozen=True)
class NormalizedToken:
    lemma: str
    form: str
    pos: str | None = None
    normalized_lemma: str | None = None


class Normalizer(Protocol):
    def normalize(self, text: str) -> list[NormalizedToken]:
        ...


def is_obvious_junk(token: NormalizedToken) -> bool:
    lemma = token.lemma.strip()
    form = token.form.strip()
    if not lemma or not form:
        return True
    if all(not char.isalnum() for char in lemma):
        return True
    if lemma.isdigit():
        return True
    return False
```

`build_candidates()` should group by `(candidate_id, lemma, pos)`, not by raw surface form.

- [ ] **Step 7: Run focused tests and lint**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_tsv.py tests/importer/test_ids.py tests/importer/test_normalize.py -v
.venv/bin/ruff check app/importer tests/importer
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/importer backend/tests/importer
git commit -m "feat: normalize TSV vocabulary candidates"
```

---

### Task 3: Transliteration and CLASSLA Adapter

**Files:**
- Create: `backend/app/importer/transliteration.py`
- Create: `backend/app/importer/classla_normalizer.py`
- Modify: `backend/pyproject.toml`
- Test: `backend/tests/importer/test_transliteration.py`

- [ ] **Step 1: Write failing transliteration tests**

Cover:

- Common Serbian Cyrillic to Latin pairs: `ђ`, `љ`, `њ`, `ћ`, `џ`, `ш`, `ж`, `ч`.
- Case-insensitive normalization for duplicate checks.
- `equivalent_serbian_headword("радити", "raditi")` is true.
- Obvious mismatches are false.

- [ ] **Step 2: Implement transliteration helpers**

Keep this intentionally small. It is for deterministic checks and duplicate matching, not full linguistic analysis.

- [ ] **Step 3: Add optional local dependencies**

Modify `backend/pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
  "httpx>=0.27",
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "ruff>=0.6",
]
importer-local = [
  "classla>=2.1",
  "httpx>=0.27",
]
```

- [ ] **Step 4: Implement lazy CLASSLA adapter**

`classla_normalizer.py` must import CLASSLA inside initialization/use, not at module import time. Server import should be able to import `app.importer.import_service` without CLASSLA installed.

Implementation expectations:

- Constructor accepts language/config options with Serbian default.
- `normalize(text)` returns `NormalizedToken` objects.
- If CLASSLA is missing, raise a clear runtime error explaining to install `.[importer-local]`.
- Keep tests mocked; do not download models in tests.

- [ ] **Step 5: Run checks**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_transliteration.py -v
.venv/bin/ruff check app/importer tests/importer
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/app/importer backend/tests/importer
git commit -m "feat: add Serbian importer normalization adapters"
```

---

### Task 4: Deterministic Validation

**Files:**
- Create: `backend/app/importer/validation.py`
- Test: `backend/tests/importer/test_validation.py`

- [ ] **Step 1: Extend failing validation tests**

Cover:

- Accepted rows require `vocabulary`, `metadata`, null `rejection_reason`, null `note`.
- Rejected rows require `rejection_reason`, null `vocabulary`, optional `metadata`, optional short `note`.
- Unknown `candidate_id` fails.
- Missing result for requested `candidate_id` fails.
- Duplicate result for a candidate fails.
- Theme outside enum fails.
- CEFR outside enum fails.
- Example sentence and translation line counts must match.
- `selected_example_count` must equal the number of live example lines when examples are present and must be no more than 3.
- `import-ready` rows must be accepted only.
- Structural validation failures are represented as app errors, not as LLM rejection reasons.

- [ ] **Step 2: Implement validation helpers**

Create functions with small return objects:

```python
from pydantic import BaseModel, Field

from app.importer.schemas import AcceptedEnrichment, EnrichedCandidate, NormalizedCandidate


class CandidateValidationResult(BaseModel):
    valid: list[EnrichedCandidate] = Field(default_factory=list)
    invalid: dict[str, list[str]] = Field(default_factory=dict)


def validate_batch_results(
    requested: list[NormalizedCandidate],
    results: list[EnrichedCandidate],
) -> CandidateValidationResult:
    ...


def validate_import_ready_row(row: EnrichedCandidate) -> list[str]:
    ...
```

Validation is mechanical only. Do not judge translation quality or whether CEFR/theme choices are semantically correct.

- [ ] **Step 3: Run validation tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_validation.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/importer/validation.py backend/tests/importer/test_validation.py
git commit -m "feat: validate importer enrichment contract"
```

---

### Task 5: LM Studio Structured Output Client

**Files:**
- Create: `backend/app/importer/lm_studio.py`
- Test: `backend/tests/importer/test_lm_studio.py`

- [ ] **Step 1: Write failing LM Studio client tests**

Mock `httpx.Client.post` and cover:

- Request is sent to `/chat/completions` under the configured base URL.
- Request includes `response_format.type = "json_schema"`.
- JSON schema has an envelope with `results`.
- Schema uses mutually exclusive accepted/rejected result shapes.
- Schema includes enum values for `status`, `rejection_reason`, `cefr_level`, and `theme`.
- Parsed content comes from `choices[0].message.content`.
- Malformed response raises a clear client error.

- [ ] **Step 2: Implement structured output schema builder**

The schema must encode the agreed contract. Use `oneOf` or equivalent JSON Schema:

```python
def build_enrichment_json_schema() -> dict:
    return {
        "name": "slovnik_vocabulary_enrichment",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["results"],
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "oneOf": [
                            accepted_result_schema(),
                            rejected_result_schema(),
                        ]
                    },
                }
            },
        },
    }
```

The accepted result schema must require populated `vocabulary` and `metadata`, and must constrain `rejection_reason` and `note` to null. The rejected result schema must constrain `vocabulary` to null and require `rejection_reason`.

- [ ] **Step 3: Implement prompt builder**

Prompt requirements:

- Explain that a vocabulary unit is useful learning vocabulary.
- Say ambiguous/function/short words may be accepted if useful.
- Say rejected candidates must use only the controlled rejection reasons.
- Include CEFR heuristic guidance from the spec.
- Include the full theme enum and tell the model to use `other` only when no specific theme fits.
- Ask for up to 3 best examples for accepted rows, serialized as newline-separated `example_sentences` and `example_translations`.
- Tell the model to align each result by `candidate_id`.

- [ ] **Step 4: Implement client**

Implementation outline:

```python
class LMStudioClient:
    def __init__(self, *, base_url: str, model: str, temperature: float = 0.1, timeout: float = 120) -> None:
        ...

    def enrich_batch(self, candidates: list[NormalizedCandidate]) -> EnrichmentBatch:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": build_messages(candidates),
            "response_format": {
                "type": "json_schema",
                "json_schema": build_enrichment_json_schema(),
            },
        }
        ...
```

Default base URL: `http://localhost:1234/v1`.

- [ ] **Step 5: Run LM Studio tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_lm_studio.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/importer/lm_studio.py backend/tests/importer/test_lm_studio.py
git commit -m "feat: call LM Studio with structured importer schema"
```

---

### Task 6: Enrichment Orchestration and Artifacts

**Files:**
- Create: `backend/app/importer/enrich.py`
- Test: `backend/tests/importer/test_enrich.py`

- [ ] **Step 1: Write failing enrichment tests**

Use fake clients. Cover:

- Valid accepted LLM rows are written to `llm-enriched.jsonl` and `import-ready.jsonl`.
- Valid rejected LLM rows are written to `llm-enriched.jsonl` and `rejected-candidates.jsonl`, not `import-ready.jsonl`.
- Contradictory LLM rows are treated as invalid structural output.
- Invalid batch candidates are retried individually once by default.
- Retry prompt receives the validation errors.
- Candidates still invalid after retry go to `invalid-llm-output.jsonl`.
- Valid rows from a partially invalid batch are kept.
- `import-ready.jsonl` contains only valid accepted rows.
- `run-summary.json` includes accepted, rejected, invalid, and retry counts.

- [ ] **Step 2: Implement result container**

Use explicit buckets:

```python
class EnrichmentRunResult(BaseModel):
    llm_enriched: list[EnrichedCandidate] = Field(default_factory=list)
    import_ready: list[AcceptedEnrichment] = Field(default_factory=list)
    rejected: list[RejectedEnrichment] = Field(default_factory=list)
    invalid: list[InvalidLLMOutput] = Field(default_factory=list)
    retries_attempted: int = 0
```

- [ ] **Step 3: Implement orchestration**

Rules:

- Batch size is configurable.
- Max concurrency defaults to 1.
- Repair retry count defaults to 1.
- Retry only structural/schema/app-contract failures.
- Do not retry semantic disagreements with a valid accepted or rejected row.
- Do not convert invalid structural outputs into `status = rejected`.
- `invalid-llm-output.jsonl` is the destination for persistent structural failures.
- `import-ready.jsonl` is only for valid accepted rows ready for server import.

- [ ] **Step 4: Write artifacts**

`write_enrichment_outputs(output_dir, result)` writes:

- `llm-enriched.jsonl`
- `import-ready.jsonl`
- `rejected-candidates.jsonl`
- `invalid-llm-output.jsonl`
- `run-summary.json`

Empty files may be omitted except `import-ready.jsonl` and `run-summary.json`, which should always be produced.

- [ ] **Step 5: Run enrichment tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_enrich.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/importer/enrich.py backend/tests/importer/test_enrich.py
git commit -m "feat: enrich vocabulary candidates with retryable validation"
```

---

### Task 7: Database Import Service With Dry Run

**Files:**
- Create: `backend/app/importer/import_service.py`
- Test: `backend/tests/importer/test_import_service.py`

- [ ] **Step 1: Write failing import tests**

Use existing backend SQLAlchemy test fixtures/patterns. Cover:

- Accepted import-ready row inserts one `VocabularyItem`.
- `--dry-run` reports `would_import` but inserts no row.
- Rerunning the same artifact skips duplicates.
- Duplicates are matched by normalized Serbian Cyrillic/Latin headwords.
- Duplicate skips are counted and returned with existing word id when available.
- Import command writes `duplicate-skips.jsonl` when duplicates are found.
- Import command always writes `import-report.json`.
- Invalid rows are counted as `invalid_rows` and not inserted.
- Rejected rows are invalid for `import-ready.jsonl`.
- Example sentence and translation line counts are checked again at import time.

- [ ] **Step 2: Implement duplicate matching**

Best-effort v1 logic:

- Normalize whitespace and case.
- Compare existing `serbian_cyrillic` and `serbian_latin`.
- Use transliteration helper where practical to catch Cyrillic/Latin equivalence.
- Do not add a DB constraint or migration in v1.

- [ ] **Step 3: Implement import function**

Expected shape:

```python
def import_artifact_rows(
    db: Session,
    rows: list[EnrichedCandidate],
    *,
    dry_run: bool = False,
) -> tuple[ImportReport, list[DuplicateSkip]]:
    ...
```

Rules:

- Validate every row with `validate_import_ready_row`.
- Skip duplicates and append `DuplicateSkip`.
- If `dry_run` is true, increment `would_import` and do not call `db.add()`/`commit()`.
- If live import, create `VocabularyCreate` from the row payload and call existing service conventions or add `VocabularyItem` consistently with current code.
- Commit once per import run or in small chunks; tests should not require per-row commits.

- [ ] **Step 4: Implement import artifact file wrapper**

Add a wrapper used by the CLI:

```python
def import_artifact_file(
    db: Session,
    *,
    input_path: Path,
    output_dir: Path,
    dry_run: bool = False,
) -> ImportReport:
    ...
```

It must read `import-ready.jsonl`, call `import_artifact_rows`, write `import-report.json`,
and write `duplicate-skips.jsonl` when duplicates are skipped.

- [ ] **Step 5: Run import tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_import_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/importer/import_service.py backend/tests/importer/test_import_service.py
git commit -m "feat: import vocabulary artifacts into the database"
```

---

### Task 8: CLI Commands

**Files:**
- Create: `backend/app/importer/config.py`
- Create: `backend/app/importer/cli.py`
- Test: `backend/tests/importer/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Cover command parsing and orchestration with mocks:

- `normalize --input pairs.tsv --output-dir out` writes normalized candidates and parse errors.
- `enrich --input out/normalized-candidates.jsonl --output-dir out --model google/gemma-4-26b-a4b-qat` calls LM Studio client.
- `import-artifact --input out/import-ready.jsonl --output-dir out --dry-run` calls import service with `dry_run=True`.
- `run-local` runs normalize then enrich only.
- `run-all` runs normalize, enrich, then import-artifact.
- Local commands accept `--limit` for cheap sample runs.

- [ ] **Step 2: Implement CLI**

Commands:

```text
python -m app.importer.cli normalize --input source.tsv --output-dir import-run --source tatoeba
python -m app.importer.cli enrich --input import-run/normalized-candidates.jsonl --output-dir import-run --model google/gemma-4-26b-a4b-qat
python -m app.importer.cli import-artifact --input import-run/import-ready.jsonl --output-dir import-run --dry-run
python -m app.importer.cli run-local --input source.tsv --output-dir import-run --model google/gemma-4-26b-a4b-qat --limit 100
python -m app.importer.cli run-all --input source.tsv --output-dir import-run --model google/gemma-4-26b-a4b-qat --dry-run
```

Key options:

- `--base-url`, default `http://localhost:1234/v1`
- `--model`
- `--temperature`, default low
- `--batch-size`
- `--timeout`
- `--retries`, default `1`
- `--max-concurrency`, default `1`
- `--limit`
- `--dry-run` for `import-artifact` and `run-all`

- [ ] **Step 3: Ensure server import path has no local-only imports**

Add a test that imports `app.importer.import_service` without importing `classla_normalizer` or `lm_studio`.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/importer/config.py backend/app/importer/cli.py backend/tests/importer/test_cli.py
git commit -m "feat: add vocabulary importer CLI"
```

---

### Task 9: Documentation and Product Audit

**Files:**
- Modify: `README.md`
- Modify: `docs/product-state.md`

- [ ] **Step 1: Update README importer section**

Document:

- Optional local install:

```bash
cd backend
.venv/bin/python -m pip install -e ".[dev,importer-local]"
```

- LM Studio expectation:
  - OpenAI-compatible server at `http://localhost:1234/v1`.
  - Tested model family during spec work: `google/gemma-4-26b-a4b-qat`.
  - Structured output uses `response_format.type = json_schema`.

- Safe sample run:

```bash
cd backend
.venv/bin/python -m app.importer.cli run-local \
  --input /path/to/pairs.tsv \
  --output-dir /path/to/import-run \
  --model google/gemma-4-26b-a4b-qat \
  --limit 100
```

- Dry-run import:

```bash
cd backend
.venv/bin/python -m app.importer.cli import-artifact \
  --input /path/to/import-run/import-ready.jsonl \
  --output-dir /path/to/import-run \
  --dry-run
```

- Live import warning:

```bash
cd backend
.venv/bin/python -m app.importer.cli import-artifact \
  --input /path/to/import-run/import-ready.jsonl \
  --output-dir /path/to/import-run
```

- Artifact meanings:
  - `normalized-candidates.jsonl`
  - `llm-enriched.jsonl`
  - `import-ready.jsonl`
  - `rejected-candidates.jsonl`
  - `invalid-llm-output.jsonl`
  - `duplicate-skips.jsonl`
  - `import-report.json`
  - `run-summary.json`

- [ ] **Step 2: Update product state**

Update durable facts only:

- Importer exists as a backend CLI, not a web UI.
- Local enrichment requires optional CLASSLA/LM Studio dependencies.
- Server import reads `import-ready.jsonl` and writes directly to `vocabulary_items`.
- Dry-run mode exists.
- No human review gate, verifier model, upload endpoint, source provenance tables, or live lemma column in v1.
- Add importer tests/verification commands.

- [ ] **Step 3: Run docs sanity check**

Run:

```bash
git diff --check
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/product-state.md
git commit -m "docs: document vocabulary importer workflow"
```

---

### Task 10: End-to-End Verification

**Files:**
- No new source files expected.
- May create temporary files under `/tmp` or pytest `tmp_path`; do not commit generated import artifacts.

- [ ] **Step 1: Run importer test suite**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer -v
```

Expected: PASS.

- [ ] **Step 2: Run full backend checks**

Run:

```bash
cd backend
.venv/bin/ruff check .
.venv/bin/pytest -v
```

Expected: PASS.

- [ ] **Step 3: Run a tiny normalize-only smoke test when local importer deps are installed**

If CLASSLA and its Serbian model are available locally, create a temporary TSV with two rows and run:

```bash
cd backend
.venv/bin/python -m app.importer.cli normalize \
  --input /tmp/slovnik-import-smoke.tsv \
  --output-dir /tmp/slovnik-import-smoke \
  --source smoke \
  --limit 2
```

Expected:

- `normalized-candidates.jsonl` exists.
- `parse-errors.jsonl` is empty or absent for valid input.
- `run-summary.json` exists.

If CLASSLA is not available in the execution environment, document that this optional smoke check was skipped and rely on mocked importer tests plus the import dry-run smoke test below.

- [ ] **Step 4: Run import dry-run smoke test**

Use a tiny hand-written `import-ready.jsonl` with one accepted row and run against a local dev/test database:

```bash
cd backend
.venv/bin/python -m app.importer.cli import-artifact \
  --input /tmp/slovnik-import-smoke/import-ready.jsonl \
  --output-dir /tmp/slovnik-import-smoke \
  --dry-run
```

Expected:

- `import-report.json` has `dry_run: true`.
- `would_import` is 1 for a new word.
- No new DB row is inserted.

- [ ] **Step 5: Optional LM Studio smoke test**

Only run when LM Studio is available locally:

```bash
cd backend
.venv/bin/python -m app.importer.cli enrich \
  --input /tmp/slovnik-import-smoke/normalized-candidates.jsonl \
  --output-dir /tmp/slovnik-import-smoke \
  --model google/gemma-4-26b-a4b-qat \
  --batch-size 1 \
  --limit 1
```

Expected:

- `llm-enriched.jsonl` exists.
- `import-ready.jsonl` contains only accepted valid rows.
- `rejected-candidates.jsonl` contains valid LLM rejections, if any.
- `invalid-llm-output.jsonl` contains only persistent structural failures after retry, if any.

- [ ] **Step 6: Final git and diff checks**

Run:

```bash
git status --short
git diff --check
```

Expected:

- Only intentional importer/docs files are modified.
- `git diff --check` passes.

- [ ] **Step 7: Final commit**

If tasks were not already committed individually, commit the full implementation:

```bash
git add backend/app/importer backend/tests/importer backend/pyproject.toml README.md docs/product-state.md
git commit -m "feat: add vocabulary importer"
```

---

## Manual Acceptance Criteria

- A developer can run local normalization/enrichment without touching the production DB.
- `import-ready.jsonl` contains only rows ready to import.
- Rejected candidates and structurally invalid LLM outputs are separated.
- Import dry-run reports `would_import`, `duplicate_skips`, and `invalid_rows` without writing.
- Live import skips obvious duplicates and writes accepted rows to `vocabulary_items`.
- Server import does not require CLASSLA, LM Studio, or the original TSV.

## Deferred Improvements

- Verifier-model stage.
- Human review UI.
- Backend upload/import endpoint.
- API push to deployed FastAPI.
- Live `lemma` column and backfill.
- Rich source/provenance tables.
- Updating existing live vocabulary rows with improved examples/translations.
