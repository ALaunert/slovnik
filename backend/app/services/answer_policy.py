"""Finite, reviewed answer keys for the local written pilot.

This module makes no claim about arbitrary Serbian responses. Unknown wording is
unresolved and cannot become a scored failure without a later reviewed policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import unicodedata

from app.domain.shared import Capability
from app.pilot_examples import _comparison_text
from app.reviewed_example_bank import example_revision_hash


class AnswerVerdict(str, Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class AnswerDecision:
    verdict: AnswerVerdict
    policy_id: str
    policy_revision: int
    source: str = "deterministic"
    error_category: str | None = None


def _normalize(value: str) -> str:
    # The approved bank pins NFC + outer trim. Case, diacritics, inner
    # whitespace and punctuation are intentionally preserved.
    return unicodedata.normalize("NFC", value).strip()


@dataclass(frozen=True)
class ReviewedAnswerPolicy:
    id: str
    revision: int
    example_id: str
    example_revision: int
    example_hash: str
    target_ref: str
    target_span: tuple[int, int]
    capability: Capability
    task_format: str
    accepted: tuple[str, ...]
    field_values: tuple[tuple[str, tuple[str, ...]], ...] = ()

    @classmethod
    def from_reviewed_example(
        cls, item: dict, *, capability: Capability,
    ) -> ReviewedAnswerPolicy:
        policy = item.get("answer_policy", {})
        if policy.get("normalization") != ["NFC", "trim"]:
            raise ValueError("unsupported reviewed answer normalization")
        if policy.get("unlisted") != "unresolved":
            raise ValueError("unlisted answers must remain unresolved")
        if (item.get("content_hash") != example_revision_hash(item)
                or item.get("review", {}).get("status") != "internally_checked"
                or item.get("answer_policy_status") != "internally_checked"):
            raise ValueError("answer policy requires unchanged reviewed example hash")
        if capability is not Capability.APPLY_CONSTRUCTION:
            raise ValueError("pilot answer policy requires apply_construction capability")
        text = item.get("text")
        span = item.get("target_span")
        if (not isinstance(text, str) or not isinstance(span, list) or len(span) != 2
                or any(type(index) is not int for index in span)
                or not 0 <= span[0] < span[1] <= len(text)):
            raise ValueError("invalid reviewed target span")
        answers = item.get("accepted_answers")
        aliases = policy.get("equivalent_script_answers", [])
        if (not isinstance(answers, list) or not answers
                or not isinstance(aliases, list)
                or any(not isinstance(value, str) or not _normalize(value)
                       for value in answers + aliases)):
            raise ValueError("reviewed answer key is empty or malformed")
        task_format = item.get("task", {}).get("format")
        if task_format not in {"sentence", "form", "price_notice"}:
            raise ValueError("unsupported reviewed task format")
        field_values: tuple[tuple[str, tuple[str, ...]], ...] = ()
        if task_format == "form":
            fields = policy.get("fields")
            if not isinstance(fields, dict) or not fields:
                raise ValueError("reviewed form fields missing")
            field_values = tuple((name, tuple(values)) for name, values in fields.items())
            if any(not values or any(not isinstance(value, str) for value in values)
                   for _, values in field_values):
                raise ValueError("reviewed form field values missing")
        if task_format == "price_notice" and policy.get("expected_numeral") != answers[0]:
            raise ValueError("reviewed price numeral mismatch")
        return cls(
            id=policy["id"], revision=policy["revision"], example_id=item["id"],
            example_revision=item["revision"], example_hash=item["content_hash"],
            target_ref=item["target_ref"], target_span=(span[0], span[1]),
            capability=capability, task_format=task_format,
            accepted=tuple(_normalize(answer) for answer in answers + aliases),
            field_values=field_values,
        )

    def _decision(
        self, verdict: AnswerVerdict, error_category: str | None = None,
    ) -> AnswerDecision:
        return AnswerDecision(
            verdict=verdict, policy_id=self.id, policy_revision=self.revision,
            error_category=error_category,
        )

    def evaluate(self, response: str) -> AnswerDecision:
        if not isinstance(response, str):
            raise ValueError("answer must be text")
        if len(response) > 2000:
            raise ValueError("answer exceeds the response snapshot limit")
        value = _normalize(response)
        if not value:
            return self._decision(AnswerVerdict.INCORRECT, "missing_response")
        if self.task_format == "form":
            return self._evaluate_form(value)
        if value in self.accepted:
            return self._decision(AnswerVerdict.CORRECT)
        if self.task_format == "price_notice" and value.isascii() and value.isdigit():
            if int(value) != int(self.accepted[0]):
                return self._decision(AnswerVerdict.INCORRECT, "wrong_numeral")
        return self._decision(AnswerVerdict.UNRESOLVED, "unlisted_variant")

    def _evaluate_form(self, value: str) -> AnswerDecision:
        expected = {_comparison_text(name): set(values) for name, values in self.field_values}
        provided: dict[str, str] = {}
        for line in value.splitlines():
            name, separator, answer = line.partition(":")
            normalized_name = _comparison_text(name)
            if not separator or normalized_name not in expected or normalized_name in provided:
                return self._decision(AnswerVerdict.UNRESOLVED, "unlisted_variant")
            provided[normalized_name] = _normalize(answer)
        if set(provided) != set(expected):
            return self._decision(AnswerVerdict.INCORRECT, "missing_field")
        if any(not answer for answer in provided.values()):
            return self._decision(AnswerVerdict.INCORRECT, "missing_field")
        if all(provided[name] in values for name, values in expected.items()):
            return self._decision(AnswerVerdict.CORRECT)
        return self._decision(AnswerVerdict.UNRESOLVED, "unlisted_variant")
