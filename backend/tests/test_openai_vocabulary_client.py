from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ContentFilterFinishReasonError,
    LengthFinishReasonError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import ValidationError

from app.services import openai_vocabulary_client as client_module
from app.services.openai_vocabulary_client import (
    InvalidAiResponseError,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    OpenAiNotConfiguredError,
    OpenAiRateLimitedError,
    OpenAiTimeoutError,
    OpenAiUnavailableError,
    OpenAiVocabularyResult,
    RawAiVocabulary,
    RawStressPattern,
    generate_vocabulary,
)


TOP_LEVEL_FIELDS = {
    "serbian_cyrillic",
    "serbian_latin",
    "russian_translation",
    "cefr_level",
    "theme",
    "usage_register",
    "stress_pattern",
    "meaning_notes",
    "example_sentences",
    "example_translations",
}

CONTROLLED_THEMES = {
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


def _allows_null(property_schema):
    return any(option.get("type") == "null" for option in property_schema["anyOf"])


def _raw_vocabulary():
    return RawAiVocabulary(
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


def _http_response(status_code, request_id):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    return httpx.Response(
        status_code,
        request=request,
        headers={"x-request-id": request_id},
    )


def test_raw_vocabulary_schema_requires_every_nullable_known_field():
    schema = RawAiVocabulary.model_json_schema()

    assert PROMPT_VERSION == "v1"
    assert set(schema["required"]) == TOP_LEVEL_FIELDS
    assert schema["additionalProperties"] is False
    assert all(_allows_null(field_schema) for field_schema in schema["properties"].values())
    assert schema["properties"]["cefr_level"]["anyOf"][0]["enum"] == [
        "A1",
        "A2",
        "B1",
        "B2",
        "C1",
        "C2",
    ]
    assert set(schema["properties"]["theme"]["anyOf"][0]["enum"]) == CONTROLLED_THEMES


def test_raw_stress_schema_requires_every_nullable_known_field():
    schema = RawStressPattern.model_json_schema()

    assert set(schema["required"]) == {
        "cyrillic_syllables",
        "latin_syllables",
        "stressed_syllable_index",
    }
    assert schema["additionalProperties"] is False
    assert all(_allows_null(field_schema) for field_schema in schema["properties"].values())


def test_raw_vocabulary_has_no_defaults_for_nullable_fields():
    with pytest.raises(ValidationError):
        RawAiVocabulary()


def test_generate_uses_responses_parse_with_exact_structured_request(monkeypatch):
    monkeypatch.setattr(client_module.settings, "openai_model", "test-model")
    parsed = _raw_vocabulary()
    responses = SimpleNamespace(
        parse=Mock(
            return_value=SimpleNamespace(
                output_parsed=parsed,
                _request_id="req_123",
            )
        )
    )

    result = generate_vocabulary("raditi", client=SimpleNamespace(responses=responses))

    assert result == OpenAiVocabularyResult(payload=parsed, request_id="req_123")
    responses.parse.assert_called_once_with(
        model="test-model",
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "raditi"},
        ],
        text_format=RawAiVocabulary,
        store=False,
    )
    with pytest.raises(FrozenInstanceError):
        result.request_id = "changed"


def test_prompt_contains_required_vocabulary_constraints():
    prompt = " ".join(SYSTEM_PROMPT.casefold().split())

    assert "one serbian word" in prompt
    assert "russian-speaking learner" in prompt
    assert "vocabulary card draft" in prompt
    assert "null" in prompt
    assert "cyrillic" in prompt
    assert "latin" in prompt
    assert "syllable" in prompt
    assert "shared zero-based" in prompt
    assert "phrase" in prompt
    assert "list of alternatives" in prompt


def test_missing_api_key_does_not_construct_or_call_sdk(monkeypatch, caplog):
    openai_constructor = Mock()
    monkeypatch.setattr(client_module.settings, "openai_api_key", "  ")
    monkeypatch.setattr(client_module, "OpenAI", openai_constructor)

    with caplog.at_level("WARNING"), pytest.raises(OpenAiNotConfiguredError):
        generate_vocabulary("raditi")

    openai_constructor.assert_not_called()
    assert caplog.records[-1].category == "not_configured"


def test_blank_model_does_not_construct_or_call_sdk(monkeypatch, caplog):
    openai_constructor = Mock()
    monkeypatch.setattr(client_module.settings, "openai_api_key", "configured-key")
    monkeypatch.setattr(client_module.settings, "openai_model", "  ")
    monkeypatch.setattr(client_module, "OpenAI", openai_constructor)

    with caplog.at_level("WARNING"), pytest.raises(OpenAiNotConfiguredError):
        generate_vocabulary("raditi")

    openai_constructor.assert_not_called()
    assert caplog.records[-1].category == "not_configured"


def test_default_client_uses_configured_key_and_timeout(monkeypatch):
    parsed = _raw_vocabulary()
    sdk_client = SimpleNamespace(
        responses=SimpleNamespace(
            parse=Mock(
                return_value=SimpleNamespace(output_parsed=parsed, _request_id=None),
            ),
        ),
    )
    openai_constructor = Mock(return_value=sdk_client)
    monkeypatch.setattr(client_module.settings, "openai_api_key", "configured-key")
    monkeypatch.setattr(client_module.settings, "openai_timeout_seconds", 31.0)
    monkeypatch.setattr(client_module, "OpenAI", openai_constructor)

    generate_vocabulary("raditi")

    openai_constructor.assert_called_once_with(
        api_key="configured-key",
        timeout=31.0,
        max_retries=0,
    )


def test_generation_prevents_openai_sdk_debug_payload_logging():
    sdk_logger = client_module.sdk_logger
    previous_level = sdk_logger.level
    sdk_logger.setLevel("DEBUG")
    try:
        responses = SimpleNamespace(
            parse=Mock(
                return_value=SimpleNamespace(
                    output_parsed=_raw_vocabulary(),
                    _request_id=None,
                )
            )
        )

        generate_vocabulary("source-word-must-not-be-debug-logged", client=SimpleNamespace(responses=responses))

        assert sdk_logger.getEffectiveLevel() >= client_module.logging.INFO
    finally:
        sdk_logger.setLevel(previous_level)


@pytest.mark.parametrize(
    ("sdk_error", "expected_error", "category", "request_id"),
    [
        (
            AuthenticationError(
                "authentication failed",
                response=_http_response(401, "req_auth"),
                body=None,
            ),
            OpenAiNotConfiguredError,
            "authentication",
            "req_auth",
        ),
        (
            BadRequestError(
                "invalid model",
                response=_http_response(400, "req_bad_model"),
                body=None,
            ),
            OpenAiNotConfiguredError,
            "configuration",
            "req_bad_model",
        ),
        (
            PermissionDeniedError(
                "model access denied",
                response=_http_response(403, "req_permission"),
                body=None,
            ),
            OpenAiNotConfiguredError,
            "configuration",
            "req_permission",
        ),
        (
            NotFoundError(
                "model not found",
                response=_http_response(404, "req_not_found"),
                body=None,
            ),
            OpenAiNotConfiguredError,
            "configuration",
            "req_not_found",
        ),
        (
            RateLimitError(
                "rate limited",
                response=_http_response(429, "req_rate"),
                body=None,
            ),
            OpenAiRateLimitedError,
            "rate_limited",
            "req_rate",
        ),
        (
            APITimeoutError(httpx.Request("POST", "https://api.openai.com/v1/responses")),
            OpenAiTimeoutError,
            "timeout",
            None,
        ),
        (
            APIConnectionError(
                request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
            ),
            OpenAiUnavailableError,
            "connection",
            None,
        ),
        (
            APIStatusError(
                "unavailable",
                response=_http_response(503, "req_status"),
                body=None,
            ),
            OpenAiUnavailableError,
            "api_status",
            "req_status",
        ),
    ],
)
def test_sdk_errors_map_to_typed_client_errors(
    sdk_error,
    expected_error,
    category,
    request_id,
    caplog,
):
    responses = SimpleNamespace(parse=Mock(side_effect=sdk_error))

    with caplog.at_level("WARNING"), pytest.raises(expected_error) as exc_info:
        generate_vocabulary("raditi", client=SimpleNamespace(responses=responses))

    assert exc_info.value.request_id == request_id
    assert caplog.records[-1].category == category
    assert caplog.records[-1].model == client_module.settings.openai_model
    assert caplog.records[-1].prompt_version == PROMPT_VERSION
    if request_id is None:
        assert not hasattr(caplog.records[-1], "request_id")
    else:
        assert caplog.records[-1].request_id == request_id


@pytest.mark.parametrize(
    ("output", "category"),
    [
        (
            [
                SimpleNamespace(
                    content=[SimpleNamespace(type="refusal", refusal="Cannot comply")],
                ),
            ],
            "refusal",
        ),
        ([], "unparsed"),
    ],
)
def test_refusal_and_unparsed_output_map_to_invalid_response(output, category, caplog):
    response = SimpleNamespace(
        output_parsed=None,
        output=output,
        _request_id="req_invalid",
    )
    responses = SimpleNamespace(parse=Mock(return_value=response))

    with caplog.at_level("WARNING"), pytest.raises(InvalidAiResponseError) as exc_info:
        generate_vocabulary("raditi", client=SimpleNamespace(responses=responses))

    assert exc_info.value.request_id == "req_invalid"
    assert caplog.records[-1].category == category
    assert caplog.records[-1].request_id == "req_invalid"


def test_parse_validation_error_maps_to_invalid_response(caplog):
    with pytest.raises(ValidationError) as validation_error:
        RawAiVocabulary.model_validate({})
    responses = SimpleNamespace(parse=Mock(side_effect=validation_error.value))

    with caplog.at_level("WARNING"), pytest.raises(InvalidAiResponseError) as exc_info:
        generate_vocabulary("raditi", client=SimpleNamespace(responses=responses))

    assert exc_info.value.request_id is None
    assert caplog.records[-1].category == "parse_validation"


def test_raw_response_preserves_request_id_when_parsing_fails(caplog):
    with pytest.raises(ValidationError) as validation_error:
        RawAiVocabulary.model_validate({})
    raw_response = SimpleNamespace(
        headers={"x-request-id": "req_parse"},
        parse=Mock(side_effect=validation_error.value),
    )
    raw_parse = Mock(return_value=raw_response)
    responses = SimpleNamespace(with_raw_response=SimpleNamespace(parse=raw_parse))

    with caplog.at_level("WARNING"), pytest.raises(InvalidAiResponseError) as exc_info:
        generate_vocabulary("raditi", client=SimpleNamespace(responses=responses))

    assert exc_info.value.request_id == "req_parse"
    assert caplog.records[-1].request_id == "req_parse"
    assert raw_parse.call_args.kwargs["store"] is False


@pytest.mark.parametrize(
    ("sdk_error", "category"),
    [
        (
            LengthFinishReasonError(completion=SimpleNamespace(usage=None)),
            "length_finish_reason",
        ),
        (
            ContentFilterFinishReasonError(),
            "content_filter_finish_reason",
        ),
    ],
)
def test_structured_finish_reason_errors_map_to_invalid_response(
    sdk_error,
    category,
    caplog,
):
    raw_response = SimpleNamespace(
        headers={"x-request-id": "req_finish_reason"},
        parse=Mock(side_effect=sdk_error),
    )
    responses = SimpleNamespace(
        with_raw_response=SimpleNamespace(parse=Mock(return_value=raw_response)),
    )

    with caplog.at_level("WARNING"), pytest.raises(InvalidAiResponseError) as exc_info:
        generate_vocabulary("raditi", client=SimpleNamespace(responses=responses))

    assert exc_info.value.request_id == "req_finish_reason"
    assert caplog.records[-1].category == category
    assert caplog.records[-1].request_id == "req_finish_reason"
    assert caplog.records[-1].model == client_module.settings.openai_model
    assert caplog.records[-1].prompt_version == PROMPT_VERSION


def test_logs_and_client_errors_exclude_secret_and_source_word(monkeypatch, caplog):
    secret = "sk-sensitive-test-secret"
    source_word = "source-word-must-not-be-logged"
    sdk_error = AuthenticationError(
        f"Authorization: Bearer {secret}; input={source_word}",
        response=_http_response(401, "req_sensitive"),
        body=None,
    )
    responses = SimpleNamespace(parse=Mock(side_effect=sdk_error))
    monkeypatch.setattr(client_module.settings, "openai_api_key", secret)

    with caplog.at_level("WARNING"), pytest.raises(OpenAiNotConfiguredError) as exc_info:
        generate_vocabulary(source_word, client=SimpleNamespace(responses=responses))

    assert secret not in caplog.text
    assert source_word not in caplog.text
    assert secret not in str(exc_info.value)
    assert source_word not in str(exc_info.value)
    assert exc_info.value.__context__ is None
    custom_log_fields = {
        key
        for key in caplog.records[-1].__dict__
        if key in {"model", "prompt_version", "category", "request_id", "source_word", "api_key"}
    }
    assert custom_log_fields == {"model", "prompt_version", "category", "request_id"}
