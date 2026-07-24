import logging
import unicodedata
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.models import AiVocabularyGeneration, VocabularyItem
from app.schemas import AiFillRequest
from app.services import ai_vocabulary_service
from app.services.ai_vocabulary_service import (
    AiFillServiceError,
    fill_vocabulary,
    normalize_source_word,
)
from app.services.openai_vocabulary_client import (
    OpenAiVocabularyResult,
    RawAiVocabulary,
    RawStressPattern,
)


VALID_STRESS = {
    "cyrillic_syllables": ["ра", "ди", "ти"],
    "latin_syllables": ["ra", "di", "ti"],
    "stressed_syllable_index": 0,
}

GENERATED_PAYLOAD = {
    "serbian_cyrillic": "радити",
    "serbian_latin": "raditi",
    "russian_translation": "делать",
    "cefr_level": "A1",
    "theme": "work",
    "usage_register": None,
    "stress_pattern": VALID_STRESS,
    "meaning_notes": None,
    "example_sentences": None,
    "example_translations": None,
}

ERROR_CASES = [
    (
        "OpenAiNotConfiguredError",
        "openai_not_configured",
        "AI fill is not configured.",
        503,
    ),
    (
        "OpenAiRateLimitedError",
        "openai_rate_limited",
        "AI fill is temporarily unavailable.",
        503,
    ),
    (
        "OpenAiTimeoutError",
        "openai_timeout",
        "AI fill timed out.",
        503,
    ),
    (
        "OpenAiUnavailableError",
        "openai_unavailable",
        "AI fill is temporarily unavailable.",
        503,
    ),
    (
        "InvalidAiResponseError",
        "invalid_ai_response",
        "AI fill returned an invalid response.",
        502,
    ),
]


@pytest.fixture(autouse=True)
def configured_model(monkeypatch):
    monkeypatch.setattr(
        ai_vocabulary_service,
        "settings",
        SimpleNamespace(openai_model="test-model"),
    )


def generated_result(request_id="req_123", **overrides):
    payload = {**GENERATED_PAYLOAD, **overrides}
    stress_pattern = payload.get("stress_pattern")
    if isinstance(stress_pattern, dict):
        payload["stress_pattern"] = RawStressPattern(**stress_pattern)
    return OpenAiVocabularyResult(
        payload=RawAiVocabulary.model_construct(**payload),
        request_id=request_id,
    )


def add_word(db_session, **overrides):
    payload = {
        "serbian_cyrillic": "радити",
        "serbian_latin": "raditi",
        "russian_translation": "делать",
        "cefr_level": "A1",
        "theme": "work",
        **overrides,
    }
    word = VocabularyItem(**payload)
    db_session.add(word)
    db_session.commit()
    db_session.refresh(word)
    return word


def add_generation(db_session, **overrides):
    payload = {
        "source_word": "raditi",
        "normalized_source_word": "raditi",
        "generated_payload": {
            "serbian_latin": "raditi",
            "russian_translation": "делать",
        },
        "missing_required_fields": ["serbian_cyrillic", "cefr_level", "theme"],
        "model": "stored-model",
        "prompt_version": "stored-v1",
        **overrides,
    }
    generation = AiVocabularyGeneration(**payload)
    db_session.add(generation)
    db_session.commit()
    db_session.refresh(generation)
    return generation


def test_normalize_source_word_uses_nfc_trim_and_casefold():
    decomposed = unicodedata.normalize("NFD", "RÁDITI")

    assert normalize_source_word(f"  {decomposed}  ") == normalize_source_word("ráditi")


@pytest.mark.parametrize("source_word", ["", "   ", "dve reči", "x" * 161])
def test_invalid_source_word_uses_stable_service_error(db_session, source_word):
    with pytest.raises(AiFillServiceError) as caught:
        fill_vocabulary(
            db_session,
            AiFillRequest(source_word=source_word),
            generate=Mock(side_effect=AssertionError("OpenAI must not run")),
        )

    assert caught.value.code == "invalid_source_word"
    assert caught.value.message == "Enter one Serbian word up to 160 characters."
    assert caught.value.status_code == 422


def test_existing_word_wins_before_store_or_openai(db_session):
    existing = add_word(db_session, serbian_latin="Raditi")
    add_generation(db_session)

    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word=" raditi "),
        generate=Mock(side_effect=AssertionError("OpenAI must not run")),
    )

    assert result.status == "already_exists"
    assert result.word_id == existing.id


def test_duplicate_lookup_matches_normalized_cyrillic(db_session):
    existing = add_word(db_session, serbian_cyrillic=unicodedata.normalize("NFD", "РАДИТИ"))

    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="радити"),
        generate=Mock(side_effect=AssertionError("OpenAI must not run")),
    )

    assert result.status == "already_exists"
    assert result.word_id == existing.id


def test_duplicate_lookup_excludes_current_word(db_session):
    existing = add_word(db_session)
    generate = Mock(return_value=generated_result())

    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi", current_word_id=existing.id),
        generate=generate,
    )

    assert result.status == "generated"
    assert result.source == "openai"
    generate.assert_called_once_with("raditi")


def test_duplicate_lookup_still_finds_other_word_when_current_is_excluded(db_session):
    current = add_word(db_session, serbian_cyrillic="тренутан", serbian_latin="trenutan")
    duplicate = add_word(db_session)

    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi", current_word_id=current.id),
        generate=Mock(side_effect=AssertionError("OpenAI must not run")),
    )

    assert result.status == "already_exists"
    assert result.word_id == duplicate.id


def test_store_hit_skips_openai(db_session):
    stored = add_generation(db_session)

    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word=" Raditi "),
        generate=Mock(side_effect=AssertionError("OpenAI must not run")),
    )

    assert result.status == "generated"
    assert result.source == "store"
    assert result.payload.model_dump(exclude_unset=True) == stored.generated_payload
    assert result.missing_required_fields == stored.missing_required_fields


def test_openai_success_persists_non_null_patch_and_metadata(db_session):
    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word=" Raditi "),
        generate=lambda _: generated_result(usage_register=None),
    )

    assert result.status == "generated"
    assert result.source == "openai"
    assert "usage_register" not in result.payload.model_dump(exclude_unset=True)
    generation = db_session.scalar(select(AiVocabularyGeneration))
    assert generation is not None
    assert generation.source_word == "Raditi"
    assert generation.normalized_source_word == "raditi"
    assert generation.generated_payload == result.payload.model_dump(exclude_none=True)
    assert generation.model == "test-model"
    assert generation.prompt_version == ai_vocabulary_service.PROMPT_VERSION


def test_openai_receives_trimmed_source_word(db_session):
    generate = Mock(return_value=generated_result())

    fill_vocabulary(
        db_session,
        AiFillRequest(source_word="  RÁDITI  "),
        generate=generate,
    )

    generate.assert_called_once_with("RÁDITI")


def test_partial_output_is_persisted_with_missing_required_fields(db_session):
    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi"),
        generate=lambda _: generated_result(
            serbian_cyrillic=None,
            cefr_level=None,
            theme=None,
            stress_pattern=None,
        ),
    )

    assert result.payload.model_dump(exclude_unset=True) == {
        "serbian_latin": "raditi",
        "russian_translation": "делать",
    }
    assert result.missing_required_fields == ["serbian_cyrillic", "cefr_level", "theme"]
    stored = db_session.scalar(select(AiVocabularyGeneration))
    assert stored is not None
    assert stored.missing_required_fields == result.missing_required_fields


def test_every_non_null_generated_string_is_trimmed(db_session):
    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi"),
        generate=lambda _: generated_result(
            serbian_cyrillic="  радити ",
            serbian_latin="\traditi\n",
            russian_translation=" делать ",
            cefr_level=" A1 ",
            theme=" work ",
            usage_register=" neutral ",
            meaning_notes=" note ",
            example_sentences=" Ja radim. ",
            example_translations=" Я работаю. ",
            stress_pattern={
                "cyrillic_syllables": [" ра ", " ди ", " ти "],
                "latin_syllables": [" ra ", " di ", " ti "],
                "stressed_syllable_index": 0,
            },
        ),
    )

    assert result.payload.model_dump(exclude_none=True) == {
        "serbian_cyrillic": "радити",
        "serbian_latin": "raditi",
        "russian_translation": "делать",
        "cefr_level": "A1",
        "theme": "work",
        "usage_register": "neutral",
        "stress_pattern": VALID_STRESS,
        "meaning_notes": "note",
        "example_sentences": "Ja radim.",
        "example_translations": "Я работаю.",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("serbian_cyrillic", " "),
        ("serbian_latin", "x" * 161),
        ("usage_register", "x" * 81),
        ("meaning_notes", "   "),
        ("example_sentences", "\n"),
        ("example_translations", "\t"),
        ("cefr_level", "A0"),
        ("theme", "arbitrary-theme"),
    ],
)
def test_unusable_generated_fields_are_omitted_and_logged(
    db_session,
    caplog,
    field,
    value,
):
    caplog.set_level(logging.WARNING)

    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi"),
        generate=lambda _: generated_result(**{field: value}, stress_pattern=None),
    )

    assert field not in result.payload.model_dump(exclude_unset=True)
    record = next(
        record
        for record in caplog.records
        if getattr(record, "error_category", None) == "invalid_generated_field"
        and getattr(record, "field", None) == field
    )
    assert record.normalized_source_word == "raditi"
    assert record.model == "test-model"
    assert record.prompt_version == ai_vocabulary_service.PROMPT_VERSION
    assert record.request_id == "req_123"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("russian_translation", "x" * 241),
        ("russian_translation", " "),
        ("serbian_cyrillic", "x" * 161),
    ],
)
def test_dropping_minimum_required_output_returns_invalid_response_without_persistence(
    db_session,
    field,
    value,
):
    overrides = {field: value}
    if field == "serbian_cyrillic":
        overrides["serbian_latin"] = None

    with pytest.raises(AiFillServiceError) as caught:
        fill_vocabulary(
            db_session,
            AiFillRequest(source_word="raditi"),
            generate=lambda _: generated_result(**overrides),
        )

    assert caught.value.code == "invalid_ai_response"
    assert caught.value.status_code == 502
    assert db_session.scalar(select(func.count(AiVocabularyGeneration.id))) == 0


def test_valid_stress_pattern_is_kept(db_session):
    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi"),
        generate=lambda _: generated_result(),
    )

    assert result.payload.stress_pattern is not None
    assert result.payload.stress_pattern.model_dump() == VALID_STRESS


@pytest.mark.parametrize(
    "stress_pattern",
    [
        {**VALID_STRESS, "stressed_syllable_index": 3},
        {**VALID_STRESS, "latin_syllables": ["ra", "diti"]},
        {**VALID_STRESS, "cyrillic_syllables": ["рад", "ити"]},
        {**VALID_STRESS, "latin_syllables": ["rad", "", "iti"]},
    ],
)
def test_invalid_stress_is_dropped_and_remaining_payload_is_persisted(
    db_session,
    caplog,
    stress_pattern,
):
    caplog.set_level(logging.WARNING)

    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi"),
        generate=lambda _: generated_result(stress_pattern=stress_pattern),
    )

    assert result.payload.stress_pattern is None
    stored = db_session.scalar(select(AiVocabularyGeneration))
    assert stored is not None
    assert "stress_pattern" not in stored.generated_payload
    record = next(
        record
        for record in caplog.records
        if getattr(record, "error_category", None) == "invalid_stress_pattern"
    )
    assert record.normalized_source_word == "raditi"
    assert record.model == "test-model"
    assert record.prompt_version == ai_vocabulary_service.PROMPT_VERSION
    assert record.request_id == "req_123"


@pytest.mark.parametrize("missing_spelling", ["serbian_cyrillic", "serbian_latin"])
def test_stress_is_dropped_when_either_generated_spelling_is_absent(
    db_session,
    missing_spelling,
):
    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi"),
        generate=lambda _: generated_result(**{missing_spelling: None}),
    )

    assert result.payload.stress_pattern is None
    assert result.source == "openai"


@pytest.mark.parametrize(
    ("error_class_name", "code", "message", "status_code"),
    ERROR_CASES,
)
def test_typed_openai_errors_are_translated_and_logged(
    db_session,
    caplog,
    error_class_name,
    code,
    message,
    status_code,
):
    caplog.set_level(logging.WARNING)
    error_class = getattr(ai_vocabulary_service, error_class_name)
    error = error_class("technical detail")
    error.request_id = "req_error"

    with pytest.raises(AiFillServiceError) as caught:
        fill_vocabulary(
            db_session,
            AiFillRequest(source_word=" Raditi "),
            generate=Mock(side_effect=error),
        )

    assert (caught.value.code, caught.value.message, caught.value.status_code) == (
        code,
        message,
        status_code,
    )
    record = next(
        record
        for record in caplog.records
        if getattr(record, "error_category", None) == code
    )
    assert record.normalized_source_word == "raditi"
    assert record.model == "test-model"
    assert record.prompt_version == ai_vocabulary_service.PROMPT_VERSION
    assert record.request_id == "req_error"


def test_integrity_error_rolls_back_and_returns_concurrent_store_row(
    db_session,
    monkeypatch,
):
    concurrent = AiVocabularyGeneration(
        source_word="raditi",
        normalized_source_word="raditi",
        generated_payload={
            "serbian_latin": "raditi",
            "russian_translation": "делать",
        },
        missing_required_fields=["serbian_cyrillic", "cefr_level", "theme"],
        model="other-model",
        prompt_version="other-v1",
    )
    find_stored = Mock(side_effect=[None, concurrent])
    rollback = Mock()
    monkeypatch.setattr(ai_vocabulary_service, "_find_stored_generation", find_stored)
    monkeypatch.setattr(
        db_session,
        "commit",
        Mock(side_effect=IntegrityError("insert", {}, Exception("unique"))),
    )
    monkeypatch.setattr(db_session, "rollback", rollback)

    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi"),
        generate=lambda _: generated_result(),
    )

    assert result.source == "store"
    assert result.payload.serbian_latin == "raditi"
    rollback.assert_called_once_with()
    assert find_stored.call_count == 2


def test_ai_fill_requires_editor_password(client):
    response = client.post("/api/vocabulary/ai-fill", json={"source_word": "raditi"})

    assert response.status_code == 403
    assert response.json() == {
        "code": "invalid_editor_password",
        "message": "Invalid editor password.",
    }


def test_ai_fill_returns_generated_payload_without_null_fields(client, monkeypatch):
    monkeypatch.setattr(
        ai_vocabulary_service,
        "generate_vocabulary",
        lambda _: generated_result(usage_register=None),
    )

    response = client.post(
        "/api/vocabulary/ai-fill",
        headers={"X-Editor-Password": settings.editor_password},
        json={"source_word": "raditi"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "generated"
    assert response.json()["source"] == "openai"
    assert "usage_register" not in response.json()["payload"]


def test_ai_fill_endpoint_returns_stable_source_validation_error(client, monkeypatch):
    generate = Mock(side_effect=AssertionError("OpenAI must not run"))
    monkeypatch.setattr(ai_vocabulary_service, "generate_vocabulary", generate)

    response = client.post(
        "/api/vocabulary/ai-fill",
        headers={"X-Editor-Password": settings.editor_password},
        json={"source_word": "two words"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "invalid_source_word",
        "message": "Enter one Serbian word up to 160 characters.",
    }


@pytest.mark.parametrize(
    ("error_class_name", "code", "message", "status_code"),
    ERROR_CASES,
)
def test_ai_fill_endpoint_returns_stable_openai_error(
    client,
    monkeypatch,
    error_class_name,
    code,
    message,
    status_code,
):
    error_class = getattr(ai_vocabulary_service, error_class_name)
    monkeypatch.setattr(
        ai_vocabulary_service,
        "generate_vocabulary",
        Mock(side_effect=error_class("technical detail")),
    )

    response = client.post(
        "/api/vocabulary/ai-fill",
        headers={"X-Editor-Password": settings.editor_password},
        json={"source_word": "raditi"},
    )

    assert response.status_code == status_code
    assert response.json() == {"code": code, "message": message}
