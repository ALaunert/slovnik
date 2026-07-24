from dataclasses import dataclass
import logging
from typing import Literal

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ContentFilterFinishReasonError,
    LengthFinishReasonError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import BaseModel, ConfigDict, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)
sdk_logger = logging.getLogger("openai")

PROMPT_VERSION = "v1"
SYSTEM_PROMPT = """
Create a Slovnik vocabulary card draft from one Serbian word for a Russian-speaking learner.
Return null for every field you are uncertain about.
When stress is known, provide corresponding Cyrillic and Latin syllable arrays and one shared
zero-based stressed syllable index. The index must identify the full stressed syllable in both
scripts.
Use only the controlled theme values from the response schema, and use other only when no specific
theme fits.
Do not invent or return a phrase or a list of alternatives when the input is not one Serbian word.
""".strip()

Theme = Literal[
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
]


class RawStressPattern(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cyrillic_syllables: list[str] | None
    latin_syllables: list[str] | None
    stressed_syllable_index: int | None


class RawAiVocabulary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    serbian_cyrillic: str | None
    serbian_latin: str | None
    russian_translation: str | None
    cefr_level: Literal["A1", "A2", "B1", "B2", "C1", "C2"] | None
    theme: Theme | None
    usage_register: str | None
    stress_pattern: RawStressPattern | None
    meaning_notes: str | None
    example_sentences: str | None
    example_translations: str | None


@dataclass(frozen=True)
class OpenAiVocabularyResult:
    payload: RawAiVocabulary
    request_id: str | None


class OpenAiVocabularyClientError(Exception):
    def __init__(self, message: str, request_id: str | None = None) -> None:
        super().__init__(message)
        self.request_id = request_id


class OpenAiNotConfiguredError(OpenAiVocabularyClientError):
    pass


class OpenAiRateLimitedError(OpenAiVocabularyClientError):
    pass


class OpenAiTimeoutError(OpenAiVocabularyClientError):
    pass


class OpenAiUnavailableError(OpenAiVocabularyClientError):
    pass


class InvalidAiResponseError(OpenAiVocabularyClientError):
    pass


def _log_failure(category: str, request_id: str | None = None) -> None:
    context = {
        "model": settings.openai_model,
        "prompt_version": PROMPT_VERSION,
        "category": category,
    }
    if request_id:
        context["request_id"] = request_id
    logger.warning("OpenAI vocabulary request failed", extra=context)


def _request_id(value) -> str | None:
    return getattr(value, "request_id", None) or getattr(value, "_request_id", None)


def _has_refusal(response) -> bool:
    for output_item in getattr(response, "output", None) or ():
        for content_item in getattr(output_item, "content", None) or ():
            if getattr(content_item, "type", None) == "refusal":
                return True
    return False


def generate_vocabulary(source_word: str, client=None) -> OpenAiVocabularyResult:
    if client is None:
        if not settings.openai_api_key.strip() or not settings.openai_model.strip():
            _log_failure("not_configured")
            raise OpenAiNotConfiguredError("OpenAI is not configured")

    failure = None
    request_id = None
    try:
        if sdk_logger.getEffectiveLevel() < logging.INFO:
            sdk_logger.setLevel(logging.INFO)
        if client is None:
            client = OpenAI(
                api_key=settings.openai_api_key,
                timeout=settings.openai_timeout_seconds,
                max_retries=0,
            )
        request_options = {
            "model": settings.openai_model,
            "input": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": source_word},
            ],
            "text_format": RawAiVocabulary,
            "store": False,
        }
        raw_api = getattr(client.responses, "with_raw_response", None)
        if raw_api is None:
            response = client.responses.parse(**request_options)
        else:
            raw_response = raw_api.parse(**request_options)
            request_id = raw_response.headers.get("x-request-id")
            response = raw_response.parse()
    except AuthenticationError as error:
        failure = (
            OpenAiNotConfiguredError,
            "OpenAI authentication failed",
            "authentication",
            _request_id(error),
        )
    except (BadRequestError, PermissionDeniedError, NotFoundError) as error:
        failure = (
            OpenAiNotConfiguredError,
            "OpenAI model configuration is unavailable",
            "configuration",
            _request_id(error),
        )
    except RateLimitError as error:
        failure = (
            OpenAiRateLimitedError,
            "OpenAI rate limit exceeded",
            "rate_limited",
            _request_id(error),
        )
    except APITimeoutError as error:
        failure = (
            OpenAiTimeoutError,
            "OpenAI request timed out",
            "timeout",
            _request_id(error),
        )
    except APIConnectionError as error:
        failure = (
            OpenAiUnavailableError,
            "OpenAI connection failed",
            "connection",
            _request_id(error),
        )
    except APIStatusError as error:
        failure = (
            OpenAiUnavailableError,
            "OpenAI request failed",
            "api_status",
            _request_id(error),
        )
    except ValidationError as error:
        failure = (
            InvalidAiResponseError,
            "OpenAI returned invalid structured output",
            "parse_validation",
            request_id or _request_id(error),
        )
    except LengthFinishReasonError as error:
        failure = (
            InvalidAiResponseError,
            "OpenAI structured output exceeded the length limit",
            "length_finish_reason",
            request_id or _request_id(error),
        )
    except ContentFilterFinishReasonError as error:
        failure = (
            InvalidAiResponseError,
            "OpenAI structured output was rejected by the content filter",
            "content_filter_finish_reason",
            request_id or _request_id(error),
        )

    if failure is not None:
        error_type, message, category, request_id = failure
        _log_failure(category, request_id)
        raise error_type(message, request_id)

    request_id = request_id or _request_id(response)
    if response.output_parsed is None:
        category = "refusal" if _has_refusal(response) else "unparsed"
        _log_failure(category, request_id)
        raise InvalidAiResponseError("OpenAI returned no parsed vocabulary", request_id)

    return OpenAiVocabularyResult(
        payload=response.output_parsed,
        request_id=request_id,
    )
