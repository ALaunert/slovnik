from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone
import inspect
import json

import pytest


NOW = datetime(2026, 8, 27, 12, 30, tzinfo=timezone.utc)


def test_shadow_contract_wire_values_are_frozen() -> None:
    from app.services.domain_shadow_contracts import (
        ShadowAdapterStatus,
        ShadowComparisonCategory,
        ShadowComparisonReasonCode,
        ShadowLegacySourceKind,
        ShadowPolicyVersion,
        ShadowReasonCode,
    )

    assert tuple(item.value for item in ShadowLegacySourceKind) == (
        "new_word",
        "review",
        "quiz_answer",
    )
    assert tuple(item.value for item in ShadowPolicyVersion) == (
        "legacy-new-word-v1",
        "legacy-review-v1",
        "legacy-quiz-v1",
    )
    assert tuple(item.value for item in ShadowReasonCode) == (
        "legacy_new_word",
        "legacy_review",
        "legacy_quiz",
    )
    assert tuple(item.value for item in ShadowAdapterStatus) == (
        "recorded",
        "duplicate",
    )
    assert tuple(item.value for item in ShadowComparisonCategory) == (
        "agreement",
        "intent_difference",
        "target_difference",
        "shadow_no_activity",
        "legacy_no_activity",
    )
    assert tuple(item.value for item in ShadowComparisonReasonCode) == (
        "legacy_new_word",
        "legacy_review",
        "legacy_quiz",
        "due_review",
        "weak_competence",
        "new_target",
        "assessment_gap",
        "no_active_curriculum",
        "empty_frontier",
        "daily_acquire_budget_reached",
        "no_valid_candidate",
    )


def test_legacy_source_ref_and_idempotency_inputs_have_stable_wire_bytes() -> None:
    from app.domain.practice import SelfReportRating
    from app.services.domain_shadow_contracts import (
        NewWordIdempotencyInput,
        QuizAnswerIdempotencyInput,
        ReviewIdempotencyInput,
        ShadowLegacySourceKind,
        ShadowLegacySourceRef,
    )

    source = ShadowLegacySourceRef(
        kind=ShadowLegacySourceKind.REVIEW,
        reference="user-word-progress:42",
    )
    new_word = NewWordIdempotencyInput(
        learner_ref="learner-1",
        progress_id=42,
        first_seen_at=NOW,
    )
    review = ReviewIdempotencyInput(
        progress_id=42,
        locked_due_at=NOW,
        rating=SelfReportRating.GOOD,
    )
    quiz = QuizAnswerIdempotencyInput(answer_id=17)

    assert source.to_payload() == {
        "kind": "review",
        "reference": "user-word-progress:42",
    }
    assert new_word.key == (
        "legacy:new-word:"
        "a95e258c8d7c9b45b7d6184e5a6a53755c17f36ee0fa13c7238b222e2b1f0244"
    )
    assert review.key == (
        "legacy:review:"
        "ec56b61063331530a46b7d2fa12895596475b1d89db632eac720db92b0da23c7"
    )
    assert quiz.key == "legacy:quiz-answer:17"
    assert ShadowLegacySourceRef(
        kind=ShadowLegacySourceKind.REVIEW,
        reference="re\u0301f",
    ).to_payload() == ShadowLegacySourceRef(
        kind=ShadowLegacySourceKind.REVIEW,
        reference="réf",
    ).to_payload()


def test_adapter_result_and_comparison_have_byte_stable_bounded_payloads() -> None:
    from app.domain.practice import LearningIntent
    from app.services.domain_shadow_contracts import (
        ShadowAdapterResult,
        ShadowAdapterStatus,
        ShadowComparison,
        ShadowComparisonCategory,
        ShadowReasonCode,
    )

    result = ShadowAdapterResult(
        status=ShadowAdapterStatus.RECORDED,
        practice_run_id="10000000-0000-4000-8000-000000000001",
        activity_instance_ids=("20000000-0000-4000-8000-000000000001",),
        event_ids=("30000000-0000-4000-8000-000000000001",),
    )
    comparison = ShadowComparison(
        policy_version="selector-v1",
        legacy_intent=LearningIntent.REVIEW,
        shadow_intent=LearningIntent.REVIEW,
        selected_target_key="v1:sense:target",
        reason_codes=(ShadowReasonCode.LEGACY_REVIEW,),
        category=ShadowComparisonCategory.AGREEMENT,
    )

    assert json.dumps(
        result.to_payload(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode() == (
        b'{"activity_instance_ids":["20000000-0000-4000-8000-000000000001"],'
        b'"event_ids":["30000000-0000-4000-8000-000000000001"],'
        b'"practice_run_id":"10000000-0000-4000-8000-000000000001",'
        b'"status":"recorded"}'
    )
    assert comparison.to_payload() == {
        "policy_version": "selector-v1",
        "legacy_intent": "review",
        "shadow_intent": "review",
        "selected_target_key": "v1:sense:target",
        "reason_codes": ["legacy_review"],
        "category": "agreement",
    }
    with pytest.raises(FrozenInstanceError):
        result.status = ShadowAdapterStatus.DUPLICATE


def test_contract_excludes_sensitive_fields_and_legacy_service_imports() -> None:
    from app.services import domain_shadow_contracts as contracts
    from app.services.domain_shadow_contracts import (
        ShadowAdapterResult,
        ShadowComparison,
        ShadowLegacySourceRef,
    )

    field_names = {
        field.name
        for contract in (ShadowAdapterResult, ShadowComparison, ShadowLegacySourceRef)
        for field in fields(contract)
    }
    source = inspect.getsource(contracts)

    assert field_names.isdisjoint(
        {"raw_response", "learner_response", "provider_prompt", "api_key"}
    )
    assert "learning_service" not in source
    assert "quiz_service" not in source


@pytest.mark.parametrize(
    "reason_codes",
    ["due_review", ("due_reveiw",), ("due_review",)],
)
def test_comparison_rejects_ambiguous_or_untyped_reason_codes(reason_codes) -> None:
    from app.domain.practice import LearningIntent
    from app.services.domain_shadow_contracts import (
        ShadowComparison,
        ShadowComparisonCategory,
    )

    with pytest.raises(ValueError, match="reason code"):
        ShadowComparison(
            policy_version="selector-v1",
            legacy_intent=LearningIntent.REVIEW,
            shadow_intent=LearningIntent.REVIEW,
            selected_target_key="v1:sense:target",
            reason_codes=reason_codes,
            category=ShadowComparisonCategory.AGREEMENT,
        )
