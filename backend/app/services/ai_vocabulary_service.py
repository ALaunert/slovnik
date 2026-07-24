import logging
import unicodedata
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.config import settings
from app.models import AiVocabularyGeneration, VocabularyItem
from app.schemas import (
    AiFillExistingResponse,
    AiFillGeneratedResponse,
    AiFillPayload,
    AiFillRequest,
    StressPattern,
)
from app.services.openai_vocabulary_client import (
    PROMPT_VERSION,
    InvalidAiResponseError,
    OpenAiNotConfiguredError,
    OpenAiRateLimitedError,
    OpenAiTimeoutError,
    OpenAiUnavailableError,
    OpenAiVocabularyResult,
    generate_vocabulary,
)

logger = logging.getLogger(__name__)

CEFR_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
THEMES = {
    "greetings",
    "personal-info",
    "family-relationships",
    "home",
    "daily-life",
    "food-drink",
    "shopping-money",
    "travel-transport",
    "places-directions",
    "health-body",
    "education",
    "work",
    "free-time",
    "nature-weather",
    "services",
    "language-communication",
    "technology-media",
    "emotions-qualities",
    "time-numbers",
    "grammar-functions",
    "other",
}
REQUIRED_FIELDS = [
    "serbian_cyrillic",
    "serbian_latin",
    "russian_translation",
    "cefr_level",
    "theme",
]
STRING_FIELDS = {
    "serbian_cyrillic": 160,
    "serbian_latin": 160,
    "russian_translation": 240,
    "usage_register": 80,
    "meaning_notes": None,
    "example_sentences": None,
    "example_translations": None,
}
KNOWN_FIELDS = {*STRING_FIELDS, "cefr_level", "theme", "stress_pattern"}


class AiFillServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def normalize_source_word(value: str) -> str:
    return unicodedata.normalize("NFC", value.strip()).casefold()


def _log_context(
    normalized_source_word: str,
    error_category: str,
    request_id: str | None,
    *,
    field: str | None = None,
) -> None:
    context = {
        "normalized_source_word": normalized_source_word,
        "model": settings.openai_model,
        "prompt_version": PROMPT_VERSION,
        "error_category": error_category,
        "request_id": request_id,
    }
    if field is not None:
        context["field"] = field
    logger.warning("AI vocabulary fill validation or provider failure", extra=context)


def _validate_source_word(source_word: str) -> str:
    trimmed = source_word.strip()
    normalized = normalize_source_word(trimmed)
    has_control_character = any(
        unicodedata.category(character).startswith("C") for character in trimmed
    )
    if (
        not trimmed
        or len(trimmed) > 160
        or len(normalized) > 160
        or len(trimmed.split()) != 1
        or has_control_character
    ):
        raise AiFillServiceError(
            "invalid_source_word",
            "Enter one Serbian word up to 160 characters.",
            422,
        )
    return trimmed


def _find_existing_word(
    db: Session,
    normalized_source_word: str,
    current_word_id: int | None,
) -> VocabularyItem | None:
    words = db.scalars(select(VocabularyItem).order_by(VocabularyItem.id))
    for word in words:
        if current_word_id is not None and word.id == current_word_id:
            continue
        if normalized_source_word in {
            normalize_source_word(word.serbian_cyrillic),
            normalize_source_word(word.serbian_latin),
        }:
            return word
    return None


def _find_stored_generation(
    db: Session,
    normalized_source_word: str,
) -> AiVocabularyGeneration | None:
    return db.scalar(
        select(AiVocabularyGeneration).where(
            AiVocabularyGeneration.normalized_source_word == normalized_source_word
        )
    )


def _stored_response(
    generation: AiVocabularyGeneration,
    normalized_source_word: str,
) -> AiFillGeneratedResponse:
    try:
        stored_payload = AiFillPayload.model_validate(generation.generated_payload)
        payload = _validated_patch(
            OpenAiVocabularyResult(payload=stored_payload, request_id=None),
            normalized_source_word,
        )
    except (AiFillServiceError, ValidationError, TypeError, ValueError) as error:
        _log_context(
            normalized_source_word,
            "invalid_stored_generation",
            None,
        )
        raise AiFillServiceError(
            "invalid_ai_response",
            "Stored AI fill data is invalid.",
            502,
        ) from error
    generated_data = payload.model_dump(exclude_none=True)
    return AiFillGeneratedResponse(
        source="store",
        payload=payload,
        missing_required_fields=[
            field for field in REQUIRED_FIELDS if field not in generated_data
        ],
    )


def _trimmed_string(
    raw_payload: dict[str, Any],
    field: str,
    max_length: int | None,
    normalized_source_word: str,
    request_id: str | None,
) -> str | None:
    value = raw_payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        _log_context(
            normalized_source_word,
            "invalid_generated_field",
            request_id,
            field=field,
        )
        return None
    value = value.strip()
    if not value or (max_length is not None and len(value) > max_length):
        _log_context(
            normalized_source_word,
            "invalid_generated_field",
            request_id,
            field=field,
        )
        return None
    return value


def _stress_pattern(
    raw_stress: Any,
    patch: dict[str, Any],
    normalized_source_word: str,
    request_id: str | None,
) -> StressPattern | None:
    if raw_stress is None:
        return None
    if hasattr(raw_stress, "model_dump"):
        raw_stress = raw_stress.model_dump()
    if not isinstance(raw_stress, dict):
        _log_context(
            normalized_source_word,
            "invalid_stress_pattern",
            request_id,
        )
        return None

    cyrillic = raw_stress.get("cyrillic_syllables")
    latin = raw_stress.get("latin_syllables")
    index = raw_stress.get("stressed_syllable_index")
    valid_arrays = (
        isinstance(cyrillic, list)
        and isinstance(latin, list)
        and len(cyrillic) > 0
        and len(cyrillic) == len(latin)
        and all(isinstance(value, str) for value in [*cyrillic, *latin])
    )
    if valid_arrays:
        cyrillic = [value.strip() for value in cyrillic]
        latin = [value.strip() for value in latin]
    valid = (
        valid_arrays
        and all(cyrillic)
        and all(latin)
        and type(index) is int
        and 0 <= index < len(cyrillic)
        and "serbian_cyrillic" in patch
        and "serbian_latin" in patch
        and unicodedata.normalize("NFC", "".join(cyrillic))
        == unicodedata.normalize("NFC", patch["serbian_cyrillic"])
        and unicodedata.normalize("NFC", "".join(latin))
        == unicodedata.normalize("NFC", patch["serbian_latin"])
    )
    if not valid:
        _log_context(
            normalized_source_word,
            "invalid_stress_pattern",
            request_id,
        )
        return None
    return StressPattern(
        cyrillic_syllables=cyrillic,
        latin_syllables=latin,
        stressed_syllable_index=index,
    )


def _validated_patch(
    result: OpenAiVocabularyResult,
    normalized_source_word: str,
) -> AiFillPayload:
    raw_payload = result.payload.model_dump()
    request_id = result.request_id
    patch: dict[str, Any] = {}

    for field in raw_payload.keys() - KNOWN_FIELDS:
        _log_context(
            normalized_source_word,
            "invalid_generated_field",
            request_id,
            field=field,
        )
    for field, max_length in STRING_FIELDS.items():
        value = _trimmed_string(
            raw_payload,
            field,
            max_length,
            normalized_source_word,
            request_id,
        )
        if value is not None:
            patch[field] = value

    cefr_level = _trimmed_string(
        raw_payload,
        "cefr_level",
        None,
        normalized_source_word,
        request_id,
    )
    if cefr_level in CEFR_LEVELS:
        patch["cefr_level"] = cefr_level
    elif cefr_level is not None:
        _log_context(
            normalized_source_word,
            "invalid_generated_field",
            request_id,
            field="cefr_level",
        )

    theme = _trimmed_string(
        raw_payload,
        "theme",
        None,
        normalized_source_word,
        request_id,
    )
    if theme in THEMES:
        patch["theme"] = theme
    elif theme is not None:
        _log_context(
            normalized_source_word,
            "invalid_generated_field",
            request_id,
            field="theme",
        )

    stress = _stress_pattern(
        raw_payload.get("stress_pattern"),
        patch,
        normalized_source_word,
        request_id,
    )
    if stress is not None:
        patch["stress_pattern"] = stress

    if "russian_translation" not in patch or not {
        "serbian_cyrillic",
        "serbian_latin",
    }.intersection(patch):
        _log_context(
            normalized_source_word,
            "invalid_ai_response",
            request_id,
        )
        raise AiFillServiceError(
            "invalid_ai_response",
            "AI fill returned an invalid response.",
            502,
        )
    return AiFillPayload(**patch)


def _translate_openai_error(
    error: Exception,
    normalized_source_word: str,
) -> AiFillServiceError:
    if isinstance(error, OpenAiNotConfiguredError):
        details = ("openai_not_configured", "AI fill is not configured.", 503)
    elif isinstance(error, OpenAiRateLimitedError):
        details = ("openai_rate_limited", "AI fill is temporarily unavailable.", 503)
    elif isinstance(error, OpenAiTimeoutError):
        details = ("openai_timeout", "AI fill timed out.", 503)
    elif isinstance(error, InvalidAiResponseError):
        details = ("invalid_ai_response", "AI fill returned an invalid response.", 502)
    else:
        details = ("openai_unavailable", "AI fill is temporarily unavailable.", 503)
    _log_context(
        normalized_source_word,
        details[0],
        getattr(error, "request_id", None),
    )
    return AiFillServiceError(*details)


def _is_normalized_source_conflict(error: IntegrityError) -> bool:
    constraint_name = getattr(
        getattr(error.orig, "diag", None),
        "constraint_name",
        None,
    )
    if constraint_name == "uq_ai_vocabulary_generations_normalized_source_word":
        return True
    message = str(error.orig)
    return (
        "UNIQUE constraint failed" in message
        and "ai_vocabulary_generations.normalized_source_word" in message
    )


def fill_vocabulary(
    db: Session,
    payload: AiFillRequest,
    *,
    generate: Callable[[str], OpenAiVocabularyResult] | None = None,
) -> AiFillGeneratedResponse | AiFillExistingResponse:
    source_word = _validate_source_word(payload.source_word)
    normalized_source_word = normalize_source_word(source_word)

    existing = _find_existing_word(db, normalized_source_word, payload.current_word_id)
    if existing is not None:
        return AiFillExistingResponse(word_id=existing.id)

    stored = _find_stored_generation(db, normalized_source_word)
    if stored is not None:
        return _stored_response(stored, normalized_source_word)

    db.rollback()
    generator = generate or generate_vocabulary
    try:
        generated = generator(source_word)
    except (
        OpenAiNotConfiguredError,
        OpenAiRateLimitedError,
        OpenAiTimeoutError,
        OpenAiUnavailableError,
        InvalidAiResponseError,
    ) as error:
        raise _translate_openai_error(error, normalized_source_word) from error

    generated_payload = _validated_patch(generated, normalized_source_word)
    existing = _find_existing_word(db, normalized_source_word, payload.current_word_id)
    if existing is not None:
        return AiFillExistingResponse(word_id=existing.id)
    stored = _find_stored_generation(db, normalized_source_word)
    if stored is not None:
        return _stored_response(stored, normalized_source_word)

    generated_data = generated_payload.model_dump(exclude_none=True)
    missing_required_fields = [
        field for field in REQUIRED_FIELDS if field not in generated_data
    ]
    generation = AiVocabularyGeneration(
        source_word=source_word,
        normalized_source_word=normalized_source_word,
        generated_payload=generated_data,
        missing_required_fields=missing_required_fields,
        model=settings.openai_model,
        prompt_version=PROMPT_VERSION,
    )
    db.add(generation)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if not _is_normalized_source_conflict(error):
            raise
        stored = _find_stored_generation(db, normalized_source_word)
        if stored is None:
            raise
        return _stored_response(stored, normalized_source_word)

    return AiFillGeneratedResponse(
        source="openai",
        payload=generated_payload,
        missing_required_fields=missing_required_fields,
    )
