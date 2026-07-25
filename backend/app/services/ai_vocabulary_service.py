import logging
import math
import threading
import time
import unicodedata
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from pydantic import ValidationError

from app.config import settings
from app.models import (
    AiVocabularyGeneration,
    AiVocabularyGenerationReservation,
    VocabularyItem,
)
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
VOCABULARY_SCAN_BATCH_SIZE = 250
RESERVATION_POLL_SECONDS = 0.05
RESERVATION_LEASE_GRACE_SECONDS = 5.0
RESERVATION_HEARTBEAT_STOP_SECONDS = 0.25


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
    statement = (
        select(VocabularyItem)
        .order_by(VocabularyItem.id)
        .execution_options(yield_per=VOCABULARY_SCAN_BATCH_SIZE)
    )
    words = db.scalars(statement)
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


def _reservation_lease_seconds() -> float:
    return settings.openai_timeout_seconds + RESERVATION_LEASE_GRACE_SECONDS


def _database_now(db: Session) -> datetime:
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "postgresql":
        value = db.scalar(select(func.clock_timestamp()))
    elif dialect_name == "sqlite":
        raw_value = db.scalar(
            select(func.strftime("%Y-%m-%d %H:%M:%f", "now"))
        )
        value = datetime.fromisoformat(raw_value)
    else:
        value = db.scalar(select(func.current_timestamp()))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _reservation_expires_at(database_now: datetime) -> datetime:
    return database_now + timedelta(seconds=_reservation_lease_seconds())


def _reservation_heartbeat_interval_seconds() -> float:
    return max(
        RESERVATION_POLL_SECONDS,
        min(1.0, _reservation_lease_seconds() / 3),
    )


def _reservation_wait_deadline() -> float:
    return time.monotonic() + _reservation_lease_seconds()


def _remaining_before(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _reservation_in_progress_error()
    return remaining


def _configure_transaction_deadline(db: Session, deadline: float) -> None:
    timeout_ms = max(1, math.ceil(_remaining_before(deadline) * 1000))
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "postgresql":
        timeout = f"{timeout_ms}ms"
        db.execute(
            text("SELECT set_config('statement_timeout', :timeout, true)"),
            {"timeout": timeout},
        )
        db.execute(
            text("SELECT set_config('lock_timeout', :timeout, true)"),
            {"timeout": timeout},
        )
    elif dialect_name == "sqlite":
        db.execute(text(f"PRAGMA busy_timeout = {timeout_ms}"))


def _reservation_in_progress_error() -> AiFillServiceError:
    return AiFillServiceError(
        "ai_fill_in_progress",
        "AI fill for this word is already in progress.",
        503,
    )


def _is_reservation_conflict(error: IntegrityError) -> bool:
    constraint_name = getattr(
        getattr(error.orig, "diag", None),
        "constraint_name",
        None,
    )
    if constraint_name == "pk_ai_vocabulary_generation_reservations":
        return True
    message = str(error.orig)
    return (
        "UNIQUE constraint failed" in message
        and (
            "ai_vocabulary_generation_reservations.normalized_source_word"
            in message
        )
    )


def _is_reservation_deadline_error(error: SQLAlchemyError) -> bool:
    sqlstate = getattr(getattr(error, "orig", None), "sqlstate", None)
    if sqlstate in {"55P03", "57014"}:
        return True
    message = str(error).casefold()
    return any(
        fragment in message
        for fragment in (
            "database is locked",
            "lock timeout",
            "statement timeout",
            "canceling statement due to statement timeout",
        )
    )


def _try_acquire_reservation(
    db: Session,
    normalized_source_word: str,
    owner_token: str,
    deadline: float | None = None,
) -> bool:
    deadline = deadline if deadline is not None else _reservation_wait_deadline()
    try:
        _configure_transaction_deadline(db, deadline)
        database_now = _database_now(db)
        reservation = AiVocabularyGenerationReservation(
            normalized_source_word=normalized_source_word,
            owner_token=owner_token,
            expires_at=_reservation_expires_at(database_now),
        )
        db.add(reservation)
        db.commit()
        return True
    except IntegrityError as error:
        db.rollback()
        if not _is_reservation_conflict(error):
            raise
    except SQLAlchemyError as error:
        db.rollback()
        if not _is_reservation_deadline_error(error):
            raise
        _remaining_before(deadline)
        return False

    try:
        _configure_transaction_deadline(db, deadline)
        database_now = _database_now(db)
        takeover = db.execute(
            update(AiVocabularyGenerationReservation)
            .where(
                AiVocabularyGenerationReservation.normalized_source_word
                == normalized_source_word,
                AiVocabularyGenerationReservation.expires_at <= database_now,
            )
            .values(
                owner_token=owner_token,
                expires_at=_reservation_expires_at(database_now),
                updated_at=database_now,
            )
        )
        if takeover.rowcount == 1:
            db.commit()
            return True
        db.rollback()
        return False
    except SQLAlchemyError as error:
        db.rollback()
        if not _is_reservation_deadline_error(error):
            raise
        _remaining_before(deadline)
        return False


class _ReservationHeartbeat:
    def __init__(
        self,
        db: Session,
        normalized_source_word: str,
        owner_token: str,
    ):
        bind = db.get_bind()
        self._session_factory = sessionmaker(
            bind=getattr(bind, "engine", bind),
            autoflush=False,
            expire_on_commit=False,
        )
        self._normalized_source_word = normalized_source_word
        self._owner_token = owner_token
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="ai-vocabulary-reservation-heartbeat",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def request_stop(self) -> None:
        self._stop_event.set()

    def wait(self, *, deadline: float) -> bool:
        if self._thread.ident is None:
            return True
        self._thread.join(timeout=max(0.0, deadline - time.monotonic()))
        return not self._thread.is_alive()

    def stop(self, *, deadline: float) -> bool:
        self.request_stop()
        return self.wait(deadline=deadline)

    def _run(self) -> None:
        interval = _reservation_heartbeat_interval_seconds()
        while not self._stop_event.wait(interval):
            try:
                with self._session_factory() as heartbeat_db:
                    operation_deadline = (
                        time.monotonic()
                        + _reservation_heartbeat_interval_seconds()
                    )
                    _configure_transaction_deadline(
                        heartbeat_db,
                        operation_deadline,
                    )
                    database_now = _database_now(heartbeat_db)
                    renewal = heartbeat_db.execute(
                        update(AiVocabularyGenerationReservation)
                        .where(
                            AiVocabularyGenerationReservation.normalized_source_word
                            == self._normalized_source_word,
                            AiVocabularyGenerationReservation.owner_token
                            == self._owner_token,
                        )
                        .values(
                            expires_at=_reservation_expires_at(database_now),
                            updated_at=database_now,
                        )
                    )
                    heartbeat_db.commit()
                    if renewal.rowcount != 1:
                        return
            except (AiFillServiceError, SQLAlchemyError):
                logger.exception(
                    "Failed to renew AI vocabulary generation reservation",
                    extra={
                        "normalized_source_word": self._normalized_source_word,
                    },
                )


def _fence_reservation_owner(
    db: Session,
    normalized_source_word: str,
    owner_token: str,
) -> bool:
    database_now = _database_now(db)
    fence = db.execute(
        update(AiVocabularyGenerationReservation)
        .where(
            AiVocabularyGenerationReservation.normalized_source_word
            == normalized_source_word,
            AiVocabularyGenerationReservation.owner_token == owner_token,
        )
        .values(
            expires_at=_reservation_expires_at(database_now),
            updated_at=database_now,
        )
    )
    return fence.rowcount == 1


def _wait_for_stored_generation(
    db: Session,
    normalized_source_word: str,
    deadline: float,
) -> AiFillGeneratedResponse:
    while True:
        stored = _find_stored_generation(db, normalized_source_word)
        if stored is not None:
            return _stored_response(stored, normalized_source_word)
        db.rollback()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _reservation_in_progress_error()
        time.sleep(min(RESERVATION_POLL_SECONDS, remaining))


def _release_reservation(
    db: Session,
    normalized_source_word: str,
    owner_token: str,
    deadline: float,
) -> None:
    try:
        db.rollback()
        _configure_transaction_deadline(db, deadline)
        db.execute(
            delete(AiVocabularyGenerationReservation).where(
                AiVocabularyGenerationReservation.normalized_source_word
                == normalized_source_word,
                AiVocabularyGenerationReservation.owner_token == owner_token,
            )
        )
        _remaining_before(deadline)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to release AI vocabulary generation reservation",
            extra={"normalized_source_word": normalized_source_word},
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

    owner_token = str(uuid4())
    reservation_wait_deadline = _reservation_wait_deadline()
    while not _try_acquire_reservation(
        db,
        normalized_source_word,
        owner_token,
        reservation_wait_deadline,
    ):
        stored = _find_stored_generation(db, normalized_source_word)
        if stored is not None:
            return _stored_response(stored, normalized_source_word)
        db.rollback()
        remaining = reservation_wait_deadline - time.monotonic()
        if remaining <= 0:
            raise _reservation_in_progress_error()
        time.sleep(min(RESERVATION_POLL_SECONDS, remaining))

    reservation_owned = True
    heartbeat = _ReservationHeartbeat(
        db,
        normalized_source_word,
        owner_token,
    )
    try:
        heartbeat.start()
        existing = _find_existing_word(
            db,
            normalized_source_word,
            payload.current_word_id,
        )
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
        existing = _find_existing_word(
            db,
            normalized_source_word,
            payload.current_word_id,
        )
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
        try:
            if not _fence_reservation_owner(
                db,
                normalized_source_word,
                owner_token,
            ):
                db.rollback()
                reservation_owned = False
                return _wait_for_stored_generation(
                    db,
                    normalized_source_word,
                    reservation_wait_deadline,
                )
            db.add(generation)
            db.flush()
            release = db.execute(
                delete(AiVocabularyGenerationReservation).where(
                    AiVocabularyGenerationReservation.normalized_source_word
                    == normalized_source_word,
                    AiVocabularyGenerationReservation.owner_token == owner_token,
                )
            )
            if release.rowcount != 1:
                db.rollback()
                reservation_owned = False
                return _wait_for_stored_generation(
                    db,
                    normalized_source_word,
                    reservation_wait_deadline,
                )
            db.commit()
            reservation_owned = False
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
    finally:
        cleanup_deadline = (
            time.monotonic() + RESERVATION_HEARTBEAT_STOP_SECONDS
        )
        heartbeat.request_stop()
        if reservation_owned:
            _release_reservation(
                db,
                normalized_source_word,
                owner_token,
                cleanup_deadline,
            )
        stopped = heartbeat.wait(deadline=cleanup_deadline)
        if not stopped:
            logger.warning(
                "AI vocabulary reservation heartbeat did not stop before deadline",
                extra={"normalized_source_word": normalized_source_word},
            )
