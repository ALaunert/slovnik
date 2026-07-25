import logging
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import Base
from app.models import (
    AiVocabularyGeneration,
    AiVocabularyGenerationReservation,
    VocabularyItem,
)
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
        SimpleNamespace(openai_model="test-model", openai_timeout_seconds=1),
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


@pytest.mark.parametrize(
    "source_word",
    ["", "   ", "dve reči", "x" * 161, "\x00raditi", "İ" * 160],
)
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


def test_duplicate_lookup_streams_vocabulary_rows():
    word = SimpleNamespace(
        id=7,
        serbian_cyrillic=unicodedata.normalize("NFD", "РАДИТИ"),
        serbian_latin="drugo",
    )
    words = MagicMock()
    words.__iter__.return_value = iter([word])
    db = Mock()
    db.scalars.return_value = words

    result = ai_vocabulary_service._find_existing_word(db, "радити", None)

    assert result is word
    statement = db.scalars.call_args.args[0]
    assert statement.get_execution_options()["yield_per"] == (
        ai_vocabulary_service.VOCABULARY_SCAN_BATCH_SIZE
    )


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


def test_concurrent_requests_share_one_provider_call(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'concurrent-ai-fill.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    provider_entered = threading.Event()
    second_request_waiting = threading.Event()
    release_provider = threading.Event()
    provider_lock = threading.Lock()
    provider_call_count = 0
    acquire_reservation = ai_vocabulary_service._try_acquire_reservation

    def tracked_acquire_reservation(*args):
        acquired = acquire_reservation(*args)
        if not acquired:
            second_request_waiting.set()
        return acquired

    monkeypatch.setattr(
        ai_vocabulary_service,
        "_try_acquire_reservation",
        tracked_acquire_reservation,
    )

    def generate(_):
        nonlocal provider_call_count
        with provider_lock:
            provider_call_count += 1
        provider_entered.set()
        assert release_provider.wait(timeout=3)
        return generated_result()

    def fill(source_word):
        with SessionFactory() as session:
            return fill_vocabulary(
                session,
                AiFillRequest(source_word=source_word),
                generate=generate,
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(fill, "Raditi")
            assert provider_entered.wait(timeout=3)
            second = executor.submit(fill, " raditi ")
            assert second_request_waiting.wait(timeout=3)
            assert provider_call_count == 1
            release_provider.set()
            results = [first.result(timeout=3), second.result(timeout=3)]
    finally:
        release_provider.set()
        engine.dispose()

    assert {result.source for result in results} == {"openai", "store"}
    assert all(result.payload.serbian_latin == "raditi" for result in results)


def test_heartbeat_prevents_takeover_during_long_provider_call(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'long-ai-fill.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    monkeypatch.setattr(
        ai_vocabulary_service,
        "settings",
        SimpleNamespace(openai_model="test-model", openai_timeout_seconds=0.05),
    )
    monkeypatch.setattr(
        ai_vocabulary_service,
        "RESERVATION_LEASE_GRACE_SECONDS",
        0.05,
    )
    monkeypatch.setattr(ai_vocabulary_service, "RESERVATION_POLL_SECONDS", 0.01)
    provider_entered = threading.Event()
    provider_lock = threading.Lock()
    provider_call_count = 0

    def generate(_):
        nonlocal provider_call_count
        with provider_lock:
            provider_call_count += 1
        provider_entered.set()
        threading.Event().wait(0.18)
        return generated_result()

    def fill():
        with SessionFactory() as session:
            return fill_vocabulary(
                session,
                AiFillRequest(source_word="raditi"),
                generate=generate,
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(fill)
            assert provider_entered.wait(timeout=1)
            threading.Event().wait(0.12)
            second = executor.submit(fill)
            results = [first.result(timeout=3), second.result(timeout=3)]
    finally:
        engine.dispose()

    assert provider_call_count == 1
    assert {result.source for result in results} == {"openai", "store"}
    assert not any(
        thread.name == "ai-vocabulary-reservation-heartbeat" and thread.is_alive()
        for thread in threading.enumerate()
    )


def test_heartbeat_prevents_takeover_during_post_acquisition_scan(
    tmp_path,
    monkeypatch,
):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'post-acquisition-scan.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    monkeypatch.setattr(
        ai_vocabulary_service,
        "settings",
        SimpleNamespace(openai_model="test-model", openai_timeout_seconds=0.05),
    )
    monkeypatch.setattr(
        ai_vocabulary_service,
        "RESERVATION_LEASE_GRACE_SECONDS",
        0.05,
    )
    monkeypatch.setattr(ai_vocabulary_service, "RESERVATION_POLL_SECONDS", 0.01)
    scan_entered = threading.Event()
    release_scan = threading.Event()
    provider_entered = threading.Event()
    two_provider_calls = threading.Event()
    release_provider = threading.Event()
    call_lock = threading.Lock()
    find_call_count = 0
    provider_call_count = 0
    original_find = ai_vocabulary_service._find_existing_word

    def blocked_post_acquisition_scan(*args, **kwargs):
        nonlocal find_call_count
        with call_lock:
            find_call_count += 1
            call_number = find_call_count
        if call_number == 2:
            scan_entered.set()
            assert release_scan.wait(timeout=3)
        return original_find(*args, **kwargs)

    monkeypatch.setattr(
        ai_vocabulary_service,
        "_find_existing_word",
        blocked_post_acquisition_scan,
    )

    def generate(_):
        nonlocal provider_call_count
        with call_lock:
            provider_call_count += 1
            if provider_call_count == 2:
                two_provider_calls.set()
        provider_entered.set()
        assert release_provider.wait(timeout=3)
        return generated_result()

    def fill():
        with SessionFactory() as session:
            return fill_vocabulary(
                session,
                AiFillRequest(source_word="raditi"),
                generate=generate,
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(fill)
            assert scan_entered.wait(timeout=1)
            threading.Event().wait(0.12)
            second = executor.submit(fill)
            takeover_reached_provider = provider_entered.wait(timeout=0.05)
            release_scan.set()
            assert provider_entered.wait(timeout=1)
            if takeover_reached_provider:
                assert two_provider_calls.wait(timeout=1)
            release_provider.set()
            results = [first.result(timeout=3), second.result(timeout=3)]
    finally:
        release_scan.set()
        release_provider.set()
        engine.dispose()

    assert not takeover_reached_provider
    assert provider_call_count == 1
    assert {result.source for result in results} == {"openai", "store"}


def test_heartbeat_prevents_takeover_during_validation(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'validation-ai-fill.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    monkeypatch.setattr(
        ai_vocabulary_service,
        "settings",
        SimpleNamespace(openai_model="test-model", openai_timeout_seconds=0.05),
    )
    monkeypatch.setattr(
        ai_vocabulary_service,
        "RESERVATION_LEASE_GRACE_SECONDS",
        0.05,
    )
    monkeypatch.setattr(ai_vocabulary_service, "RESERVATION_POLL_SECONDS", 0.01)
    validation_entered = threading.Event()
    release_validation = threading.Event()
    second_acquisition_entered = threading.Event()
    second_provider_entered = threading.Event()
    provider_lock = threading.Lock()
    provider_call_count = 0
    validation_call_count = 0
    original_validate = ai_vocabulary_service._validated_patch
    original_acquire = ai_vocabulary_service._try_acquire_reservation

    def tracked_acquire(*args, **kwargs):
        if validation_entered.is_set():
            second_acquisition_entered.set()
        return original_acquire(*args, **kwargs)

    def blocked_validation(*args, **kwargs):
        nonlocal validation_call_count
        validation_call_count += 1
        if validation_call_count == 1:
            validation_entered.set()
            assert release_validation.wait(timeout=3)
        return original_validate(*args, **kwargs)

    monkeypatch.setattr(
        ai_vocabulary_service,
        "_try_acquire_reservation",
        tracked_acquire,
    )
    monkeypatch.setattr(
        ai_vocabulary_service,
        "_validated_patch",
        blocked_validation,
    )

    def generate(_):
        nonlocal provider_call_count
        with provider_lock:
            provider_call_count += 1
            if provider_call_count > 1:
                second_provider_entered.set()
        return generated_result()

    def fill():
        with SessionFactory() as session:
            return fill_vocabulary(
                session,
                AiFillRequest(source_word="raditi"),
                generate=generate,
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(fill)
            assert validation_entered.wait(timeout=1)
            threading.Event().wait(0.12)
            second = executor.submit(fill)
            assert second_acquisition_entered.wait(timeout=1)
            assert not second_provider_entered.wait(timeout=0.05)
            release_validation.set()
            results = [first.result(timeout=3), second.result(timeout=3)]
    finally:
        release_validation.set()
        engine.dispose()

    assert provider_call_count == 1
    assert {result.source for result in results} == {"openai", "store"}


def test_heartbeat_uses_engine_for_connection_bound_request_session(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'heartbeat-bind.db'}",
        connect_args={"check_same_thread": False},
    )
    try:
        with engine.connect() as connection:
            RequestSession = sessionmaker(bind=connection)
            with RequestSession() as session:
                heartbeat = ai_vocabulary_service._ReservationHeartbeat(
                    session,
                    "raditi",
                    "owner-token",
                )

                assert heartbeat._session_factory.kw["bind"] is engine
    finally:
        engine.dispose()


def test_heartbeat_stop_is_bounded_when_database_operation_blocks(
    db_session,
    monkeypatch,
):
    operation_entered = threading.Event()
    release_operation = threading.Event()

    class BlockingHeartbeatSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

        def scalar(self, *_args, **_kwargs):
            operation_entered.set()
            assert release_operation.wait(timeout=3)
            return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

        def execute(self, *_args, **_kwargs):
            operation_entered.set()
            assert release_operation.wait(timeout=3)
            return SimpleNamespace(rowcount=1)

        def commit(self):
            pass

        def rollback(self):
            pass

    heartbeat = ai_vocabulary_service._ReservationHeartbeat(
        db_session,
        "raditi",
        "owner-token",
    )
    heartbeat._session_factory = BlockingHeartbeatSession
    monkeypatch.setattr(ai_vocabulary_service, "RESERVATION_POLL_SECONDS", 0.001)
    monkeypatch.setattr(
        ai_vocabulary_service,
        "_reservation_heartbeat_interval_seconds",
        lambda: 0.001,
    )
    heartbeat.start()
    assert operation_entered.wait(timeout=1)

    started_at = time.monotonic()
    try:
        stopped = heartbeat.stop(deadline=started_at + 0.03)
    finally:
        release_operation.set()
        heartbeat._thread.join(timeout=1)

    assert not stopped
    assert time.monotonic() - started_at < 0.2


def test_cleanup_is_bounded_when_reservation_delete_is_locked(
    tmp_path,
    monkeypatch,
):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'locked-cleanup.db'}",
        connect_args={"check_same_thread": False, "timeout": 1},
    )
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    monkeypatch.setattr(
        ai_vocabulary_service,
        "settings",
        SimpleNamespace(openai_model="test-model", openai_timeout_seconds=0.5),
    )
    monkeypatch.setattr(
        ai_vocabulary_service,
        "RESERVATION_LEASE_GRACE_SECONDS",
        0.5,
    )
    monkeypatch.setattr(
        ai_vocabulary_service,
        "RESERVATION_HEARTBEAT_STOP_SECONDS",
        0.05,
    )
    locker = engine.connect()
    lock_transaction = None

    def generate(_):
        nonlocal lock_transaction
        lock_transaction = locker.begin()
        locker.execute(
            text(
                """
                UPDATE ai_vocabulary_generation_reservations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE normalized_source_word = 'raditi'
                """
            )
        )
        raise ai_vocabulary_service.OpenAiUnavailableError("provider failed")

    started_at = time.monotonic()
    try:
        with SessionFactory() as session:
            with pytest.raises(AiFillServiceError) as caught:
                fill_vocabulary(
                    session,
                    AiFillRequest(source_word="raditi"),
                    generate=generate,
                )
    finally:
        elapsed = time.monotonic() - started_at
        if lock_transaction is not None:
            lock_transaction.rollback()
        locker.close()
        engine.dispose()

    assert caught.value.code == "openai_unavailable"
    assert elapsed < 0.3


def test_openai_call_runs_without_an_open_database_transaction(db_session):
    def generate(_):
        assert not db_session.in_transaction()
        return generated_result()

    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi"),
        generate=generate,
    )

    assert result.source == "openai"


def test_reservation_takeover_uses_database_clock(db_session, monkeypatch):
    database_now = db_session.scalar(select(func.current_timestamp()))
    db_session.add(
        AiVocabularyGenerationReservation(
            normalized_source_word="raditi",
            owner_token="current-owner",
            expires_at=database_now + timedelta(seconds=30),
        )
    )
    db_session.commit()

    class SkewedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return super().now(tz) + timedelta(hours=1)

    monkeypatch.setattr(ai_vocabulary_service, "datetime", SkewedDateTime)

    acquired = ai_vocabulary_service._try_acquire_reservation(
        db_session,
        "raditi",
        "skewed-owner",
    )

    assert not acquired
    db_session.expire_all()
    reservation = db_session.get(AiVocabularyGenerationReservation, "raditi")
    assert reservation.owner_token == "current-owner"


def test_reservation_acquisition_stops_at_database_lock_deadline(
    tmp_path,
    monkeypatch,
):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'locked-reservation.db'}",
        connect_args={"check_same_thread": False, "timeout": 1},
    )
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    monkeypatch.setattr(
        ai_vocabulary_service,
        "settings",
        SimpleNamespace(openai_model="test-model", openai_timeout_seconds=0.03),
    )
    monkeypatch.setattr(
        ai_vocabulary_service,
        "RESERVATION_LEASE_GRACE_SECONDS",
        0.02,
    )
    provider = Mock(side_effect=AssertionError("OpenAI must not run"))

    locker = engine.connect()
    transaction = locker.begin()
    locker.execute(
        text(
            """
            INSERT INTO ai_vocabulary_generation_reservations (
                normalized_source_word,
                owner_token,
                expires_at
            ) VALUES (
                'locked-word',
                'locked-owner',
                CURRENT_TIMESTAMP
            )
            """
        )
    )
    started_at = time.monotonic()
    try:
        with SessionFactory() as session:
            with pytest.raises(AiFillServiceError) as caught:
                fill_vocabulary(
                    session,
                    AiFillRequest(source_word="raditi"),
                    generate=provider,
                )
    finally:
        transaction.rollback()
        locker.close()
        engine.dispose()

    assert caught.value.code == "ai_fill_in_progress"
    assert caught.value.status_code == 503
    assert time.monotonic() - started_at < 0.3
    provider.assert_not_called()


def test_lost_owner_cannot_persist_generated_payload(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'fenced-ai-fill.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    monkeypatch.setattr(
        ai_vocabulary_service,
        "settings",
        SimpleNamespace(openai_model="test-model", openai_timeout_seconds=0.01),
    )
    monkeypatch.setattr(
        ai_vocabulary_service,
        "RESERVATION_LEASE_GRACE_SECONDS",
        0.01,
    )
    monkeypatch.setattr(ai_vocabulary_service, "RESERVATION_POLL_SECONDS", 0.001)

    def generate(_):
        with SessionFactory() as competing_session:
            competing_session.execute(
                update(AiVocabularyGenerationReservation)
                .where(
                    AiVocabularyGenerationReservation.normalized_source_word
                    == "raditi"
                )
                .values(
                    owner_token="new-owner",
                    expires_at=datetime.now(timezone.utc) + timedelta(seconds=30),
                )
            )
            competing_session.commit()
        return generated_result()

    try:
        with SessionFactory() as session:
            with pytest.raises(AiFillServiceError) as caught:
                fill_vocabulary(
                    session,
                    AiFillRequest(source_word="raditi"),
                    generate=generate,
                )
            generation_count = session.scalar(
                select(func.count(AiVocabularyGeneration.id))
            )
    finally:
        engine.dispose()

    assert caught.value.code == "ai_fill_in_progress"
    assert caught.value.status_code == 503
    assert generation_count == 0


def test_waiter_stops_at_monotonic_deadline(db_session, monkeypatch):
    acquire_calls = 0

    def never_acquire(*_):
        nonlocal acquire_calls
        acquire_calls += 1
        if acquire_calls > 2:
            raise AssertionError("reservation polling ignored its deadline")
        return False

    monkeypatch.setattr(
        ai_vocabulary_service,
        "_try_acquire_reservation",
        never_acquire,
    )
    monkeypatch.setattr(
        ai_vocabulary_service.time,
        "monotonic",
        Mock(side_effect=[100.0, 107.0]),
    )
    monkeypatch.setattr(ai_vocabulary_service.time, "sleep", Mock())

    with pytest.raises(AiFillServiceError) as caught:
        fill_vocabulary(
            db_session,
            AiFillRequest(source_word="raditi"),
            generate=Mock(side_effect=AssertionError("OpenAI must not run")),
        )

    assert caught.value.code == "ai_fill_in_progress"
    assert caught.value.message == "AI fill for this word is already in progress."
    assert caught.value.status_code == 503
    assert acquire_calls == 1


def test_provider_failure_releases_reservation_and_allows_retry(db_session):
    with pytest.raises(AiFillServiceError):
        fill_vocabulary(
            db_session,
            AiFillRequest(source_word="raditi"),
            generate=Mock(
                side_effect=ai_vocabulary_service.OpenAiUnavailableError("provider failed")
            ),
        )

    reservation_count = db_session.scalar(
        text("SELECT count(*) FROM ai_vocabulary_generation_reservations")
    )
    assert reservation_count == 0

    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi"),
        generate=lambda _: generated_result(),
    )

    assert result.source == "openai"


def test_stale_reservation_is_reclaimed_and_removed(db_session):
    expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.execute(
        text(
            """
            INSERT INTO ai_vocabulary_generation_reservations (
                normalized_source_word,
                owner_token,
                expires_at,
                created_at,
                updated_at
            ) VALUES (
                :normalized_source_word,
                :owner_token,
                :expires_at,
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "normalized_source_word": "raditi",
            "owner_token": "crashed-worker",
            "expires_at": expired_at,
            "created_at": expired_at,
            "updated_at": expired_at,
        },
    )
    db_session.commit()

    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi"),
        generate=lambda _: generated_result(),
    )

    assert result.source == "openai"
    assert (
        db_session.scalar(
            text("SELECT count(*) FROM ai_vocabulary_generation_reservations")
        )
        == 0
    )


def test_vocabulary_created_during_generation_wins_before_persistence(db_session):
    def generate(_):
        existing = add_word(db_session)
        return generated_result(request_id=f"word-{existing.id}")

    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi"),
        generate=generate,
    )

    assert result.status == "already_exists"
    assert db_session.scalar(select(func.count(AiVocabularyGeneration.id))) == 0


def test_store_row_created_during_generation_is_reused(db_session):
    def generate(_):
        add_generation(db_session)
        return generated_result()

    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi"),
        generate=generate,
    )

    assert result.source == "store"
    assert db_session.scalar(select(func.count(AiVocabularyGeneration.id))) == 1


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


def test_autoflush_integrity_race_returns_concurrent_store_row(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'autoflush-race.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=True)
    original_find_stored = ai_vocabulary_service._find_stored_generation
    lookup_count = 0

    def hide_concurrent_store_until_integrity_error(db, normalized_source_word):
        nonlocal lookup_count
        lookup_count += 1
        if lookup_count <= 3:
            return None
        return original_find_stored(db, normalized_source_word)

    monkeypatch.setattr(
        ai_vocabulary_service,
        "_find_stored_generation",
        hide_concurrent_store_until_integrity_error,
    )

    def generate(_):
        with SessionFactory() as competing_session:
            add_generation(competing_session)
        return generated_result()

    try:
        with SessionFactory() as session:
            result = fill_vocabulary(
                session,
                AiFillRequest(source_word="raditi"),
                generate=generate,
            )
            generation_count = session.scalar(
                select(func.count(AiVocabularyGeneration.id))
            )
    finally:
        engine.dispose()

    assert result.source == "store"
    assert result.payload.serbian_latin == "raditi"
    assert generation_count == 1


def test_non_unique_integrity_error_is_not_misclassified(db_session, monkeypatch):
    monkeypatch.setattr(
        ai_vocabulary_service,
        "settings",
        SimpleNamespace(
            openai_model=None,
            openai_timeout_seconds=1,
        ),
    )

    with pytest.raises(IntegrityError, match="NOT NULL constraint failed"):
        fill_vocabulary(
            db_session,
            AiFillRequest(source_word="raditi"),
            generate=lambda _: generated_result(),
        )


def test_invalid_stored_payload_returns_stable_error(db_session):
    add_generation(
        db_session,
        generated_payload={
            "serbian_latin": ["not", "a", "string"],
            "russian_translation": "делать",
        },
    )

    with pytest.raises(AiFillServiceError) as caught:
        fill_vocabulary(
            db_session,
            AiFillRequest(source_word="raditi"),
            generate=Mock(side_effect=AssertionError("OpenAI must not run")),
        )

    assert (caught.value.code, caught.value.status_code) == ("invalid_ai_response", 502)


def test_stored_payload_revalidates_and_drops_invalid_stress(db_session):
    add_generation(
        db_session,
        generated_payload={
            "serbian_cyrillic": "радити",
            "serbian_latin": "raditi",
            "russian_translation": "делать",
            "stress_pattern": {
                "cyrillic_syllables": ["не", "ваља"],
                "latin_syllables": ["ra", "di", "ti"],
                "stressed_syllable_index": 0,
            },
        },
    )

    result = fill_vocabulary(
        db_session,
        AiFillRequest(source_word="raditi"),
        generate=Mock(side_effect=AssertionError("OpenAI must not run")),
    )

    assert result.source == "store"
    assert result.payload.stress_pattern is None


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
