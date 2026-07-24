# AI Vocabulary Fill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add password-gated, single-word OpenAI vocabulary generation with persistent reuse, duplicate detection, editable structured stress, and in-word stressed-syllable emphasis.

**Architecture:** Extend `vocabulary_items` with nullable structured stress and add a separate `ai_vocabulary_generations` store keyed by NFC/trim/casefold source word. A focused OpenAI client parses a strict nullable Pydantic output, while `ai_vocabulary_service.py` owns validation, duplicate/store lookup, patch construction, persistence, and stable product errors. Vue keeps AI orchestration in the editor view and delegates stress editing/rendering to focused components.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, OpenAI Python SDK/Responses API, PostgreSQL/SQLite tests, Vue 3, TypeScript, Vitest, Playwright.

---

### Task 1: Reproducible backend setup and persistence schema

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/models.py`
- Create: `backend/alembic/versions/20260724_0002_ai_vocabulary_fill.py`
- Test: `backend/tests/test_schema.py`
- Test: `backend/tests/test_migrations.py`

- [ ] **Step 1: Write failing model and migration tests**

Add tests that assert:

```python
def test_vocabulary_item_accepts_structured_stress(db_session):
    word = VocabularyItem(
        serbian_cyrillic="радити",
        serbian_latin="raditi",
        russian_translation="делать",
        cefr_level="A1",
        theme="work",
        stress_pattern={
            "cyrillic_syllables": ["ра", "ди", "ти"],
            "latin_syllables": ["ra", "di", "ti"],
            "stressed_syllable_index": 0,
        },
    )
    db_session.add(word)
    db_session.commit()
    assert word.stress_pattern["stressed_syllable_index"] == 0


def test_ai_generation_normalized_source_is_unique(db_session):
    first = AiVocabularyGeneration(
        source_word="raditi",
        normalized_source_word="raditi",
        generated_payload={"serbian_latin": "raditi", "russian_translation": "делать"},
        missing_required_fields=["serbian_cyrillic", "cefr_level", "theme"],
        model="test-model",
        prompt_version="v1",
    )
    duplicate = AiVocabularyGeneration(
        source_word="Raditi",
        normalized_source_word="raditi",
        generated_payload={"serbian_latin": "Raditi", "russian_translation": "делать"},
        missing_required_fields=[],
        model="test-model",
        prompt_version="v1",
    )
    db_session.add(first)
    db_session.commit()
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
```

Add a migration test that upgrades a temporary SQLite database from `20260702_0001` to `head`, then inspects:

```python
assert "stress_pattern" in vocabulary_columns
assert "ai_vocabulary_generations" in inspector.get_table_names()
assert {"source_word", "normalized_source_word", "generated_payload"} <= generation_columns
unique_columns = {
    tuple(constraint["column_names"])
    for constraint in inspector.get_unique_constraints("ai_vocabulary_generations")
}
unique_indexes = {
    tuple(index["column_names"])
    for index in inspector.get_indexes("ai_vocabulary_generations")
    if index["unique"]
}
assert ("normalized_source_word",) in unique_columns | unique_indexes
```

The migration test must also insert two rows with the same normalized key through SQL against the upgraded database and assert the second insert raises `IntegrityError`. The ORM uniqueness test remains useful, but it is not a substitute for testing the migrated schema.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_schema.py tests/test_migrations.py -v
```

Expected: FAIL because `stress_pattern`, `AiVocabularyGeneration`, and migration `0002` do not exist.

- [ ] **Step 3: Add model and migration**

In `backend/app/models.py`:

```python
from typing import Any

from sqlalchemy import JSON, ...


class VocabularyItem(Base):
    ...
    stress_pattern: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class AiVocabularyGeneration(Base):
    __tablename__ = "ai_vocabulary_generations"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_word: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_source_word: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    generated_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    missing_required_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Migration `20260724_0002` adds `vocabulary_items.stress_pattern`, creates the generation table, and creates a unique constraint/index for `normalized_source_word`. Downgrade drops only the new table and column; it never drops `stress_marker`.

- [ ] **Step 4: Fix reproducible packaging**

In `backend/pyproject.toml`:

```toml
dependencies = [
  ...
  "openai>=2.48,<3",
]

[project.optional-dependencies]
dev = [
  ...
  "ruff>=0.6,<0.7",
]

[tool.setuptools.packages.find]
include = ["app*"]
exclude = ["alembic*", "tests*"]
```

Run:

```bash
cd backend
.venv/bin/python -m pip install -e ".[dev]"
```

Expected: editable install succeeds.

- [ ] **Step 5: Run focused tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_schema.py tests/test_migrations.py -v
.venv/bin/ruff check app/models.py alembic/versions/20260724_0002_ai_vocabulary_fill.py tests/test_schema.py tests/test_migrations.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/app/models.py backend/alembic/versions/20260724_0002_ai_vocabulary_fill.py backend/tests/test_schema.py backend/tests/test_migrations.py
git commit -m "feat: add AI generation persistence"
```

### Task 2: Structured stress API contract and vocabulary validation

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/services/vocabulary_service.py`
- Test: `backend/tests/test_vocabulary.py`
- Create: `frontend/src/components/StressText.vue`
- Create: `frontend/tests/unit/stress-text.test.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/components/WordCard.vue`
- Modify: `frontend/src/views/VocabularyListView.vue`

- [ ] **Step 1: Write failing backend validation tests**

Add:

```python
VALID_STRESS = {
    "cyrillic_syllables": ["ра", "ди", "ти"],
    "latin_syllables": ["ra", "di", "ti"],
    "stressed_syllable_index": 0,
}


def test_editor_can_save_structured_stress(client):
    response = client.post(
        "/api/vocabulary",
        headers={"X-Editor-Password": settings.editor_password},
        json={**BASE_WORD, "stress_pattern": VALID_STRESS},
    )
    assert response.status_code == 201
    assert response.json()["stress_pattern"] == VALID_STRESS


@pytest.mark.parametrize(
    "stress_pattern",
    [
        {**VALID_STRESS, "stressed_syllable_index": 3},
        {**VALID_STRESS, "latin_syllables": ["ra", "diti"]},
        {**VALID_STRESS, "cyrillic_syllables": ["рад", "ити"]},
    ],
)
def test_editor_rejects_invalid_structured_stress(client, stress_pattern):
    response = client.post(
        "/api/vocabulary",
        headers={"X-Editor-Password": settings.editor_password},
        json={**BASE_WORD, "stress_pattern": stress_pattern},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run backend tests and verify they fail**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_vocabulary.py -v
```

Expected: FAIL because schemas ignore/reject no structured stress contract.

- [ ] **Step 3: Implement Pydantic stress schemas**

Add:

```python
class StressPattern(BaseModel):
    cyrillic_syllables: list[str] = Field(min_length=1)
    latin_syllables: list[str] = Field(min_length=1)
    stressed_syllable_index: int = Field(ge=0)


class VocabularyCreate(BaseModel):
    ...
    stress_pattern: StressPattern | None = None

    @model_validator(mode="after")
    def validate_stress_pattern(self) -> "VocabularyCreate":
        pattern = self.stress_pattern
        if pattern is None:
            return self
        if len(pattern.cyrillic_syllables) != len(pattern.latin_syllables):
            raise ValueError("Stress syllable counts must match")
        if pattern.stressed_syllable_index >= len(pattern.cyrillic_syllables):
            raise ValueError("Stress index is out of range")
        if normalize_nfc("".join(pattern.cyrillic_syllables)) != normalize_nfc(self.serbian_cyrillic):
            raise ValueError("Cyrillic syllables must reconstruct the word")
        if normalize_nfc("".join(pattern.latin_syllables)) != normalize_nfc(self.serbian_latin):
            raise ValueError("Latin syllables must reconstruct the word")
        return self
```

Use one local NFC helper and reject empty/whitespace-only syllables.

- [ ] **Step 4: Write failing stress renderer tests**

Test `StressText.vue`:

```ts
it("bolds the complete selected syllable without using HTML", () => {
  const wrapper = mount(StressText, {
    props: {
      word: "ljubav",
      syllables: ["lju", "bav"],
      stressedIndex: 0,
    },
  });
  expect(wrapper.text()).toBe("ljubav");
  expect(wrapper.get("strong").text()).toBe("lju");
  expect(wrapper.html()).not.toContain("v-html");
});

it("falls back to plain text when pattern does not reconstruct the word", () => {
  const wrapper = mount(StressText, {
    props: { word: "raditi", syllables: ["ra", "diti-x"], stressedIndex: 0 },
  });
  expect(wrapper.find("strong").exists()).toBe(false);
  expect(wrapper.text()).toBe("raditi");
});
```

- [ ] **Step 5: Implement shared stress rendering**

Extend frontend types:

```ts
export type StressPattern = {
  cyrillic_syllables: string[];
  latin_syllables: string[];
  stressed_syllable_index: number;
};

export type VocabularyWord = {
  ...
  stress_pattern?: StressPattern | null;
};
```

`StressText.vue` renders syllables with normal interpolation and a conditional `<strong>`. Update `WordCard.vue` and `VocabularyListView.vue` to use it for both scripts. Keep `stress_marker` in metadata only when no `stress_pattern` exists.

- [ ] **Step 6: Run focused backend/frontend tests**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_vocabulary.py -v
cd ../frontend
npm run test:unit -- stress-text
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas.py backend/app/services/vocabulary_service.py backend/tests/test_vocabulary.py frontend/src/api/client.ts frontend/src/components/StressText.vue frontend/src/components/WordCard.vue frontend/src/views/VocabularyListView.vue frontend/tests/unit/stress-text.test.ts
git commit -m "feat: render structured word stress"
```

### Task 3: OpenAI configuration and strict generation client

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/services/openai_vocabulary_client.py`
- Create: `backend/tests/test_openai_vocabulary_client.py`
- Modify: `backend/tests/test_config.py`

- [ ] **Step 1: Write failing config and client tests**

Config:

```python
def test_openai_model_has_efficient_default():
    config = Settings(environment="test", editor_password="secret")
    assert config.openai_model == "gpt-5.6-luna"
    assert config.openai_api_key == ""
```

Client:

```python
def test_generate_uses_responses_parse_with_structured_schema():
    parsed = RawAiVocabulary(
        serbian_cyrillic="радити",
        serbian_latin="raditi",
        russian_translation="делать",
        cefr_level="A1",
        theme="work",
        usage_register=None,
        stress_pattern=None,
        meaning_notes=None,
        example_sentences=None,
        example_translations=None,
    )
    responses = Mock()
    responses.parse.return_value = SimpleNamespace(
        output_parsed=parsed,
        _request_id="req_123",
    )
    result = generate_vocabulary("raditi", client=SimpleNamespace(responses=responses))
    assert result.payload == parsed
    assert result.request_id == "req_123"
    assert responses.parse.call_args.kwargs["model"] == settings.openai_model
```

Also test missing key, rate limit, timeout, connection failure, refusal/unparsed output, and that logs never contain the API key.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_config.py tests/test_openai_vocabulary_client.py -v
```

Expected: FAIL because settings and client do not exist.

- [ ] **Step 3: Implement settings and raw model**

In settings:

```python
openai_api_key: str = ""
openai_model: str = "gpt-5.6-luna"
openai_timeout_seconds: float = 20.0
```

In `openai_vocabulary_client.py`, define:

```python
PROMPT_VERSION = "v1"


class RawStressPattern(BaseModel):
    cyrillic_syllables: list[str] | None
    latin_syllables: list[str] | None
    stressed_syllable_index: int | None


class RawAiVocabulary(BaseModel):
    serbian_cyrillic: str | None
    serbian_latin: str | None
    russian_translation: str | None
    cefr_level: Literal["A1", "A2", "B1", "B2", "C1", "C2"] | None
    theme: Literal[...controlled themes...] | None
    usage_register: str | None
    stress_pattern: RawStressPattern | None
    meaning_notes: str | None
    example_sentences: str | None
    example_translations: str | None


@dataclass(frozen=True)
class OpenAiVocabularyResult:
    payload: RawAiVocabulary
    request_id: str | None
```

All properties have no Pydantic defaults so the generated JSON Schema marks them required while allowing null.

- [ ] **Step 4: Implement Responses API adapter**

Use:

```python
client = OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
response = client.responses.parse(
    model=settings.openai_model,
    input=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": source_word},
    ],
    text_format=RawAiVocabulary,
)
if response.output_parsed is None:
    raise InvalidAiResponseError("OpenAI returned no parsed vocabulary")
return OpenAiVocabularyResult(
    payload=response.output_parsed,
    request_id=getattr(response, "_request_id", None),
)
```

Map SDK exceptions to internal typed errors:

- missing key/authentication -> `OpenAiNotConfiguredError`
- `RateLimitError` -> `OpenAiRateLimitedError`
- `APITimeoutError` -> `OpenAiTimeoutError`
- connection/status failures -> `OpenAiUnavailableError`
- refusal/unparsed output -> `InvalidAiResponseError`

The client logs transport/API categories with model, prompt version, and request id when available. It does not log the source word because normalization belongs to the service. The returned `OpenAiVocabularyResult` preserves request metadata so `ai_vocabulary_service.py` can log semantic validation categories with `normalized_source_word`, model, prompt version, and request id.

- [ ] **Step 5: Run focused tests and lint**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_config.py tests/test_openai_vocabulary_client.py -v
.venv/bin/ruff check app/config.py app/services/openai_vocabulary_client.py tests/test_config.py tests/test_openai_vocabulary_client.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/services/openai_vocabulary_client.py backend/tests/test_config.py backend/tests/test_openai_vocabulary_client.py
git commit -m "feat: add structured OpenAI vocabulary client"
```

### Task 4: AI fill orchestration, persistent reuse, and endpoint

**Files:**
- Create: `backend/app/services/ai_vocabulary_service.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routers/vocabulary.py`
- Create: `backend/tests/test_ai_vocabulary.py`

- [ ] **Step 1: Write failing service tests**

Cover normalization, validation, duplicate priority, edit exclusion, store hit, generation persistence, partial output, stress dropping, below-threshold output, and conflict recovery:

```python
def test_normalize_source_word_uses_nfc_trim_and_casefold():
    assert normalize_source_word("  RÁDITI  ") == normalize_source_word("ráditi")


def test_existing_word_wins_before_store_or_openai(db_session, monkeypatch):
    existing = add_word(db_session, serbian_latin="raditi")
    generate = Mock(side_effect=AssertionError("OpenAI must not run"))
    result = fill_vocabulary(db_session, AiFillRequest(source_word=" Raditi "), generate=generate)
    assert result.status == "already_exists"
    assert result.word_id == existing.id


def test_store_hit_skips_openai(db_session):
    add_generation(db_session, normalized_source_word="raditi")
    generate = Mock(side_effect=AssertionError("OpenAI must not run"))
    result = fill_vocabulary(db_session, AiFillRequest(source_word="raditi"), generate=generate)
    assert result.status == "generated"
    assert result.source == "store"


def test_openai_success_persists_non_null_patch(db_session):
    generated = generated_result(usage_register=None, request_id="req_123")
    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi"),
        generate=lambda _: generated,
    )
    assert result.source == "openai"
    assert "usage_register" not in result.payload.model_dump(exclude_unset=True)
    assert db_session.scalar(select(func.count(AiVocabularyGeneration.id))) == 1
```

Add parameterized validation cases:

```python
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("serbian_cyrillic", " "),
        ("serbian_latin", "x" * 161),
        ("russian_translation", "x" * 241),
        ("usage_register", "x" * 81),
        ("meaning_notes", "   "),
        ("example_sentences", "\n"),
    ],
)
def test_unusable_generated_fields_are_omitted(db_session, field, value):
    generated = generated_result(**{field: value})
    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi"),
        generate=lambda _: generated,
    )
    assert field not in result.payload.model_dump(exclude_unset=True)
```

Also test that trimming is applied to every non-null string, and that dropping invalid bounded fields triggers `invalid_ai_response` without persistence when the minimum usable threshold is no longer met.

- [ ] **Step 2: Run service tests and verify they fail**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_ai_vocabulary.py -v
```

Expected: FAIL because service and API schemas do not exist.

- [ ] **Step 3: Implement request/response schemas**

Add:

```python
class AiFillRequest(BaseModel):
    source_word: str
    current_word_id: int | None = Field(default=None, ge=1)


class AiFillPayload(BaseModel):
    serbian_cyrillic: str | None = None
    ...
    stress_pattern: StressPattern | None = None


class AiFillGeneratedResponse(BaseModel):
    status: Literal["generated"] = "generated"
    source: Literal["openai", "store"]
    payload: AiFillPayload
    missing_required_fields: list[str]


class AiFillExistingResponse(BaseModel):
    status: Literal["already_exists"] = "already_exists"
    word_id: int
    message: str = "Word already exists."


AiFillResponse = Annotated[
    AiFillGeneratedResponse | AiFillExistingResponse,
    Field(discriminator="status"),
]
```

- [ ] **Step 4: Implement orchestration**

`fill_vocabulary` performs exactly:

1. Validate one trimmed word, max 160.
2. Normalize with NFC + trim + casefold.
3. Scan existing headwords using the same normalization, excluding `current_word_id`.
4. Return `already_exists` before store/OpenAI.
5. Return stored generation when present.
6. Call the injected/default generator.
7. Build a non-null, bounded patch. Strip every generated string and omit whitespace-only strings. Enforce `160` for each Serbian spelling, `240` for Russian translation, and `80` for usage register. CEFR and theme remain enum-controlled. Existing Text fields (`meaning_notes`, examples, translations) have no database length cap, but whitespace-only values are omitted.
8. Keep stress only when both generated spellings exist and pattern reconstructs both.
9. Require Russian translation plus at least one Serbian spelling.
10. Calculate missing required fields.
11. Insert generation; on `IntegrityError`, rollback, re-read, and return `source="store"`.

Use typed `AiFillServiceError(code, message, status_code)` for stable product errors. When semantic validation drops stress or another generated field, log `normalized_source_word`, configured model, prompt version, error category, and the request id retained in `OpenAiVocabularyResult`.

Catch typed OpenAI client errors at the service boundary, log the same normalized-source context there, and translate them to the stable product codes. Client logs may describe transport details, but service logs are the authoritative records that join those failures to `normalized_source_word`.

- [ ] **Step 5: Write failing endpoint tests**

Add:

```python
def test_ai_fill_requires_editor_password(client):
    response = client.post("/api/vocabulary/ai-fill", json={"source_word": "raditi"})
    assert response.status_code == 403
    assert response.json() == {
        "code": "invalid_editor_password",
        "message": "Invalid editor password.",
    }


def test_ai_fill_returns_generated_payload(client, monkeypatch):
    monkeypatch.setattr(ai_vocabulary_service, "generate_vocabulary", lambda _: generated_result())
    response = client.post(
        "/api/vocabulary/ai-fill",
        headers={"X-Editor-Password": settings.editor_password},
        json={"source_word": "raditi"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "generated"
```

Also assert all stable error codes/statuses from the SDD.

- [ ] **Step 6: Implement endpoint**

The route manually verifies `X-Editor-Password` so the AI endpoint can return its stable error body. Declare `response_model=AiFillResponse` and `response_model_exclude_none=True` so both success branches retain discriminated validation while omitted patch fields are not serialized as null. It calls the service and converts `AiFillServiceError` to:

```python
JSONResponse(
    status_code=error.status_code,
    content={"code": error.code, "message": error.message},
)
```

- [ ] **Step 7: Run backend suite**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_ai_vocabulary.py tests/test_vocabulary.py -v
.venv/bin/ruff check app/services/ai_vocabulary_service.py app/routers/vocabulary.py app/schemas.py tests/test_ai_vocabulary.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/ai_vocabulary_service.py backend/app/schemas.py backend/app/routers/vocabulary.py backend/tests/test_ai_vocabulary.py
git commit -m "feat: add persistent AI vocabulary fill endpoint"
```

### Task 5: Frontend API, stress editor, and AI fill workflow

**Files:**
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/components/StressEditor.vue`
- Modify: `frontend/src/views/WordEditorView.vue`
- Modify: `frontend/src/i18n/messages.ts`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/unit/vocabulary.test.ts`
- Modify: `frontend/tests/unit/word-editor.test.ts`
- Create: `frontend/tests/unit/stress-editor.test.ts`

- [ ] **Step 1: Write failing API tests**

Test:

```ts
it("requests one AI-filled word with editor password and current id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ status: "generated", source: "store", payload: {}, missing_required_fields: [] }),
  });
  vi.stubGlobal("fetch", fetchMock);
  await fillVocabularyWithAi("raditi", "secret", 7);
  expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/vocabulary/ai-fill", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Editor-Password": "secret" },
    body: JSON.stringify({ source_word: "raditi", current_word_id: 7 }),
  });
});

it("throws a typed API error with backend code", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: false,
    status: 503,
    json: () => Promise.resolve({ code: "openai_timeout", message: "AI fill timed out." }),
  }));
  await expect(fillVocabularyWithAi("raditi", "secret")).rejects.toMatchObject({
    code: "openai_timeout",
  });
});
```

- [ ] **Step 2: Implement frontend API contract**

Add discriminated response types and `AiFillApiError`. Ensure `current_word_id` is omitted on create rather than serialized as undefined/null.

- [ ] **Step 3: Write failing stress editor tests**

Test middle-dot parsing, shared index selection, clear, stale headword invalidation, and external model updates:

```ts
it("emits a pattern after aligned syllables and stress selection", async () => {
  const wrapper = mount(StressEditor, {
    props: { cyrillicWord: "радити", latinWord: "raditi", modelValue: null },
  });
  await wrapper.get('[name="cyrillic_syllables"]').setValue("ра·ди·ти");
  await wrapper.get('[name="latin_syllables"]').setValue("ra·di·ti");
  await wrapper.get('[data-stress-index="0"]').trigger("click");
  expect(wrapper.emitted("update:modelValue")?.at(-1)?.[0]).toEqual({
    cyrillic_syllables: ["ра", "ди", "ти"],
    latin_syllables: ["ra", "di", "ti"],
    stressed_syllable_index: 0,
  });
});

it("synchronizes its inputs when AI updates modelValue after mount", async () => {
  const wrapper = mount(StressEditor, {
    props: { cyrillicWord: "радити", latinWord: "raditi", modelValue: null },
  });
  await wrapper.setProps({ modelValue: validStressPattern });
  expect(wrapper.get('[name="cyrillic_syllables"]').element.value).toBe("ра·ди·ти");
  expect(wrapper.get('[name="latin_syllables"]').element.value).toBe("ra·di·ti");
  expect(wrapper.get('[data-stress-index="0"]').classes()).toContain("is-selected");
});
```

- [ ] **Step 4: Implement `StressEditor.vue`**

The component owns only presentation syntax (`·`) and validation. It emits a valid `StressPattern` or `null`; it never emits stale invalid data. Watch `modelValue` with `deep: true` and `immediate: true` to synchronize both text inputs and selected index after loading an existing word, applying AI output, and restoring the snapshot. Guard the watcher/emitter against feedback loops. Use fixed-size syllable buttons and a plain-text `StressText` preview.

- [ ] **Step 5: Expand editor tests for AI flow**

Cover:

- AI block hidden before unlock.
- Empty input disables fill.
- Generated patch applies only returned fields.
- Current form snapshot restores all fields, including structured stress.
- Missing required fields are derived from the merged form, so populated pre-existing fields are not highlighted and markers disappear as the editor types.
- `already_exists` shows an explicit edit button without navigation.
- Strong errors render a dismissible `role="alert"` toast and preserve the form.
- Stored result uses neutral copy.
- Russian and Serbian copy render.

- [ ] **Step 6: Implement editor workflow**

In `WordEditorView.vue` add:

- `aiSourceWord`, `isAiLoading`, `aiInfo`, `aiError`, `existingWordId`
- `undoSnapshot`
- `showAiMissingFields` and a computed `missingRequiredFields`
- AI block after password unlock and above the form
- `fillWithAi`, `restorePreviousValues`, and dismiss-error handlers
- `StressEditor` bound to `form.stress_pattern`

Before applying `generated`, copy the form through a dedicated `cloneFormState` helper that explicitly copies scalar fields and deep-copies `stress_pattern` arrays. Do not call `structuredClone(form)` because Vue's reactive object is a Proxy. Apply only `Object.entries(response.payload)`.

Use a boolean such as `showAiMissingFields` to enable post-generation highlighting, then derive missing required fields from the current merged form with a computed value over `serbian_cyrillic`, `serbian_latin`, `russian_translation`, `cefr_level`, and `theme`. This reconciles backend partial output with pre-existing values and automatically removes markers while the user completes fields. Reset the mode on restore or successful save. On technical errors, do not mutate the form.

- [ ] **Step 7: Add localized copy and restrained styles**

Add every AI/stress string to both `ru` and `sr`. Style the AI block as an unframed subsection inside the existing panel, with a compact row, missing-field borders, aligned syllable controls, and a fixed toast. Preserve the existing light palette and mobile grid behavior.

- [ ] **Step 8: Run frontend tests and build**

Run:

```bash
cd frontend
npm run test:unit
npm run build
```

Expected: all tests and build pass.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/components/StressEditor.vue frontend/src/views/WordEditorView.vue frontend/src/i18n/messages.ts frontend/src/styles.css frontend/tests/unit/vocabulary.test.ts frontend/tests/unit/word-editor.test.ts frontend/tests/unit/stress-editor.test.ts
git commit -m "feat: add AI-assisted vocabulary editor"
```

### Task 6: Documentation, migration sanity, and end-to-end verification

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docs/product-state.md`
- Modify: `docs/testing/mvp-manual-test.md`
- Create: `frontend/tests/e2e/ai-editor-flow.spec.ts`

- [ ] **Step 1: Update setup and product audit**

Document:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6-luna
OPENAI_TIMEOUT_SECONDS=20
```

README must explain backend-only key handling, migration command, store reuse, and no-regenerate behavior. `docs/product-state.md` must move AI generation and structured stress from deferred to implemented, list `/api/vocabulary/ai-fill`, the generation table, the setup caveat, and actual verification results. Extend the manual test with unlock -> AI fill -> restore -> save -> stressed display -> duplicate edit flow.

- [ ] **Step 2: Verify migration upgrade/downgrade**

Run against a disposable database or the migration test:

```bash
cd backend
.venv/bin/pytest tests/test_migrations.py -v
```

Expected: initial -> head -> initial round trip passes without dropping legacy `stress_marker`.

- [ ] **Step 3: Run full backend verification**

Run:

```bash
cd backend
.venv/bin/ruff check .
.venv/bin/pytest -v
```

Expected: all checks pass.

- [ ] **Step 4: Run full frontend verification**

Run:

```bash
cd frontend
npm run test:unit
npm run build
npm run test:e2e
```

Expected: all checks pass.

- [ ] **Step 5: Run local browser smoke test**

Add a deterministic Playwright scenario that intercepts editor verification, AI fill, and vocabulary save/list requests. Run it at desktop and mobile widths and verify:

- AI block is legible after unlock.
- Toast and missing-field states do not overlap.
- Cyrillic and Latin stressed syllables render bold.
- Existing editor save still works.

- [ ] **Step 6: Verify documentation diff**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only intended tracked files plus pre-existing ignored/untracked user artifacts.

- [ ] **Step 7: Commit**

```bash
git add .env.example README.md docs/product-state.md docs/testing/mvp-manual-test.md frontend/tests/e2e/ai-editor-flow.spec.ts
git commit -m "docs: document AI vocabulary fill"
```

- [ ] **Step 8: Request code review**

Use `superpowers:requesting-code-review` against the implementation range. Address only verified, actionable findings, then rerun the complete verification suite.
