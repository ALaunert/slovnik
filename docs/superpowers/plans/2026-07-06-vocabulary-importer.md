# Vocabulary Importer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI-based importer that processes Russian-Serbian sentence-pair TSV files locally with CLASSLA and LM Studio, then imports a portable artifact into Slovnik's database on the server.

**Architecture:** Add a focused `backend/app/importer/` package with pure parsing, artifact, validation, enrichment, and DB-import modules. Keep CLASSLA and LM Studio dependencies out of the server import path by making local-only integrations optional and lazily imported. Expose resumable CLI subcommands for `normalize`, `enrich`, `import-artifact`, `run-local`, and `run-all`.

**Tech Stack:** Python 3.12, Pydantic, SQLAlchemy, pytest, httpx for LM Studio, optional CLASSLA for local normalization, existing FastAPI backend models/services, JSONL artifacts.

---

## Source Documents

- Design spec: `docs/superpowers/specs/2026-07-06-vocabulary-importer-design.md`
- Product audit: `docs/product-state.md`
- README setup and verification commands: `README.md`
- Existing vocabulary model/API: `backend/app/models.py`, `backend/app/schemas.py`, `backend/app/services/vocabulary_service.py`

## Scope Check

The approved spec covers one cohesive importer workflow with two runtime environments:

- Local enrichment: TSV parsing, CLASSLA normalization, LM Studio enrichment, artifact writing.
- Server import: artifact validation and DB insertion without CLASSLA or LM Studio.

These are coupled by the portable artifact contract, so they can be implemented in one plan as a sequence of independently testable modules. Do not build the deferred verifier-model stage, helper UI, backend upload endpoint, API push, live `lemma` migration, or existing-word update workflow.

## File Structure

Create a new importer package under the backend. Keep modules small and safe to import in a base server environment.

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

- `schemas.py`: Pydantic models and constants for candidate, enrichment, rejection, import report, and vocabulary payload artifacts.
- `artifacts.py`: JSONL read/write helpers and summary JSON writer.
- `tsv.py`: Tatoeba-style TSV parser only.
- `ids.py`: stable SHA-style candidate id generation.
- `normalize.py`: pure normalization orchestration against a small normalizer protocol; no direct CLASSLA import.
- `classla_normalizer.py`: CLASSLA-backed normalizer adapter with lazy `import classla`.
- `transliteration.py`: Serbian Cyrillic/Latin conversion helpers and simple equivalence checks.
- `validation.py`: deterministic validation for LLM output and import-ready artifacts.
- `lm_studio.py`: OpenAI-compatible LM Studio HTTP client.
- `enrich.py`: batch enrichment, validation, per-candidate retry, output artifact assembly.
- `import_service.py`: direct DB import from `import-ready.jsonl`.
- `config.py`: CLI/environment config models.
- `cli.py`: argparse entrypoint for all commands.

Tests:

```text
backend/tests/importer/
├── test_artifacts.py
├── test_cli.py
├── test_enrich.py
├── test_ids.py
├── test_import_service.py
├── test_normalize.py
├── test_transliteration.py
├── test_tsv.py
└── test_validation.py
```

Documentation:

- Modify `README.md` with importer setup and commands.
- Modify `docs/product-state.md` because product behavior/setup/deferred scope changes.

Dependency approach:

- Keep base server install light.
- Add optional extra `importer-local` for local-only enrichment dependencies:
  - `classla`
  - `httpx`
- Tests may mock CLASSLA and LM Studio, so CI/local test runs should not require model downloads.

---

### Task 1: Importer Package Skeleton, Schemas, and Artifact IO

**Files:**
- Create: `backend/app/importer/__init__.py`
- Create: `backend/app/importer/schemas.py`
- Create: `backend/app/importer/artifacts.py`
- Create: `backend/tests/importer/test_artifacts.py`

- [ ] **Step 1: Create importer test directory**

Run:

```bash
mkdir -p backend/tests/importer
```

- [ ] **Step 2: Write failing artifact tests**

Create `backend/tests/importer/test_artifacts.py`:

```python
import json

from app.importer.artifacts import read_jsonl, write_json, write_jsonl
from app.importer.schemas import CandidateExample, NormalizedCandidate


def test_write_and_read_jsonl_round_trip(tmp_path):
    path = tmp_path / "normalized-candidates.jsonl"
    candidate = NormalizedCandidate(
        candidate_id="sha256:test",
        lemma="raditi",
        pos="VERB",
        forms_seen=["radi"],
        examples=[
            CandidateExample(
                source="unit",
                ru_sentence_id="1",
                sr_sentence_id="2",
                ru="What are you doing?",
                sr="Sta radis?",
            )
        ],
    )

    write_jsonl(path, [candidate])

    rows = list(read_jsonl(path, NormalizedCandidate))
    assert rows == [candidate]
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_write_json_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "run-summary.json"

    write_json(path, {"parsed_rows": 2})

    assert json.loads(path.read_text(encoding="utf-8")) == {"parsed_rows": 2}
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_artifacts.py -v
```

Expected: FAIL because `app.importer` modules do not exist.

- [ ] **Step 4: Add importer schemas**

Create `backend/app/importer/__init__.py`:

```python
"""Vocabulary importer utilities."""
```

Create `backend/app/importer/schemas.py`:

```python
from typing import Literal

from pydantic import BaseModel, Field

CEFRLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
CandidateStatus = Literal["accepted", "rejected"]
RejectionReason = Literal[
    "not_serbian",
    "punctuation",
    "proper_name",
    "too_ambiguous",
    "bad_source",
    "invalid_output",
]


class SentencePair(BaseModel):
    ru_sentence_id: str
    ru: str
    sr_sentence_id: str
    sr: str


class ParseError(BaseModel):
    line_number: int
    reason: str
    raw_line: str


class CandidateExample(BaseModel):
    source: str
    ru_sentence_id: str
    sr_sentence_id: str
    ru: str
    sr: str


class NormalizedCandidate(BaseModel):
    candidate_id: str
    lemma: str
    pos: str | None = None
    forms_seen: list[str] = Field(default_factory=list)
    examples: list[CandidateExample] = Field(default_factory=list)


class VocabularyPayload(BaseModel):
    serbian_cyrillic: str = Field(min_length=1, max_length=160)
    serbian_latin: str = Field(min_length=1, max_length=160)
    russian_translation: str = Field(min_length=1, max_length=240)
    cefr_level: CEFRLevel
    theme: str = Field(min_length=1, max_length=80)
    usage_register: str | None = Field(default=None, max_length=80)
    stress_marker: str | None = Field(default=None, max_length=160)
    meaning_notes: str | None = None
    example_sentences: str | None = None
    example_translations: str | None = None


class EnrichmentMetadata(BaseModel):
    lemma: str
    pos: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    selected_example_count: int = Field(default=0, ge=0)


class EnrichedCandidate(BaseModel):
    candidate_id: str
    status: CandidateStatus
    vocabulary: VocabularyPayload | None = None
    metadata: EnrichmentMetadata | None = None
    rejection_reason: RejectionReason | None = None
    validation_errors: list[str] = Field(default_factory=list)


class ImportReport(BaseModel):
    parsed_rows: int = 0
    parse_errors: int = 0
    unique_candidates: int = 0
    accepted_llm_outputs: int = 0
    rejected_llm_outputs: int = 0
    invalid_outputs: int = 0
    duplicate_skips: int = 0
    imported_rows: int = 0
```

- [ ] **Step 5: Add artifact helpers**

Create `backend/app/importer/artifacts.py`:

```python
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


def write_jsonl(path: Path, rows: Iterable[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(row.model_dump_json(exclude_none=True))
            file.write("\n")


def read_jsonl(path: Path, model: type[ModelT]) -> Iterator[ModelT]:
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield model.model_validate_json(stripped)
            except ValueError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL row") from exc


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
```

- [ ] **Step 6: Run artifact tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_artifacts.py -v
```

Expected: PASS.

- [ ] **Step 7: Run backend lint**

Run:

```bash
cd backend
.venv/bin/ruff check app/importer tests/importer
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/importer backend/tests/importer/test_artifacts.py
git commit -m "feat: add importer artifact schemas"
```

---

### Task 2: TSV Parser

**Files:**
- Create: `backend/app/importer/tsv.py`
- Create: `backend/tests/importer/test_tsv.py`

- [ ] **Step 1: Write failing TSV parser tests**

Create `backend/tests/importer/test_tsv.py`:

```python
from app.importer.tsv import parse_sentence_pairs


def test_parse_sentence_pairs_accepts_four_column_tsv(tmp_path):
    path = tmp_path / "pairs.tsv"
    path.write_text(
        "\ufeff5411\tWhat are you doing?\t2332057\tSta radis?\r\n"
        "5412\tWhat is this?\t468730\tSta je ovo?\r\n",
        encoding="utf-8",
    )

    result = parse_sentence_pairs(path)

    assert len(result.pairs) == 2
    assert result.pairs[0].ru_sentence_id == "5411"
    assert result.pairs[0].ru == "What are you doing?"
    assert result.pairs[0].sr_sentence_id == "2332057"
    assert result.pairs[0].sr == "Sta radis?"
    assert result.errors == []


def test_parse_sentence_pairs_records_bad_rows_and_continues(tmp_path):
    path = tmp_path / "pairs.tsv"
    path.write_text(
        "1\tGood\t2\tDobro\n"
        "bad row\n"
        "3\tAgain\t4\tOpet\n",
        encoding="utf-8",
    )

    result = parse_sentence_pairs(path)

    assert [pair.ru_sentence_id for pair in result.pairs] == ["1", "3"]
    assert len(result.errors) == 1
    assert result.errors[0].line_number == 2
    assert result.errors[0].reason == "expected 4 tab-separated columns"


def test_parse_sentence_pairs_rejects_empty_fields(tmp_path):
    path = tmp_path / "pairs.tsv"
    path.write_text("1\t\t2\tSta radis?\n", encoding="utf-8")

    result = parse_sentence_pairs(path)

    assert result.pairs == []
    assert result.errors[0].reason == "empty field"


def test_parse_sentence_pairs_rejects_non_numeric_ids(tmp_path):
    path = tmp_path / "pairs.tsv"
    path.write_text("x\tWhat?\t2\tSta?\n", encoding="utf-8")

    result = parse_sentence_pairs(path)

    assert result.pairs == []
    assert result.errors[0].reason == "sentence ids must be numeric"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_tsv.py -v
```

Expected: FAIL because `app.importer.tsv` does not exist.

- [ ] **Step 3: Implement TSV parser**

Create `backend/app/importer/tsv.py`:

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
            line = raw_line.rstrip("\n")
            if line.endswith("\r"):
                line = line[:-1]
            if not line:
                result.errors.append(ParseError(line_number=line_number, reason="blank line", raw_line=raw_line))
                continue

            fields = line.split("\t")
            if len(fields) != 4:
                result.errors.append(
                    ParseError(
                        line_number=line_number,
                        reason="expected 4 tab-separated columns",
                        raw_line=raw_line,
                    )
                )
                continue

            ru_sentence_id, ru, sr_sentence_id, sr = fields
            if not all(fields):
                result.errors.append(ParseError(line_number=line_number, reason="empty field", raw_line=raw_line))
                continue
            if not ru_sentence_id.isdigit() or not sr_sentence_id.isdigit():
                result.errors.append(
                    ParseError(
                        line_number=line_number,
                        reason="sentence ids must be numeric",
                        raw_line=raw_line,
                    )
                )
                continue

            result.pairs.append(
                SentencePair(
                    ru_sentence_id=ru_sentence_id,
                    ru=ru,
                    sr_sentence_id=sr_sentence_id,
                    sr=sr,
                )
            )
    return result
```

- [ ] **Step 4: Run TSV parser tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_tsv.py -v
```

Expected: PASS.

- [ ] **Step 5: Run importer tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/importer/tsv.py backend/tests/importer/test_tsv.py
git commit -m "feat: parse sentence pair TSV imports"
```

---

### Task 3: Candidate IDs and Pure Normalization Orchestration

**Files:**
- Create: `backend/app/importer/ids.py`
- Create: `backend/app/importer/normalize.py`
- Create: `backend/tests/importer/test_ids.py`
- Create: `backend/tests/importer/test_normalize.py`

- [ ] **Step 1: Write failing candidate id tests**

Create `backend/tests/importer/test_ids.py`:

```python
from app.importer.ids import candidate_id_for


def test_candidate_id_is_stable_and_sha_prefixed():
    first = candidate_id_for(source="tatoeba", lemma="Raditi", pos="VERB", normalized_lemma="raditi")
    second = candidate_id_for(source="tatoeba", lemma="raditi", pos="VERB", normalized_lemma="raditi")

    assert first == second
    assert first.startswith("sha256:")
    assert len(first) == len("sha256:") + 64


def test_candidate_id_changes_for_pos_or_source():
    verb = candidate_id_for(source="tatoeba", lemma="raditi", pos="VERB", normalized_lemma="raditi")
    noun = candidate_id_for(source="tatoeba", lemma="raditi", pos="NOUN", normalized_lemma="raditi")
    other_source = candidate_id_for(source="manual", lemma="raditi", pos="VERB", normalized_lemma="raditi")

    assert verb != noun
    assert verb != other_source
```

- [ ] **Step 2: Write failing normalization tests**

Create `backend/tests/importer/test_normalize.py`:

```python
from app.importer.normalize import NormalizedToken, build_candidates
from app.importer.schemas import SentencePair


class FakeNormalizer:
    def normalize(self, text: str) -> list[NormalizedToken]:
        if text == "Sta radis?":
            return [NormalizedToken(lemma="sta", form="Sta", pos="PRON"), NormalizedToken(lemma="raditi", form="radis", pos="VERB")]
        if text == "Radim sada.":
            return [NormalizedToken(lemma="raditi", form="Radim", pos="VERB"), NormalizedToken(lemma="sada", form="sada", pos="ADV")]
        return []


def test_build_candidates_groups_by_lemma_and_accumulates_examples():
    pairs = [
        SentencePair(ru_sentence_id="1", ru="What are you doing?", sr_sentence_id="2", sr="Sta radis?"),
        SentencePair(ru_sentence_id="3", ru="I am working now.", sr_sentence_id="4", sr="Radim sada."),
    ]

    candidates = build_candidates(pairs, source="unit", normalizer=FakeNormalizer())

    by_lemma = {candidate.lemma: candidate for candidate in candidates}
    assert sorted(by_lemma) == ["raditi", "sada", "sta"]
    assert by_lemma["raditi"].forms_seen == ["radis", "Radim"]
    assert [example.sr for example in by_lemma["raditi"].examples] == ["Sta radis?", "Radim sada."]


def test_build_candidates_skips_empty_lemmas_and_forms():
    class EmptyNormalizer:
        def normalize(self, text: str) -> list[NormalizedToken]:
            return [NormalizedToken(lemma="", form="?", pos="PUNCT"), NormalizedToken(lemma="raditi", form="", pos="VERB")]

    pairs = [SentencePair(ru_sentence_id="1", ru="What?", sr_sentence_id="2", sr="?")]

    assert build_candidates(pairs, source="unit", normalizer=EmptyNormalizer()) == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_ids.py tests/importer/test_normalize.py -v
```

Expected: FAIL because `ids.py` and `normalize.py` do not exist.

- [ ] **Step 4: Implement candidate id helper**

Create `backend/app/importer/ids.py`:

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
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
```

- [ ] **Step 5: Implement pure normalization orchestration**

Create `backend/app/importer/normalize.py`:

```python
from collections import OrderedDict
from typing import Protocol

from pydantic import BaseModel

from app.importer.ids import candidate_id_for
from app.importer.schemas import CandidateExample, NormalizedCandidate, SentencePair


class NormalizedToken(BaseModel):
    lemma: str
    form: str
    pos: str | None = None
    normalized_lemma: str | None = None


class SerbianNormalizer(Protocol):
    def normalize(self, text: str) -> list[NormalizedToken]:
        """Return lemmatized tokens for a Serbian sentence."""


def build_candidates(
    pairs: list[SentencePair],
    *,
    source: str,
    normalizer: SerbianNormalizer,
) -> list[NormalizedCandidate]:
    candidates: OrderedDict[str, NormalizedCandidate] = OrderedDict()

    for pair in pairs:
        tokens = normalizer.normalize(pair.sr)
        for token in tokens:
            lemma = token.lemma.strip()
            form = token.form.strip()
            if not lemma or not form:
                continue

            candidate_id = candidate_id_for(
                source=source,
                lemma=lemma,
                pos=token.pos,
                normalized_lemma=token.normalized_lemma,
            )
            candidate = candidates.get(candidate_id)
            example = CandidateExample(
                source=source,
                ru_sentence_id=pair.ru_sentence_id,
                sr_sentence_id=pair.sr_sentence_id,
                ru=pair.ru,
                sr=pair.sr,
            )

            if candidate is None:
                candidates[candidate_id] = NormalizedCandidate(
                    candidate_id=candidate_id,
                    lemma=lemma,
                    pos=token.pos,
                    forms_seen=[form],
                    examples=[example],
                )
                continue

            if form not in candidate.forms_seen:
                candidate.forms_seen.append(form)
            if example not in candidate.examples:
                candidate.examples.append(example)

    return list(candidates.values())
```

- [ ] **Step 6: Run id and normalization tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_ids.py tests/importer/test_normalize.py -v
```

Expected: PASS.

- [ ] **Step 7: Run importer tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/importer/ids.py backend/app/importer/normalize.py backend/tests/importer/test_ids.py backend/tests/importer/test_normalize.py
git commit -m "feat: group import candidates by lemma"
```

---

### Task 4: CLASSLA Adapter and Normalize CLI Command

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/importer/classla_normalizer.py`
- Create: `backend/app/importer/config.py`
- Create: `backend/app/importer/cli.py`
- Create: `backend/tests/importer/test_cli.py`

- [ ] **Step 1: Write failing CLI normalize test**

Create `backend/tests/importer/test_cli.py`:

```python
import json

from app.importer.cli import main
from app.importer.normalize import NormalizedToken


class FakeNormalizer:
    def normalize(self, text: str) -> list[NormalizedToken]:
        return [NormalizedToken(lemma="raditi", form="radis", pos="VERB")]


def test_cli_normalize_writes_candidates_and_summary(tmp_path, monkeypatch):
    source = tmp_path / "source.tsv"
    output_dir = tmp_path / "out"
    source.write_text("1\tWhat are you doing?\t2\tSta radis?\n", encoding="utf-8")
    monkeypatch.setattr("app.importer.cli.create_classla_normalizer", lambda: FakeNormalizer())

    exit_code = main([
        "normalize",
        "--input",
        str(source),
        "--output-dir",
        str(output_dir),
        "--source",
        "unit",
    ])

    assert exit_code == 0
    candidate_rows = [
        json.loads(line)
        for line in (output_dir / "normalized-candidates.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert candidate_rows[0]["lemma"] == "raditi"
    summary = json.loads((output_dir / "run-summary.json").read_text(encoding="utf-8"))
    assert summary["parsed_rows"] == 1
    assert summary["unique_candidates"] == 1


def test_cli_normalize_writes_parse_errors(tmp_path, monkeypatch):
    source = tmp_path / "source.tsv"
    output_dir = tmp_path / "out"
    source.write_text("bad row\n", encoding="utf-8")
    monkeypatch.setattr("app.importer.cli.create_classla_normalizer", lambda: FakeNormalizer())

    exit_code = main(["normalize", "--input", str(source), "--output-dir", str(output_dir)])

    assert exit_code == 0
    assert (output_dir / "parse-errors.jsonl").exists()
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_cli.py -v
```

Expected: FAIL because CLI and CLASSLA adapter do not exist.

- [ ] **Step 3: Add optional local importer dependencies**

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
  "classla>=2.2",
  "httpx>=0.27",
]
```

If the existing `dev` block already includes `httpx`, leave it there. The important point is that base install remains free of CLASSLA.

- [ ] **Step 4: Add importer config model**

Create `backend/app/importer/config.py`:

```python
from pathlib import Path

from pydantic import BaseModel, Field


class ImporterConfig(BaseModel):
    input_path: Path | None = None
    output_dir: Path
    source: str = "tatoeba"
    lm_studio_base_url: str = "http://localhost:1234/v1"
    lm_studio_model: str = "local-model"
    llm_temperature: float = 0.1
    llm_timeout_seconds: float = 120
    llm_retries: int = 2
    llm_batch_size: int = Field(default=10, ge=1)
    llm_max_concurrency: int = Field(default=1, ge=1)
    candidate_limit: int | None = Field(default=None, ge=1)
```

- [ ] **Step 5: Add CLASSLA adapter with lazy import**

Create `backend/app/importer/classla_normalizer.py`:

```python
from app.importer.normalize import NormalizedToken


class ClasslaSerbianNormalizer:
    def __init__(self, pipeline) -> None:
        self.pipeline = pipeline

    def normalize(self, text: str) -> list[NormalizedToken]:
        document = self.pipeline(text)
        tokens: list[NormalizedToken] = []
        for sentence in document.sentences:
            for word in sentence.words:
                lemma = (getattr(word, "lemma", None) or getattr(word, "text", "")).strip()
                form = getattr(word, "text", "").strip()
                pos = getattr(word, "upos", None)
                tokens.append(NormalizedToken(lemma=lemma, form=form, pos=pos, normalized_lemma=lemma))
        return tokens


def create_classla_normalizer() -> ClasslaSerbianNormalizer:
    try:
        import classla
    except ImportError as exc:
        raise RuntimeError(
            "CLASSLA is required for normalize. Install local importer dependencies with "
            "`python -m pip install -e '.[importer-local]'`."
        ) from exc

    pipeline = classla.Pipeline("sr", processors="tokenize,pos,lemma")
    return ClasslaSerbianNormalizer(pipeline)
```

- [ ] **Step 6: Add CLI normalize command**

Create `backend/app/importer/cli.py`:

```python
import argparse
from pathlib import Path

from app.importer.artifacts import write_json, write_jsonl
from app.importer.classla_normalizer import create_classla_normalizer
from app.importer.normalize import build_candidates
from app.importer.tsv import parse_sentence_pairs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="slovnik-importer")
    subcommands = parser.add_subparsers(dest="command", required=True)

    normalize = subcommands.add_parser("normalize")
    normalize.add_argument("--input", required=True, type=Path)
    normalize.add_argument("--output-dir", required=True, type=Path)
    normalize.add_argument("--source", default="tatoeba")
    normalize.add_argument("--limit", type=int)

    return parser


def run_normalize(args: argparse.Namespace) -> int:
    output_dir: Path = args.output_dir
    parsed = parse_sentence_pairs(args.input)
    pairs = parsed.pairs[: args.limit] if args.limit else parsed.pairs
    normalizer = create_classla_normalizer()
    candidates = build_candidates(pairs, source=args.source, normalizer=normalizer)

    write_jsonl(output_dir / "normalized-candidates.jsonl", candidates)
    if parsed.errors:
        write_jsonl(output_dir / "parse-errors.jsonl", parsed.errors)
    write_json(
        output_dir / "run-summary.json",
        {
            "parsed_rows": len(parsed.pairs),
            "parse_errors": len(parsed.errors),
            "unique_candidates": len(candidates),
        },
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "normalize":
        return run_normalize(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Run CLI tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 8: Run importer tests and lint**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer -v
.venv/bin/ruff check app/importer tests/importer
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/pyproject.toml backend/app/importer/classla_normalizer.py backend/app/importer/config.py backend/app/importer/cli.py backend/tests/importer/test_cli.py
git commit -m "feat: add importer normalize command"
```

---

### Task 5: Transliteration and Deterministic Validation

**Files:**
- Create: `backend/app/importer/transliteration.py`
- Create: `backend/app/importer/validation.py`
- Create: `backend/tests/importer/test_transliteration.py`
- Create: `backend/tests/importer/test_validation.py`

- [ ] **Step 1: Write failing transliteration tests**

Create `backend/tests/importer/test_transliteration.py`:

```python
from app.importer.transliteration import cyrillic_to_latin, latin_to_cyrillic, scripts_match


def test_serbian_cyrillic_to_latin():
    assert cyrillic_to_latin("радити") == "raditi"
    assert cyrillic_to_latin("шта") == "šta"
    assert cyrillic_to_latin("жена") == "žena"


def test_serbian_latin_to_cyrillic_handles_digraphs():
    assert latin_to_cyrillic("raditi") == "радити"
    assert latin_to_cyrillic("ljudi") == "људи"
    assert latin_to_cyrillic("njegov") == "његов"
    assert latin_to_cyrillic("džep") == "џеп"
    assert latin_to_cyrillic("čitati") == "читати"
    assert latin_to_cyrillic("đak") == "ђак"


def test_scripts_match_ignores_case_and_whitespace():
    assert scripts_match("радити", " Raditi ")
    assert scripts_match("шта", "šta")
    assert scripts_match("шта", "sta")
    assert not scripts_match("радити", "pisati")
```

- [ ] **Step 2: Write failing validation tests**

Create `backend/tests/importer/test_validation.py`:

```python
from app.importer.schemas import EnrichedCandidate, EnrichmentMetadata, VocabularyPayload
from app.importer.validation import validate_enriched_candidate, validate_import_ready_rows


def accepted_candidate(**overrides):
    payload = {
        "candidate_id": "sha256:test",
        "status": "accepted",
        "vocabulary": VocabularyPayload(
            serbian_cyrillic="радити",
            serbian_latin="raditi",
            russian_translation="to do",
            cefr_level="A1",
            theme="verbs",
            example_sentences="Sta radis?",
            example_translations="What are you doing?",
        ),
        "metadata": EnrichmentMetadata(lemma="raditi", pos="VERB", confidence=0.9, selected_example_count=1),
    }
    payload.update(overrides)
    return EnrichedCandidate(**payload)


def test_validate_enriched_candidate_accepts_valid_row():
    errors = validate_enriched_candidate(accepted_candidate())

    assert errors == []


def test_validate_enriched_candidate_rejects_missing_vocabulary_for_accepted():
    errors = validate_enriched_candidate(accepted_candidate(vocabulary=None))

    assert "accepted candidate requires vocabulary" in errors


def test_validate_enriched_candidate_rejects_script_mismatch():
    candidate = accepted_candidate(
        vocabulary=VocabularyPayload(
            serbian_cyrillic="радити",
            serbian_latin="pisati",
            russian_translation="to do",
            cefr_level="A1",
            theme="verbs",
        )
    )

    errors = validate_enriched_candidate(candidate)

    assert "serbian_cyrillic and serbian_latin do not match" in errors


def test_validate_enriched_candidate_requires_examples_for_accepted_rows():
    candidate = accepted_candidate(
        vocabulary=VocabularyPayload(
            serbian_cyrillic="радити",
            serbian_latin="raditi",
            russian_translation="to do",
            cefr_level="A1",
            theme="verbs",
        )
    )

    errors = validate_enriched_candidate(candidate)

    assert "accepted candidate requires example_sentences" in errors
    assert "accepted candidate requires example_translations" in errors


def test_validate_import_ready_rows_rejects_duplicate_candidate_ids():
    rows = [accepted_candidate(), accepted_candidate()]

    result = validate_import_ready_rows(rows)

    assert result.valid_rows == []
    assert result.invalid_rows[0].candidate_id == "sha256:test"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_transliteration.py tests/importer/test_validation.py -v
```

Expected: FAIL because transliteration and validation modules do not exist.

- [ ] **Step 4: Implement transliteration helpers**

Create `backend/app/importer/transliteration.py`:

```python
CYR_TO_LAT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "ђ": "đ",
    "е": "e",
    "ж": "ž",
    "з": "z",
    "и": "i",
    "ј": "j",
    "к": "k",
    "л": "l",
    "љ": "lj",
    "м": "m",
    "н": "n",
    "њ": "nj",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "ћ": "ć",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "c",
    "ч": "č",
    "џ": "dž",
    "ш": "š",
}
LAT_TO_CYR_DIGRAPHS = {"lj": "љ", "nj": "њ", "dž": "џ", "dz": "џ", "dj": "ђ"}
LAT_TO_CYR = {
    "a": "а",
    "b": "б",
    "v": "в",
    "g": "г",
    "d": "д",
    "e": "е",
    "z": "з",
    "i": "и",
    "j": "ј",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "f": "ф",
    "h": "х",
    "c": "ц",
    "č": "ч",
    "ć": "ћ",
    "š": "ш",
    "ž": "ж",
    "đ": "ђ",
}
ASCII_FOLD = str.maketrans({"č": "c", "ć": "c", "š": "s", "ž": "z", "đ": "dj"})


def cyrillic_to_latin(text: str) -> str:
    return "".join(CYR_TO_LAT.get(char.casefold(), char) for char in text)


def latin_to_cyrillic(text: str) -> str:
    lower = text.casefold()
    output: list[str] = []
    index = 0
    while index < len(lower):
        pair = lower[index : index + 2]
        if pair in LAT_TO_CYR_DIGRAPHS:
            output.append(LAT_TO_CYR_DIGRAPHS[pair])
            index += 2
            continue
        output.append(LAT_TO_CYR.get(lower[index], lower[index]))
        index += 1
    return "".join(output)


def scripts_match(cyrillic: str, latin: str) -> bool:
    expected_latin = cyrillic_to_latin(cyrillic.strip()).casefold()
    actual_latin = latin.strip().casefold()
    if expected_latin == actual_latin:
        return True
    return expected_latin.translate(ASCII_FOLD) == actual_latin.translate(ASCII_FOLD)
```

Note: This is a lightweight Serbian transliteration helper, not a scholarly transliteration system. It should understand standard Serbian Latin diacritics and tolerate ASCII-folded source data for mismatch detection.

- [ ] **Step 5: Implement validation**

Create `backend/app/importer/validation.py`:

```python
from pydantic import BaseModel, Field

from app.importer.schemas import EnrichedCandidate
from app.importer.transliteration import scripts_match


class ImportReadyValidationResult(BaseModel):
    valid_rows: list[EnrichedCandidate] = Field(default_factory=list)
    invalid_rows: list[EnrichedCandidate] = Field(default_factory=list)


def validate_enriched_candidate(candidate: EnrichedCandidate) -> list[str]:
    errors: list[str] = []
    if candidate.status == "accepted":
        if candidate.vocabulary is None:
            errors.append("accepted candidate requires vocabulary")
        if candidate.metadata is None:
            errors.append("accepted candidate requires metadata")
        if candidate.rejection_reason is not None:
            errors.append("accepted candidate cannot include rejection_reason")
        if candidate.vocabulary is not None and not scripts_match(
            candidate.vocabulary.serbian_cyrillic,
            candidate.vocabulary.serbian_latin,
        ):
            errors.append("serbian_cyrillic and serbian_latin do not match")
        if candidate.vocabulary is not None and not candidate.vocabulary.example_sentences:
            errors.append("accepted candidate requires example_sentences")
        if candidate.vocabulary is not None and not candidate.vocabulary.example_translations:
            errors.append("accepted candidate requires example_translations")
    else:
        if candidate.rejection_reason is None:
            errors.append("rejected candidate requires rejection_reason")
        if candidate.vocabulary is not None:
            errors.append("rejected candidate cannot include vocabulary")
    return errors


def validate_import_ready_rows(rows: list[EnrichedCandidate]) -> ImportReadyValidationResult:
    seen: set[str] = set()
    duplicate_ids: set[str] = set()
    for row in rows:
        if row.candidate_id in seen:
            duplicate_ids.add(row.candidate_id)
        seen.add(row.candidate_id)

    result = ImportReadyValidationResult()
    for row in rows:
        errors = validate_enriched_candidate(row)
        if row.status != "accepted":
            errors.append("import-ready rows must be accepted")
        if row.candidate_id in duplicate_ids:
            errors.append("duplicate candidate_id")
        if errors:
            row.validation_errors = errors
            result.invalid_rows.append(row)
        else:
            result.valid_rows.append(row)
    return result
```

- [ ] **Step 6: Run transliteration and validation tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_transliteration.py tests/importer/test_validation.py -v
```

Expected: PASS.

- [ ] **Step 7: Run importer tests and lint**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer -v
.venv/bin/ruff check app/importer tests/importer
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/importer/transliteration.py backend/app/importer/validation.py backend/tests/importer/test_transliteration.py backend/tests/importer/test_validation.py
git commit -m "feat: validate importer artifacts"
```

---

### Task 6: LM Studio Client and Enrichment Stage

**Files:**
- Create: `backend/app/importer/lm_studio.py`
- Create: `backend/app/importer/enrich.py`
- Modify: `backend/app/importer/cli.py`
- Create: `backend/tests/importer/test_enrich.py`
- Modify: `backend/tests/importer/test_cli.py`

- [ ] **Step 1: Write failing enrichment tests**

Create `backend/tests/importer/test_enrich.py`:

```python
from app.importer.enrich import EnrichmentResult, enrich_candidates
from app.importer.schemas import CandidateExample, EnrichedCandidate, NormalizedCandidate


class FakeClient:
    def __init__(self):
        self.calls = []

    def enrich_batch(self, candidates):
        self.calls.append([candidate.candidate_id for candidate in candidates])
        outputs = []
        for candidate in candidates:
            if candidate.candidate_id == "sha256:bad" and len(candidates) > 1:
                outputs.append({"candidate_id": "sha256:bad", "status": "accepted"})
            else:
                outputs.append(
                    {
                        "candidate_id": candidate.candidate_id,
                        "status": "accepted",
                        "vocabulary": {
                            "serbian_cyrillic": "радити",
                            "serbian_latin": "raditi",
                            "russian_translation": "to do",
                            "cefr_level": "A1",
                            "theme": "verbs",
                            "example_sentences": "Sta radis?",
                            "example_translations": "What are you doing?",
                        },
                        "metadata": {
                            "lemma": candidate.lemma,
                            "pos": candidate.pos,
                            "confidence": 0.9,
                            "selected_example_count": 1,
                        },
                    }
                )
        return outputs

    def repair_candidate(self, candidate, validation_errors):
        self.calls.append([f"repair:{candidate.candidate_id}"])
        return {
            "candidate_id": candidate.candidate_id,
            "status": "accepted",
            "vocabulary": {
                "serbian_cyrillic": "радити",
                "serbian_latin": "raditi",
                "russian_translation": "to do",
                "cefr_level": "A1",
                "theme": "verbs",
                "example_sentences": "Sta radis?",
                "example_translations": "What are you doing?",
            },
            "metadata": {
                "lemma": candidate.lemma,
                "pos": candidate.pos,
                "confidence": 0.9,
                "selected_example_count": 1,
            },
        }


def candidate(candidate_id: str, lemma: str = "raditi") -> NormalizedCandidate:
    return NormalizedCandidate(
        candidate_id=candidate_id,
        lemma=lemma,
        pos="VERB",
        forms_seen=["radis"],
        examples=[
            CandidateExample(
                source="unit",
                ru_sentence_id="1",
                sr_sentence_id="2",
                ru="What are you doing?",
                sr="Sta radis?",
            )
        ],
    )


def test_enrich_candidates_keeps_valid_outputs():
    result = enrich_candidates([candidate("sha256:one")], client=FakeClient(), batch_size=10)

    assert isinstance(result, EnrichmentResult)
    assert len(result.enriched) == 1
    assert result.import_ready[0].candidate_id == "sha256:one"
    assert result.invalid == []


def test_enrich_candidates_retries_invalid_candidates_individually():
    client = FakeClient()

    result = enrich_candidates(
        [candidate("sha256:good"), candidate("sha256:bad")],
        client=client,
        batch_size=10,
    )

    assert client.calls == [["sha256:good", "sha256:bad"], ["repair:sha256:bad"]]
    assert [row.candidate_id for row in result.import_ready] == ["sha256:good", "sha256:bad"]
    assert result.invalid == []


def test_enrich_candidates_writes_persistent_invalid_output_to_invalid_rows():
    class InvalidClient:
        def enrich_batch(self, candidates):
            return [{"candidate_id": candidates[0].candidate_id, "status": "accepted"}]

        def repair_candidate(self, candidate, validation_errors):
            return {"candidate_id": candidate.candidate_id, "status": "accepted"}

    result = enrich_candidates(
        [candidate("sha256:bad")],
        client=InvalidClient(),
        batch_size=10,
        retry_count=1,
    )

    assert result.import_ready == []
    assert result.rejected == []
    assert result.invalid[0].candidate_id == "sha256:bad"
    assert "accepted candidate requires vocabulary" in result.invalid[0].validation_errors


def test_enrich_candidates_retries_missing_output():
    class MissingThenValidClient:
        def __init__(self):
            self.calls = 0

        def enrich_batch(self, candidates):
            self.calls += 1
            if self.calls == 1:
                return []
            return [
                {
                    "candidate_id": candidates[0].candidate_id,
                    "status": "accepted",
                    "vocabulary": {
                        "serbian_cyrillic": "радити",
                        "serbian_latin": "raditi",
                        "russian_translation": "to do",
                        "cefr_level": "A1",
                        "theme": "verbs",
                        "example_sentences": "Sta radis?",
                        "example_translations": "What are you doing?",
                    },
                    "metadata": {"lemma": "raditi", "pos": "VERB", "confidence": 0.9, "selected_example_count": 1},
                }
            ]

        def repair_candidate(self, candidate, validation_errors):
            self.calls += 1
            assert "missing candidate output" in validation_errors
            return {
                "candidate_id": candidate.candidate_id,
                "status": "accepted",
                "vocabulary": {
                    "serbian_cyrillic": "радити",
                    "serbian_latin": "raditi",
                    "russian_translation": "to do",
                    "cefr_level": "A1",
                    "theme": "verbs",
                    "example_sentences": "Sta radis?",
                    "example_translations": "What are you doing?",
                },
                "metadata": {"lemma": "raditi", "pos": "VERB", "confidence": 0.9, "selected_example_count": 1},
            }

    client = MissingThenValidClient()

    result = enrich_candidates([candidate("sha256:one")], client=client, batch_size=10, retry_count=1)

    assert client.calls == 2
    assert result.import_ready[0].candidate_id == "sha256:one"


def test_enrich_candidates_records_rejections():
    class RejectingClient:
        def enrich_batch(self, candidates):
            return [{"candidate_id": candidates[0].candidate_id, "status": "rejected", "rejection_reason": "proper_name"}]

        def repair_candidate(self, candidate, validation_errors):
            raise AssertionError("valid rejections should not be repaired")

    result = enrich_candidates([candidate("sha256:name")], client=RejectingClient(), batch_size=10)

    assert result.import_ready == []
    assert result.rejected[0].rejection_reason == "proper_name"
```

- [ ] **Step 2: Add failing CLI enrich test**

Append to `backend/tests/importer/test_cli.py`:

```python
def test_cli_enrich_writes_import_ready_artifact(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    normalized = output_dir / "normalized-candidates.jsonl"
    normalized.write_text(
        '{"candidate_id":"sha256:one","lemma":"raditi","pos":"VERB","forms_seen":["radis"],'
        '"examples":[{"source":"unit","ru_sentence_id":"1","sr_sentence_id":"2","ru":"What?","sr":"Sta?"}]}\n',
        encoding="utf-8",
    )

    class FakeClient:
        def enrich_batch(self, candidates):
            return [
                {
                    "candidate_id": candidates[0].candidate_id,
                    "status": "accepted",
                    "vocabulary": {
                        "serbian_cyrillic": "радити",
                        "serbian_latin": "raditi",
                        "russian_translation": "to do",
                        "cefr_level": "A1",
                        "theme": "verbs",
                        "example_sentences": "Sta radis?",
                        "example_translations": "What are you doing?",
                    },
                    "metadata": {"lemma": "raditi", "pos": "VERB", "confidence": 0.9, "selected_example_count": 1},
                }
            ]

    monkeypatch.setattr("app.importer.cli.create_lm_studio_client", lambda **_: FakeClient())

    exit_code = main([
        "enrich",
        "--output-dir",
        str(output_dir),
        "--model",
        "gemma",
        "--retries",
        "1",
        "--max-concurrency",
        "1",
    ])

    assert exit_code == 0
    assert (output_dir / "llm-enriched.jsonl").exists()
    assert (output_dir / "import-ready.jsonl").exists()
```

- [ ] **Step 3: Run enrichment tests to verify they fail**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_enrich.py tests/importer/test_cli.py -v
```

Expected: FAIL because enrichment modules and CLI command do not exist.

- [ ] **Step 4: Implement LM Studio client**

Create `backend/app/importer/lm_studio.py`:

```python
from typing import Any

import httpx

from app.importer.schemas import NormalizedCandidate


class LMStudioClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        temperature: float = 0.1,
        timeout_seconds: float = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    def enrich_batch(self, candidates: list[NormalizedCandidate]) -> list[dict[str, Any]]:
        payload = self._chat_json(_system_prompt(), _user_prompt(candidates))
        if isinstance(payload, dict) and "items" in payload:
            return payload["items"]
        if isinstance(payload, list):
            return payload
        raise ValueError("LM Studio response must be a JSON object with items or a JSON array")

    def repair_candidate(self, candidate: NormalizedCandidate, validation_errors: list[str]) -> dict[str, Any]:
        payload = self._chat_json(_system_prompt(), _repair_prompt(candidate, validation_errors))
        if isinstance(payload, dict) and "candidate_id" in payload:
            return payload
        if isinstance(payload, dict) and "items" in payload and len(payload["items"]) == 1:
            return payload["items"][0]
        raise ValueError("LM Studio repair response must be one JSON object")

    def _chat_json(self, system_prompt: str, user_prompt: str) -> Any:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "temperature": self.temperature,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return httpx.Response(200, text=content).json()


def _system_prompt() -> str:
    return (
        "You enrich Serbian vocabulary candidates for Russian-speaking learners. "
        "Return strict JSON only. Each item must align with candidate_id and have status accepted or rejected. "
        "Accepted items must include vocabulary and metadata. Rejected items must include rejection_reason."
    )


def _user_prompt(candidates: list[NormalizedCandidate]) -> str:
    lines = ["Enrich these candidates into Slovnik vocabulary JSON:"]
    for candidate in candidates:
        lines.append(candidate.model_dump_json(exclude_none=True))
    return "\n".join(lines)


def _repair_prompt(candidate: NormalizedCandidate, validation_errors: list[str]) -> str:
    return (
        "Your previous output for this candidate was invalid. "
        "Return exactly one corrected JSON object for the same candidate_id.\n"
        f"Validation errors: {validation_errors}\n"
        f"Candidate: {candidate.model_dump_json(exclude_none=True)}"
    )
```

- [ ] **Step 5: Implement enrichment orchestration**

Create `backend/app/importer/enrich.py`:

```python
from collections.abc import Iterable, Protocol
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, Field, ValidationError

from app.importer.schemas import EnrichedCandidate, NormalizedCandidate
from app.importer.validation import validate_enriched_candidate


class EnrichmentClient(Protocol):
    def enrich_batch(self, candidates: list[NormalizedCandidate]) -> list[dict]:
        """Return raw structured LLM outputs for candidates."""

    def repair_candidate(self, candidate: NormalizedCandidate, validation_errors: list[str]) -> dict:
        """Return one corrected structured output for a previously invalid candidate."""


class EnrichmentResult(BaseModel):
    enriched: list[EnrichedCandidate] = Field(default_factory=list)
    import_ready: list[EnrichedCandidate] = Field(default_factory=list)
    rejected: list[EnrichedCandidate] = Field(default_factory=list)
    invalid: list[EnrichedCandidate] = Field(default_factory=list)

    def merge(self, other: "EnrichmentResult") -> None:
        self.enriched.extend(other.enriched)
        self.import_ready.extend(other.import_ready)
        self.rejected.extend(other.rejected)
        self.invalid.extend(other.invalid)


def enrich_candidates(
    candidates: list[NormalizedCandidate],
    *,
    client: EnrichmentClient,
    batch_size: int,
    retry_count: int = 1,
    max_concurrency: int = 1,
) -> EnrichmentResult:
    result = EnrichmentResult()
    batches = list(_chunks(candidates, batch_size))
    if max_concurrency <= 1:
        for batch in batches:
            result.merge(_process_batch(batch, client=client, retry_count=retry_count))
        return result

    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        futures = [
            executor.submit(_process_batch, batch, client=client, retry_count=retry_count)
            for batch in batches
        ]
        for future in futures:
            result.merge(future.result())
    return result


def _process_batch(
    batch: list[NormalizedCandidate],
    *,
    client: EnrichmentClient,
    retry_count: int,
) -> EnrichmentResult:
    result = EnrichmentResult()
    try:
        raw_outputs = client.enrich_batch(batch)
    except Exception as exc:
        if retry_count > 0:
            for candidate in batch:
                result.merge(_process_batch([candidate], client=client, retry_count=retry_count - 1))
            return result
        for candidate in batch:
            result.invalid.append(
                EnrichedCandidate(
                    candidate_id=candidate.candidate_id,
                    status="rejected",
                    rejection_reason="invalid_output",
                    validation_errors=[f"llm request failed: {exc}"],
                )
            )
        return result

    output_counts: dict[str, int] = {}
    outputs_by_id: dict[str, dict] = {}
    for item in raw_outputs:
        if not isinstance(item, dict):
            continue
        candidate_id = item.get("candidate_id")
        if not isinstance(candidate_id, str):
            continue
        output_counts[candidate_id] = output_counts.get(candidate_id, 0) + 1
        outputs_by_id[candidate_id] = item

    for candidate in batch:
        raw = outputs_by_id.get(candidate.candidate_id)
        row, parse_errors = _parse_output(candidate, raw)
        errors = parse_errors + validate_enriched_candidate(row)
        if output_counts.get(candidate.candidate_id, 0) > 1:
            errors.append("duplicate candidate output")
        if errors and retry_count > 0:
            result.merge(
                _repair_candidate(
                    candidate,
                    client=client,
                    validation_errors=errors,
                    retry_count=retry_count - 1,
                )
            )
            continue
        if errors:
            row.validation_errors = errors
            result.invalid.append(row)
            continue
        result.enriched.append(row)
        if row.status == "accepted":
            result.import_ready.append(row)
        else:
            result.rejected.append(row)
    return result


def _repair_candidate(
    candidate: NormalizedCandidate,
    *,
    client: EnrichmentClient,
    validation_errors: list[str],
    retry_count: int,
) -> EnrichmentResult:
    result = EnrichmentResult()
    try:
        raw = client.repair_candidate(candidate, validation_errors)
    except Exception as exc:
        row = EnrichedCandidate(
            candidate_id=candidate.candidate_id,
            status="rejected",
            rejection_reason="invalid_output",
            validation_errors=[f"llm repair failed: {exc}"],
        )
        result.invalid.append(row)
        return result

    row, parse_errors = _parse_output(candidate, raw)
    errors = parse_errors + validate_enriched_candidate(row)
    if errors and retry_count > 0:
        return _repair_candidate(
            candidate,
            client=client,
            validation_errors=errors,
            retry_count=retry_count - 1,
        )
    if errors:
        row.validation_errors = errors
        result.invalid.append(row)
        return result
    result.enriched.append(row)
    if row.status == "accepted":
        result.import_ready.append(row)
    else:
        result.rejected.append(row)
    return result


def _parse_output(candidate: NormalizedCandidate, raw: dict | None) -> tuple[EnrichedCandidate, list[str]]:
    if raw is None:
        return (
            EnrichedCandidate(candidate_id=candidate.candidate_id, status="rejected", rejection_reason="invalid_output"),
            ["missing candidate output"],
        )
    try:
        return EnrichedCandidate.model_validate(raw), []
    except ValidationError as exc:
        return (
            EnrichedCandidate(candidate_id=candidate.candidate_id, status="rejected", rejection_reason="invalid_output"),
            [str(exc)],
        )


def _chunks(rows: list[NormalizedCandidate], size: int) -> Iterable[list[NormalizedCandidate]]:
    for index in range(0, len(rows), size):
        yield rows[index : index + size]
```

- [ ] **Step 6: Extend CLI with enrich command**

Modify `backend/app/importer/cli.py`:

```python
from app.importer.artifacts import read_jsonl, write_json, write_jsonl
from app.importer.enrich import enrich_candidates
from app.importer.schemas import NormalizedCandidate
```

Add a lazy LM Studio factory so `import-artifact` can run on the server without importing `httpx`:

```python
def create_lm_studio_client(**kwargs):
    from app.importer.lm_studio import LMStudioClient

    return LMStudioClient(**kwargs)
```

Add parser:

```python
    enrich = subcommands.add_parser("enrich")
    enrich.add_argument("--output-dir", required=True, type=Path)
    enrich.add_argument("--base-url", default="http://localhost:1234/v1")
    enrich.add_argument("--model", required=True)
    enrich.add_argument("--batch-size", type=int, default=10)
    enrich.add_argument("--retries", type=int, default=2)
    enrich.add_argument("--max-concurrency", type=int, default=1)
    enrich.add_argument("--temperature", type=float, default=0.1)
    enrich.add_argument("--timeout-seconds", type=float, default=120)
    enrich.add_argument("--limit", type=int)
```

Add runner:

```python
def run_enrich(args: argparse.Namespace) -> int:
    output_dir: Path = args.output_dir
    candidates = list(read_jsonl(output_dir / "normalized-candidates.jsonl", NormalizedCandidate))
    if args.limit:
        candidates = candidates[: args.limit]
    client = create_lm_studio_client(
        base_url=args.base_url,
        model=args.model,
        temperature=args.temperature,
        timeout_seconds=args.timeout_seconds,
    )
    result = enrich_candidates(
        candidates,
        client=client,
        batch_size=args.batch_size,
        retry_count=args.retries,
        max_concurrency=args.max_concurrency,
    )
    write_jsonl(output_dir / "llm-enriched.jsonl", result.enriched)
    write_jsonl(output_dir / "import-ready.jsonl", result.import_ready)
    if result.rejected:
        write_jsonl(output_dir / "rejected-candidates.jsonl", result.rejected)
    if result.invalid:
        write_jsonl(output_dir / "invalid-llm-output.jsonl", result.invalid)
    write_json(
        output_dir / "run-summary.json",
        {
            "unique_candidates": len(candidates),
            "accepted_llm_outputs": len(result.import_ready),
            "rejected_llm_outputs": len(result.rejected),
            "invalid_outputs": len(result.invalid),
        },
    )
    return 0
```

Update `main`:

```python
    if args.command == "enrich":
        return run_enrich(args)
```

- [ ] **Step 7: Run enrichment and CLI tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_enrich.py tests/importer/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 8: Run importer tests and lint**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer -v
.venv/bin/ruff check app/importer tests/importer
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/importer/lm_studio.py backend/app/importer/enrich.py backend/app/importer/cli.py backend/tests/importer/test_enrich.py backend/tests/importer/test_cli.py
git commit -m "feat: enrich vocabulary import candidates"
```

---

### Task 7: Server Artifact Import

**Files:**
- Create: `backend/app/importer/import_service.py`
- Modify: `backend/app/importer/cli.py`
- Create: `backend/tests/importer/test_import_service.py`
- Modify: `backend/tests/importer/test_cli.py`

- [ ] **Step 1: Write failing import service tests**

Create `backend/tests/importer/test_import_service.py`:

```python
from app.importer.import_service import import_artifact_rows
from app.importer.schemas import EnrichedCandidate, EnrichmentMetadata, VocabularyPayload
from app.models import VocabularyItem


def row(candidate_id: str = "sha256:one", latin: str = "raditi") -> EnrichedCandidate:
    return EnrichedCandidate(
        candidate_id=candidate_id,
        status="accepted",
        vocabulary=VocabularyPayload(
            serbian_cyrillic="радити",
            serbian_latin=latin,
            russian_translation="to do",
            cefr_level="A1",
            theme="verbs",
            example_sentences="Sta radis?",
            example_translations="What are you doing?",
        ),
        metadata=EnrichmentMetadata(lemma=latin, pos="VERB", confidence=0.9, selected_example_count=1),
    )


def test_import_artifact_rows_creates_vocabulary_items(db_session):
    report = import_artifact_rows(db_session, [row()])

    assert report.imported_rows == 1
    words = db_session.query(VocabularyItem).all()
    assert words[0].serbian_latin == "raditi"


def test_import_artifact_rows_skips_existing_latin_duplicate(db_session):
    db_session.add(
        VocabularyItem(
            serbian_cyrillic="радити",
            serbian_latin="raditi",
            russian_translation="to do",
            cefr_level="A1",
            theme="verbs",
            example_sentences="Sta radis?",
            example_translations="What are you doing?",
        )
    )
    db_session.commit()

    report = import_artifact_rows(db_session, [row()])

    assert report.imported_rows == 0
    assert report.duplicate_skips == 1
    assert db_session.query(VocabularyItem).count() == 1


def test_import_artifact_rows_skips_invalid_rows(db_session):
    invalid = row()
    invalid.validation_errors = ["bad row"]

    report = import_artifact_rows(db_session, [invalid])

    assert report.imported_rows == 0
    assert report.invalid_outputs == 1
```

- [ ] **Step 2: Add failing CLI import test**

Append to `backend/tests/importer/test_cli.py`:

```python
def test_cli_import_artifact_uses_import_ready_rows(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "import-ready.jsonl").write_text(
        '{"candidate_id":"sha256:one","status":"accepted","vocabulary":'
        '{"serbian_cyrillic":"радити","serbian_latin":"raditi","russian_translation":"to do",'
        '"cefr_level":"A1","theme":"verbs","example_sentences":"Sta radis?",'
        '"example_translations":"What are you doing?"},"metadata":{"lemma":"raditi","pos":"VERB"}}\n',
        encoding="utf-8",
    )

    called = {}

    def fake_import(db, rows):
        called["rows"] = rows
        from app.importer.schemas import ImportReport

        return ImportReport(imported_rows=1)

    monkeypatch.setattr("app.importer.cli.import_artifact_rows", fake_import)
    class FakeSession:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr("app.importer.cli.SessionLocal", lambda: FakeSession())

    exit_code = main(["import-artifact", "--output-dir", str(output_dir)])

    assert exit_code == 0
    assert called["rows"][0].candidate_id == "sha256:one"
```

- [ ] **Step 3: Run import tests to verify they fail**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_import_service.py tests/importer/test_cli.py -v
```

Expected: FAIL because import service and CLI command do not exist.

- [ ] **Step 4: Implement import service**

Create `backend/app/importer/import_service.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importer.schemas import EnrichedCandidate, ImportReport
from app.importer.validation import validate_enriched_candidate
from app.models import VocabularyItem


def import_artifact_rows(db: Session, rows: list[EnrichedCandidate]) -> ImportReport:
    report = ImportReport()
    for row in rows:
        errors = row.validation_errors or validate_enriched_candidate(row)
        if errors or row.status != "accepted" or row.vocabulary is None:
            report.invalid_outputs += 1
            continue
        if _is_duplicate(db, row.vocabulary.serbian_latin, row.vocabulary.serbian_cyrillic):
            report.duplicate_skips += 1
            continue
        db.add(VocabularyItem(**row.vocabulary.model_dump()))
        report.imported_rows += 1
    db.commit()
    return report


def _is_duplicate(db: Session, serbian_latin: str, serbian_cyrillic: str) -> bool:
    statement = select(VocabularyItem.id).where(
        (VocabularyItem.serbian_latin == serbian_latin) | (VocabularyItem.serbian_cyrillic == serbian_cyrillic)
    )
    return db.scalar(statement) is not None
```

- [ ] **Step 5: Extend CLI with import-artifact command**

Modify `backend/app/importer/cli.py` imports:

```python
from app.db import SessionLocal
from app.importer.import_service import import_artifact_rows
from app.importer.schemas import EnrichedCandidate, NormalizedCandidate
```

Add parser:

```python
    import_artifact = subcommands.add_parser("import-artifact")
    import_artifact.add_argument("--output-dir", required=True, type=Path)
```

Add runner:

```python
def run_import_artifact(args: argparse.Namespace) -> int:
    output_dir: Path = args.output_dir
    rows = list(read_jsonl(output_dir / "import-ready.jsonl", EnrichedCandidate))
    with SessionLocal() as db:
        report = import_artifact_rows(db, rows)
    write_json(output_dir / "import-report.json", report.model_dump())
    return 0
```

Update `main`:

```python
    if args.command == "import-artifact":
        return run_import_artifact(args)
```

- [ ] **Step 6: Run import tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_import_service.py tests/importer/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 7: Run backend importer tests and lint**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer -v
.venv/bin/ruff check app/importer tests/importer
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/importer/import_service.py backend/app/importer/cli.py backend/tests/importer/test_import_service.py backend/tests/importer/test_cli.py
git commit -m "feat: import vocabulary artifacts"
```

---

### Task 8: Convenience Commands, Documentation, and Product State

**Files:**
- Modify: `backend/app/importer/cli.py`
- Modify: `backend/tests/importer/test_cli.py`
- Modify: `README.md`
- Modify: `docs/product-state.md`

- [ ] **Step 1: Write failing CLI wrapper tests**

Append to `backend/tests/importer/test_cli.py`:

```python
def test_cli_run_local_runs_normalize_then_enrich(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr("app.importer.cli.run_normalize", lambda args: calls.append("normalize") or 0)
    monkeypatch.setattr("app.importer.cli.run_enrich", lambda args: calls.append("enrich") or 0)

    exit_code = main([
        "run-local",
        "--input",
        str(tmp_path / "source.tsv"),
        "--output-dir",
        str(tmp_path / "out"),
        "--model",
        "gemma",
    ])

    assert exit_code == 0
    assert calls == ["normalize", "enrich"]


def test_cli_run_all_runs_all_stages(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr("app.importer.cli.run_normalize", lambda args: calls.append("normalize") or 0)
    monkeypatch.setattr("app.importer.cli.run_enrich", lambda args: calls.append("enrich") or 0)
    monkeypatch.setattr("app.importer.cli.run_import_artifact", lambda args: calls.append("import") or 0)

    exit_code = main([
        "run-all",
        "--input",
        str(tmp_path / "source.tsv"),
        "--output-dir",
        str(tmp_path / "out"),
        "--model",
        "gemma",
    ])

    assert exit_code == 0
    assert calls == ["normalize", "enrich", "import"]
```

- [ ] **Step 2: Run wrapper tests to verify they fail**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_cli.py -v
```

Expected: FAIL because `run-local` and `run-all` commands do not exist.

- [ ] **Step 3: Add shared local pipeline parser arguments**

Modify `backend/app/importer/cli.py` with helper:

```python
def add_local_pipeline_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--source", default="tatoeba")
    parser.add_argument("--base-url", default="http://localhost:1234/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument("--limit", type=int)
```

Add subcommands:

```python
    run_local = subcommands.add_parser("run-local")
    add_local_pipeline_args(run_local)

    run_all = subcommands.add_parser("run-all")
    add_local_pipeline_args(run_all)
```

Add runners:

```python
def run_local(args: argparse.Namespace) -> int:
    normalize_exit = run_normalize(args)
    if normalize_exit != 0:
        return normalize_exit
    return run_enrich(args)


def run_all(args: argparse.Namespace) -> int:
    local_exit = run_local(args)
    if local_exit != 0:
        return local_exit
    return run_import_artifact(args)
```

Update `main`:

```python
    if args.command == "run-local":
        return run_local(args)
    if args.command == "run-all":
        return run_all(args)
```

- [ ] **Step 4: Run wrapper tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/importer/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Update README with importer setup and commands**

Modify `README.md` by adding a section after Local Development or Verification:

```markdown
## Vocabulary Importer

The importer turns Russian-Serbian sentence-pair TSV files into Slovnik vocabulary records.

Local enrichment requires CLASSLA and an OpenAI-compatible LM Studio server:

```bash
cd backend
.venv/bin/python -m pip install -e ".[dev,importer-local]"
.venv/bin/python -m app.importer.cli normalize --input /path/to/pairs.tsv --output-dir /path/to/import-run --source tatoeba --limit 100
.venv/bin/python -m app.importer.cli enrich --output-dir /path/to/import-run --model your-lm-studio-model --batch-size 10
```

Server import does not require CLASSLA or LM Studio:

```bash
cd backend
.venv/bin/python -m app.importer.cli import-artifact --output-dir /path/to/import-run
```

Convenience commands:

```bash
.venv/bin/python -m app.importer.cli run-local --input /path/to/pairs.tsv --output-dir /path/to/import-run --model your-lm-studio-model --limit 100
.venv/bin/python -m app.importer.cli run-all --input /path/to/pairs.tsv --output-dir /path/to/import-run --model your-lm-studio-model --limit 100
```

Each stage writes JSONL artifacts and summary files so failed or expensive runs can be resumed from the last completed stage.
```

- [ ] **Step 6: Update product state audit**

Modify `docs/product-state.md`:

- Update `Last audited` to the implementation date.
- In Product Summary, mention the CLI vocabulary importer.
- Add a Backend Architecture/API or Data Model note that importer modules live under `backend/app/importer/`.
- Update Verification/Test Coverage with importer test commands.
- Remove or revise the Known Limitations line that says bulk import and AI generation are not implemented. It should now say no helper UI, verifier-model stage, API push, live lemma column, or semantic LLM verification.
- Add source files under Important Source Files and Docs:
  - `backend/app/importer/`
  - `docs/superpowers/specs/2026-07-06-vocabulary-importer-design.md`
  - `docs/superpowers/plans/2026-07-06-vocabulary-importer.md`

- [ ] **Step 7: Run importer, backend, and lint verification**

Run:

```bash
cd backend
.venv/bin/ruff check .
.venv/bin/pytest -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/importer/cli.py backend/tests/importer/test_cli.py README.md docs/product-state.md
git commit -m "docs: document vocabulary importer workflow"
```

---

### Task 9: Manual Sample Verification

**Files:**
- No source changes expected unless verification exposes defects.

- [ ] **Step 1: Verify TSV parser against the real sample file**

Run:

```bash
cd backend
.venv/bin/python -m app.importer.cli normalize --input "/Users/launert/Downloads/Sentence pairs in Russian-Serbian - 2026-06-22.tsv" --output-dir /tmp/slovnik-import-sample --source tatoeba --limit 10
```

Expected:

- `normalized-candidates.jsonl` exists.
- `run-summary.json` exists.
- `parse-errors.jsonl` is absent or empty.
- No more than the first 10 parsed sentence pairs were normalized.

Note: This requires CLASSLA and its Serbian model installed locally. If CLASSLA is missing, install local importer dependencies and model per CLASSLA documentation. Do not make the VPS depend on CLASSLA.

- [ ] **Step 2: Verify enrichment against LM Studio with a tiny sample**

Start LM Studio locally with the desired model loaded, then run:

```bash
cd backend
.venv/bin/python -m app.importer.cli enrich --output-dir /tmp/slovnik-import-sample --model "google/gemma-4-26b" --batch-size 2 --limit 5
```

Expected:

- `llm-enriched.jsonl` exists.
- `import-ready.jsonl` exists.
- `run-summary.json` reports accepted, rejected, and invalid counts.
- Invalid outputs, if any, are written to `invalid-llm-output.jsonl` and not to `import-ready.jsonl`.

- [ ] **Step 3: Verify import against local dev database only**

Start local Postgres and apply migrations:

```bash
docker compose up -d postgres
cd backend
.venv/bin/alembic upgrade head
.venv/bin/python -m app.importer.cli import-artifact --output-dir /tmp/slovnik-import-sample
```

Expected:

- `import-report.json` exists.
- `imported_rows` plus `duplicate_skips` matches the number of valid accepted rows.
- Rerunning the same command increases `duplicate_skips` and does not duplicate obvious existing words.

- [ ] **Step 4: Run final regression suite**

Run:

```bash
cd backend
.venv/bin/ruff check .
.venv/bin/pytest -v
```

Expected: PASS.

Frontend tests are not required for importer-only changes unless documentation or behavior changes touch frontend code.

- [ ] **Step 5: Commit fixes if manual verification exposed defects**

If defects were found and fixed:

```bash
git add backend/app/importer backend/tests/importer README.md docs/product-state.md
git commit -m "fix: stabilize vocabulary importer sample run"
```

If no defects were found, do not create an empty commit.

---

## Final Verification Checklist

- [ ] `cd backend && .venv/bin/ruff check .`
- [ ] `cd backend && .venv/bin/pytest -v`
- [ ] `normalize` sample run with `--limit 10` on the real TSV file.
- [ ] `enrich` sample run with LM Studio and `--limit 5`.
- [ ] `import-artifact` sample run against local dev Postgres.
- [ ] `docs/product-state.md` updated with durable product facts.
- [ ] `README.md` updated with setup and command examples.
- [ ] No untracked source artifacts from sample import runs committed.
- [ ] Only intentional files staged and committed.
