from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import TYPE_CHECKING

from app.domain.practice import LearningIntent, SelectionReason
from app.domain.selection_policy import (
    AcquireRankComponents,
    ActivityValidityPolicy,
    AssessRankComponents,
    DecisionCode,
    NextActivityDecision,
    ReviewRankComponents,
    StrengthenRankComponents,
    activity_fingerprint,
)
from app.domain.selection_ports import (
    ActivityCandidate,
    ActivityCandidateProvider,
    CurriculumSelectionPort,
    CurriculumTarget,
    LearnerProfilePort,
    LearnerProgressPort,
    SelectionHistoryPort,
)

if TYPE_CHECKING:
    from app.services.domain_shadow_contracts import ShadowComparison
    from app.services.shadow_comparison_service import (
        LegacyLearningSelection,
        ShadowComparisonService,
    )


CEFR_ORDER = {level: index for index, level in enumerate(("A1", "A2", "B1", "B2", "C1", "C2"))}
INTENT_REASONS = {
    LearningIntent.REVIEW: SelectionReason.DUE_REVIEW,
    LearningIntent.STRENGTHEN: SelectionReason.WEAK_COMPETENCE,
    LearningIntent.ACQUIRE: SelectionReason.NEW_TARGET,
    LearningIntent.ASSESS: SelectionReason.ASSESSMENT_GAP,
}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Selection time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _within_requested_level(target: CurriculumTarget, requested_level: str) -> bool:
    outcome_level = target.outcome_code.split(".", 1)[0]
    return CEFR_ORDER.get(outcome_level, 99) <= CEFR_ORDER[requested_level]


def _has_native_deterministic_evidence(state) -> bool:
    return state is not None and (
        state.competence.success_weight + state.competence.failure_weight > 0
    )


def _is_due(state, now: datetime) -> bool:
    return (
        state is not None
        and state.memory.due_at is not None
        and state.memory.due_at <= now
    )


def _is_weak(state) -> bool:
    return state is not None and (
        state.competence.failure_weight > state.competence.success_weight
    )


def _is_acquirable(state, now: datetime) -> bool:
    return not _has_native_deterministic_evidence(state) and (
        state is None or state.memory.due_at is None or state.memory.due_at <= now
    )


def _intent_targets(frontier, states, now, *, acquire_budget_reached: bool):
    review = tuple(
        target
        for target in frontier
        if _is_due(states.get(target.target_spec.target_key), now)
    )
    if review:
        return LearningIntent.REVIEW, review
    strengthen = tuple(
        target
        for target in frontier
        if _is_weak(states.get(target.target_spec.target_key))
    )
    if strengthen:
        return LearningIntent.STRENGTHEN, strengthen
    acquire = tuple(
        target
        for target in frontier
        if _is_acquirable(states.get(target.target_spec.target_key), now)
    )
    if acquire and not acquire_budget_reached:
        return LearningIntent.ACQUIRE, acquire
    assess = tuple(
        target
        for target in frontier
        if _has_native_deterministic_evidence(
            states.get(target.target_spec.target_key)
        )
    )
    if assess:
        return LearningIntent.ASSESS, assess
    return None, acquire


def _utc_day_bounds(now: datetime) -> tuple[datetime, datetime]:
    today_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    return today_start, today_start + timedelta(days=1)


def _daily_acquired_target_keys(history_port, learner_id: str, now: datetime):
    today_start, tomorrow_start = _utc_day_bounds(now)
    return frozenset(
        history_port.first_acquired_target_keys(
            learner_id=learner_id,
            started_at=today_start,
            ended_at=tomorrow_start,
        )
    )


def _repetition_counts(history_port, learner_id: str, now: datetime):
    counts: dict[str, int] = {}
    for activity in history_port.completed_activities(
        learner_id=learner_id,
        started_at=now - timedelta(days=7),
        ended_at=now,
    ):
        counts[activity.activity_fingerprint] = (
            counts.get(activity.activity_fingerprint, 0) + 1
        )
    return counts


def _rank_key(intent, candidate, state, repetition_count, fingerprint):
    target = candidate.curriculum_target
    tie_break = (candidate.activity_spec.target_key, fingerprint)
    if intent is LearningIntent.REVIEW:
        assert state is not None and state.memory.due_at is not None
        return (
            state.memory.due_at,
            -target.priority,
            repetition_count,
            *tie_break,
        )
    if intent is LearningIntent.STRENGTHEN:
        assert state is not None
        weakness_gap = (
            state.competence.failure_weight - state.competence.success_weight
        )
        return (-weakness_gap, -target.priority, repetition_count, *tie_break)
    if intent is LearningIntent.ACQUIRE:
        return (
            -target.priority,
            -target.soft_ready_count,
            repetition_count,
            *tie_break,
        )
    assert intent is LearningIntent.ASSESS and state is not None
    last_evidence_at = state.evidence.last_evidence_at
    return (
        -state.competence.uncertainty,
        last_evidence_at is not None,
        last_evidence_at or datetime.min.replace(tzinfo=timezone.utc),
        -target.priority,
        *tie_break,
    )


def _rank_components(intent, candidate, state, repetition_count, fingerprint):
    target = candidate.curriculum_target
    common = {
        "target_key": candidate.activity_spec.target_key,
        "activity_fingerprint": fingerprint,
    }
    if intent is LearningIntent.REVIEW:
        assert state is not None and state.memory.due_at is not None
        return ReviewRankComponents(
            memory_due_at=state.memory.due_at,
            priority=target.priority,
            repetition_count_7d=repetition_count,
            **common,
        )
    if intent is LearningIntent.STRENGTHEN:
        assert state is not None
        return StrengthenRankComponents(
            weakness_gap=(
                state.competence.failure_weight - state.competence.success_weight
            ),
            priority=target.priority,
            repetition_count_7d=repetition_count,
            **common,
        )
    if intent is LearningIntent.ACQUIRE:
        return AcquireRankComponents(
            priority=target.priority,
            soft_ready_count=target.soft_ready_count,
            repetition_count_7d=repetition_count,
            **common,
        )
    assert intent is LearningIntent.ASSESS and state is not None
    return AssessRankComponents(
        uncertainty=state.competence.uncertainty,
        last_evidence_at=state.evidence.last_evidence_at,
        priority=target.priority,
        **common,
    )


def _select_ranked_candidate(intent, candidates, states, repetition_counts):
    ranked = tuple(
        (candidate, activity_fingerprint(candidate))
        for candidate in candidates
    )
    return min(
        ranked,
        key=lambda item: _rank_key(
            intent,
            item[0],
            states.get(item[0].activity_spec.target_key),
            repetition_counts.get(item[1], 0),
            item[1],
        ),
    )


class NextActivityService:
    def __init__(
        self,
        *,
        profile_port: LearnerProfilePort,
        curriculum_port: CurriculumSelectionPort,
        progress_port: LearnerProgressPort,
        history_port: SelectionHistoryPort,
        candidate_provider: ActivityCandidateProvider,
        validity_policy: ActivityValidityPolicy,
    ) -> None:
        self._profile_port = profile_port
        self._curriculum_port = curriculum_port
        self._progress_port = progress_port
        self._history_port = history_port
        self._candidate_provider = candidate_provider
        self._validity_policy = validity_policy

    def select_next(
        self,
        *,
        learner_id: str,
        now: datetime,
    ) -> NextActivityDecision:
        selection_time = _utc(now)
        profile = self._profile_port.get_profile(learner_id)
        if profile is None:
            raise ValueError("Learner profile is required for selection")
        active_frontier = self._curriculum_port.active_frontier(profile)
        if active_frontier is None:
            return NextActivityDecision.no_activity(
                DecisionCode.NO_ACTIVE_CURRICULUM
            )
        frontier = tuple(
            target
            for target in active_frontier
            if target.content_published
            and target.hard_ready
            and _within_requested_level(target, profile.requested_level)
        )
        if not frontier:
            return NextActivityDecision.no_activity(DecisionCode.EMPTY_FRONTIER)
        states = self._progress_port.states_for_targets(
            learner_id=learner_id,
            target_keys=(target.target_spec.target_key for target in frontier),
        )
        acquired_target_keys = _daily_acquired_target_keys(
            self._history_port,
            learner_id,
            selection_time,
        )
        acquire_budget_reached = len(acquired_target_keys) >= profile.daily_budget
        intent, eligible = _intent_targets(
            frontier,
            states,
            selection_time,
            acquire_budget_reached=acquire_budget_reached,
        )
        if intent is None:
            if eligible and acquire_budget_reached:
                return NextActivityDecision.no_activity(
                    DecisionCode.DAILY_ACQUIRE_BUDGET_REACHED
                )
            return NextActivityDecision.no_activity(DecisionCode.EMPTY_FRONTIER)

        valid_candidates: list[ActivityCandidate] = []
        for target in eligible:
            valid_candidates.extend(
                candidate
                for candidate in self._candidate_provider.candidates_for(target)
                if candidate.curriculum_target == target
                and self._validity_policy.is_valid(candidate)
            )
        if not valid_candidates:
            return NextActivityDecision.no_activity(
                DecisionCode.NO_VALID_CANDIDATE
            )
        repetition_counts = _repetition_counts(
            self._history_port,
            learner_id,
            selection_time,
        )
        selected, selected_fingerprint = _select_ranked_candidate(
            intent,
            valid_candidates,
            states,
            repetition_counts,
        )
        repetition_count = repetition_counts.get(selected_fingerprint, 0)
        return NextActivityDecision(
            activity_spec=selected.activity_spec,
            intent=intent,
            target_key=selected.activity_spec.target_key,
            reason_codes=(INTENT_REASONS[intent],),
            decision_code=None,
            rank_components=_rank_components(
                intent,
                selected,
                states.get(selected.activity_spec.target_key),
                repetition_count,
                selected_fingerprint,
            ),
            activity_fingerprint=selected_fingerprint,
            reason_metadata={
                "difficulty_features": selected.difficulty_features,
            },
        )

    def compare_non_authoritatively(
        self,
        *,
        learner_id: str,
        now: datetime,
        legacy_selection: LegacyLearningSelection,
        comparison_service: ShadowComparisonService,
    ) -> ShadowComparison | None:
        return comparison_service.compare(
            legacy_selection=legacy_selection,
            select_shadow=lambda: self.select_next(
                learner_id=learner_id,
                now=now,
            ),
        )
