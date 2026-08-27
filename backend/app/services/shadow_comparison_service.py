from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import logging

from app.config import settings
from app.domain.practice import LearningIntent
from app.domain.selection_policy import NextActivityDecision
from app.services.domain_shadow_contracts import (
    ShadowComparison,
    ShadowComparisonCategory,
    ShadowComparisonReasonCode,
)


logger = logging.getLogger(__name__)


class LegacyLearningSelectionKind(str, Enum):
    DUE = "due"
    NEW = "new"
    WEAK = "weak"
    NONE = "none"


_LEGACY_SELECTION_SEMANTICS: dict[
    LegacyLearningSelectionKind,
    tuple[
        LearningIntent | None,
        tuple[ShadowComparisonReasonCode, ...],
    ],
] = {
    LegacyLearningSelectionKind.DUE: (
        LearningIntent.REVIEW,
        (
            ShadowComparisonReasonCode.LEGACY_REVIEW,
            ShadowComparisonReasonCode.DUE_REVIEW,
        ),
    ),
    LegacyLearningSelectionKind.NEW: (
        LearningIntent.ACQUIRE,
        (
            ShadowComparisonReasonCode.LEGACY_NEW_WORD,
            ShadowComparisonReasonCode.NEW_TARGET,
        ),
    ),
    LegacyLearningSelectionKind.WEAK: (
        LearningIntent.REVIEW,
        (
            ShadowComparisonReasonCode.LEGACY_REVIEW,
            ShadowComparisonReasonCode.WEAK_COMPETENCE,
        ),
    ),
    LegacyLearningSelectionKind.NONE: (None, ()),
}


@dataclass(frozen=True)
class LegacyLearningSelection:
    kind: LegacyLearningSelectionKind
    target_key: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, LegacyLearningSelectionKind):
            raise ValueError("Legacy learning selection kind is invalid")
        has_target = self.target_key is not None
        if has_target != (self.kind is not LegacyLearningSelectionKind.NONE):
            raise ValueError("Legacy learning selection target must match its kind")
        if has_target and (
            not isinstance(self.target_key, str)
            or not 1 <= len(self.target_key) <= 255
        ):
            raise ValueError("Legacy learning selection target is invalid")

    @property
    def intent(self) -> LearningIntent | None:
        return _LEGACY_SELECTION_SEMANTICS[self.kind][0]

    @property
    def reason_codes(self) -> tuple[ShadowComparisonReasonCode, ...]:
        return _LEGACY_SELECTION_SEMANTICS[self.kind][1]


def _category(
    legacy: LegacyLearningSelection,
    shadow: NextActivityDecision,
) -> ShadowComparisonCategory:
    if legacy.intent is None and shadow.intent is not None:
        return ShadowComparisonCategory.LEGACY_NO_ACTIVITY
    if legacy.intent is not None and shadow.intent is None:
        return ShadowComparisonCategory.SHADOW_NO_ACTIVITY
    if legacy.intent != shadow.intent:
        return ShadowComparisonCategory.INTENT_DIFFERENCE
    if legacy.target_key != shadow.target_key:
        return ShadowComparisonCategory.TARGET_DIFFERENCE
    return ShadowComparisonCategory.AGREEMENT


def _reason_codes(
    legacy: LegacyLearningSelection,
    shadow: NextActivityDecision,
) -> tuple[ShadowComparisonReasonCode, ...]:
    shadow_values = tuple(reason.value for reason in shadow.reason_codes)
    if shadow.decision_code is not None:
        shadow_values += (shadow.decision_code.value,)
    combined = (
        *legacy.reason_codes,
        *(ShadowComparisonReasonCode(value) for value in shadow_values),
    )
    return tuple(dict.fromkeys(combined))


def build_shadow_comparison(
    legacy: LegacyLearningSelection,
    shadow: NextActivityDecision,
) -> ShadowComparison:
    return ShadowComparison(
        policy_version=shadow.policy_version,
        legacy_intent=legacy.intent,
        shadow_intent=shadow.intent,
        selected_target_key=shadow.target_key,
        reason_codes=_reason_codes(legacy, shadow),
        category=_category(legacy, shadow),
    )


class ApplicationComparisonLogger:
    def __call__(self, comparison: ShadowComparison | None) -> None:
        if comparison is None:
            logger.warning("Shadow selection comparison failed")
            return
        logger.info(
            "Shadow selection comparison",
            extra={"shadow_comparison": comparison.to_payload()},
        )


class ShadowComparisonService:
    def __init__(
        self,
        *,
        metrics_recorder: Callable[[ShadowComparison], object] | None = None,
        comparison_logger: Callable[[ShadowComparison | None], object] | None = None,
    ) -> None:
        self._metrics_recorder = metrics_recorder
        self._comparison_logger = comparison_logger

    def compare(
        self,
        *,
        legacy_selection: LegacyLearningSelection,
        select_shadow: Callable[[], NextActivityDecision],
    ) -> ShadowComparison | None:
        if not settings.language_assistant_shadow_enabled:
            return None
        try:
            shadow = select_shadow()
            comparison = build_shadow_comparison(legacy_selection, shadow)
        except Exception:
            self._record_best_effort(self._comparison_logger, None)
            return None
        self._record_best_effort(self._metrics_recorder, comparison)
        self._record_best_effort(self._comparison_logger, comparison)
        return comparison

    @staticmethod
    def _record_best_effort(recorder, comparison) -> None:
        if recorder is None:
            return
        try:
            recorder(comparison)
        except Exception:
            return
