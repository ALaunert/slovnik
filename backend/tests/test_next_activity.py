import inspect
import json
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace
from typing import Protocol

import pytest


NOW = datetime(2026, 8, 27, 12, tzinfo=timezone.utc)
SENSE_ID = "11111111-1111-4111-8111-111111111111"
CONSTRUCTION_ID = "22222222-2222-4222-8222-222222222222"


def _target(
    *,
    construction: bool = False,
    recognition: bool = False,
    target_id: str | None = None,
):
    from app.domain.shared import Capability, Modality, TargetKind
    from app.domain.target import TargetSpec

    if construction:
        return TargetSpec(
            target_kind=TargetKind.CONSTRUCTION,
            target_id=target_id or CONSTRUCTION_ID,
            capability=Capability.APPLY_CONSTRUCTION,
            modality=Modality.WRITTEN,
        )
    return TargetSpec(
        target_kind=TargetKind.SENSE,
        target_id=target_id or SENSE_ID,
        capability=(
            Capability.RECOGNIZE_MEANING
            if recognition
            else Capability.RETRIEVE_FORM
        ),
        modality=Modality.WRITTEN,
    )


def _curriculum_target(
    target_spec=None,
    *,
    priority: int = 50,
    hard_ready: bool = True,
    soft_ready_count: int = 0,
    content_published: bool = True,
    non_target_items=(),
):
    from app.domain.selection_ports import CurriculumTarget

    target_spec = target_spec or _target()
    stimulus_snapshot = {
        "cue": {"language": "ru", "text": "слово"},
        "expected": {"language": "sr", "text": "reč"},
    }
    if target_spec.capability.value == "recognize_meaning":
        stimulus_snapshot = {
            "cue": "reč",
            "options": ["слово", "речь"],
            "expected": "речь",
        }
    return CurriculumTarget(
        target_spec=target_spec,
        priority=priority,
        outcome_code="A1.core",
        hard_ready=hard_ready,
        soft_ready_count=soft_ready_count,
        content_published=content_published,
        stimulus_snapshot=stimulus_snapshot,
        non_target_items=non_target_items,
    )


def _native_state(target_spec, *, due_at=None, success=1, failure=0, uncertainty=0.5):
    from app.domain.progress import (
        CompetenceEstimate,
        EvidenceSummary,
        LearnerTargetState,
        MemoryState,
        ProjectionBaseline,
    )

    evidence_count = success + failure
    return LearnerTargetState(
        state_id="99999999-9999-4999-8999-999999999999",
        learner_id="learner-1",
        target_key=target_spec.target_key,
        baseline=ProjectionBaseline.neutral(),
        competence=CompetenceEstimate(
            success_weight=success,
            failure_weight=failure,
            peak=2 / 3 if success else 0,
            uncertainty=uncertainty,
        ),
        evidence=EvidenceSummary(
            count=evidence_count,
            deterministic_count=evidence_count,
            last_evidence_at=NOW - timedelta(days=2),
            last_event_id="88888888-8888-4888-8888-888888888888",
        ),
        memory=MemoryState(
            due_at=due_at,
            interval_days=2,
            lapses=failure,
            policy_version="memory-v1",
        ),
        projection_policy_version="projection-v1",
        updated_at=NOW - timedelta(days=2),
    )


class FakeProfilePort:
    def __init__(self, profile) -> None:
        self.profile = profile

    def get_profile(self, learner_id: str):
        return self.profile if learner_id == self.profile.learner_id else None


class FakeCurriculumPort:
    def __init__(self, frontier) -> None:
        self.frontier = frontier

    def active_frontier(self, profile):
        return self.frontier


class FakeProgressPort:
    def __init__(self, states) -> None:
        self.states = states

    def states_for_targets(self, *, learner_id: str, target_keys):
        return {
            key: state
            for key in target_keys
            if (state := self.states.get(key)) is not None
        }


class FakeHistoryPort:
    def __init__(self, activities=()) -> None:
        self.activities = tuple(activities)

    def completed_activities(self, *, learner_id: str, started_at, ended_at):
        return tuple(
            activity
            for activity in self.activities
            if started_at <= activity.completed_at < ended_at
        )

    def first_acquired_target_keys(self, *, learner_id: str, started_at, ended_at):
        from app.domain.practice import LearningIntent

        first_acquired_at = {}
        for activity in self.activities:
            if activity.intent is not LearningIntent.ACQUIRE:
                continue
            earliest = first_acquired_at.get(activity.target_key)
            if earliest is None or activity.completed_at < earliest:
                first_acquired_at[activity.target_key] = activity.completed_at
        return tuple(
            target_key
            for target_key, completed_at in first_acquired_at.items()
            if started_at <= completed_at < ended_at
        )


def _service(
    frontier,
    states=None,
    *,
    activities=(),
    daily_budget=5,
    candidate_provider=None,
):
    from app.domain.progress import LearnerProfile
    from app.domain.selection_policy import (
        ActivityValidityPolicy,
        CuratedActivityCandidateProvider,
    )
    from app.services.next_activity_service import NextActivityService

    return NextActivityService(
        profile_port=FakeProfilePort(
            LearnerProfile(
                learner_id="learner-1",
                l1="ru",
                requested_level="A1",
                daily_budget=daily_budget,
            )
        ),
        curriculum_port=FakeCurriculumPort(frontier),
        progress_port=FakeProgressPort(states or {}),
        history_port=FakeHistoryPort(activities),
        candidate_provider=candidate_provider or CuratedActivityCandidateProvider(),
        validity_policy=ActivityValidityPolicy(),
    )


def test_curated_provider_builds_four_bounded_deterministic_activity_shapes() -> None:
    from app.domain.practice import (
        ActivityKind,
        ExerciseOperation,
        GeneratorKind,
        ScorerKind,
    )
    from app.domain.selection_policy import CuratedActivityCandidateProvider

    provider = CuratedActivityCandidateProvider()
    recognition_target = _curriculum_target(_target(recognition=True))
    retrieval_target = _curriculum_target(_target())
    construction_target = _curriculum_target(_target(construction=True))

    candidates = (
        *provider.candidates_for(recognition_target),
        *provider.candidates_for(retrieval_target),
        *provider.candidates_for(construction_target),
    )

    assert [candidate.activity_spec.operation for candidate in candidates] == [
        ExerciseOperation.RECOGNIZE,
        ExerciseOperation.RETRIEVE,
        ExerciseOperation.COMPLETE,
        ExerciseOperation.TRANSFORM,
    ]
    assert all(
        candidate.activity_spec.activity_kind is ActivityKind.EXERCISE
        and candidate.activity_spec.target_key
        == candidate.curriculum_target.target_spec.target_key
        and candidate.activity_spec.scorer_kind is ScorerKind.DETERMINISTIC
        and candidate.generator_kind is GeneratorKind.CURATED
        and candidate.curriculum_target.content_published
        for candidate in candidates
    )
    assert [
        candidate.activity_spec.snapshot["response_contract"]["kind"]
        for candidate in candidates
    ] == ["choice", "text", "text", "text"]
    assert candidates[0].activity_spec.snapshot["response_contract"]["max_options"] == 4
    assert all(
        candidate.activity_spec.snapshot["response_contract"].get(
            "max_codepoints",
            2000,
        )
        <= 2000
        for candidate in candidates
    )


def test_ai_candidate_provider_is_a_pure_no_network_port() -> None:
    network_modules_before = {
        name for name in sys.modules if name.startswith(("openai", "httpx", "requests"))
    }

    from app.domain.selection_ports import AiActivityCandidateProvider

    network_modules_after = {
        name for name in sys.modules if name.startswith(("openai", "httpx", "requests"))
    }

    assert issubclass(AiActivityCandidateProvider, Protocol)
    assert inspect.isabstract(AiActivityCandidateProvider)
    assert network_modules_after == network_modules_before


def test_validity_policy_enforces_target_scoring_response_and_burden_bounds() -> None:
    from app.domain.curriculum import PrerequisiteKind
    from app.domain.practice import ActivitySpec, ExerciseOperation, ScorerKind
    from app.domain.selection_policy import (
        ActivityValidityPolicy,
        CuratedActivityCandidateProvider,
    )
    from app.domain.selection_ports import NonTargetItem
    from app.domain.shared import TargetKind

    provider = CuratedActivityCandidateProvider()
    policy = ActivityValidityPolicy()
    retrieval_target = _curriculum_target(_target())
    valid_lexical = provider.candidates_for(retrieval_target)[0]
    one_glossed_soft_item = NonTargetItem(
        target_kind=TargetKind.SENSE,
        known=False,
        prerequisite_kind=PrerequisiteKind.SOFT,
        gloss="новое слово",
    )
    construction_target = _curriculum_target(
        _target(construction=True),
        non_target_items=(one_glossed_soft_item,),
    )
    valid_construction = provider.candidates_for(construction_target)[0]

    def altered(candidate, **changes):
        payload = candidate.activity_spec.to_payload()
        payload.update(changes)
        return replace(candidate, activity_spec=ActivitySpec.from_payload(payload))

    lexical_unknown = provider.candidates_for(
        replace(retrieval_target, non_target_items=(one_glossed_soft_item,))
    )[0]
    two_unknown = provider.candidates_for(
        replace(
            construction_target,
            non_target_items=(one_glossed_soft_item, one_glossed_soft_item),
        )
    )[0]
    missing_gloss = provider.candidates_for(
        replace(
            construction_target,
            non_target_items=(replace(one_glossed_soft_item, gloss=None),),
        )
    )[0]
    wrong_scorer = altered(valid_lexical, scorer_kind=ScorerKind.SELF_REPORT.value)
    wrong_operation = altered(
        valid_lexical,
        operation=ExerciseOperation.RECOGNIZE.value,
    )
    wrong_target = altered(
        valid_lexical,
        target_spec=_target(recognition=True).to_payload(),
    )
    oversized_response = altered(
        valid_lexical,
        snapshot={
            **valid_lexical.activity_spec.to_payload()["snapshot"],
            "response_contract": {"kind": "text", "max_codepoints": 2001},
        },
    )

    assert policy.is_valid(valid_lexical)
    assert policy.is_valid(valid_construction)
    assert all(
        not policy.is_valid(candidate)
        for candidate in (
            provider.candidates_for(replace(retrieval_target, hard_ready=False))[0],
            provider.candidates_for(
                replace(retrieval_target, content_published=False)
            )[0],
            lexical_unknown,
            two_unknown,
            missing_gloss,
            wrong_scorer,
            wrong_operation,
            wrong_target,
            oversized_response,
        )
    )
    assert not hasattr(valid_lexical, "penalty")
    assert not hasattr(valid_lexical, "expected_success")
    assert not hasattr(valid_lexical, "difficulty")


def test_recognition_candidate_requires_usable_cue_options_and_expected_answer() -> None:
    from app.domain.practice import ActivitySpec
    from app.domain.selection_policy import (
        ActivityValidityPolicy,
        CuratedActivityCandidateProvider,
    )

    candidate = CuratedActivityCandidateProvider().candidates_for(
        _curriculum_target(_target(recognition=True))
    )[0]
    policy = ActivityValidityPolicy()

    def with_snapshot(snapshot):
        payload = candidate.activity_spec.to_payload()
        payload["snapshot"] = snapshot
        return replace(
            candidate,
            activity_spec=ActivitySpec.from_payload(payload),
        )

    response_contract = {"kind": "choice", "max_options": 2}
    valid = with_snapshot(
        {
            "cue": "reč",
            "options": ["слово", "речь"],
            "expected": "речь",
            "response_contract": response_contract,
        }
    )
    invalid = (
        with_snapshot({"response_contract": response_contract}),
        with_snapshot(
            {
                "cue": " ",
                "options": ["слово", "речь"],
                "expected": "речь",
                "response_contract": response_contract,
            }
        ),
        with_snapshot(
            {
                "cue": "reč",
                "options": [],
                "expected": "речь",
                "response_contract": response_contract,
            }
        ),
        with_snapshot(
            {
                "cue": "reč",
                "options": ["речь"],
                "expected": "речь",
                "response_contract": response_contract,
            }
        ),
        with_snapshot(
            {
                "cue": "reč",
                "options": ["слово", "речь", "язык"],
                "expected": "речь",
                "response_contract": response_contract,
            }
        ),
        with_snapshot(
            {
                "cue": "reč",
                "options": ["слово", "речь"],
                "response_contract": response_contract,
            }
        ),
        with_snapshot(
            {
                "cue": "reč",
                "options": ["слово", "речь"],
                "expected": "язык",
                "response_contract": response_contract,
            }
        ),
        with_snapshot(
            {
                "cue": "reč",
                "options": ["речь", "речь"],
                "expected": "речь",
                "response_contract": response_contract,
            }
        ),
        with_snapshot(
            {
                "cue": "x" * 2001,
                "options": ["слово", "речь"],
                "expected": "речь",
                "response_contract": response_contract,
            }
        ),
        with_snapshot(
            {
                "cue": "reč",
                "options": ["x" * 121, "речь"],
                "expected": "речь",
                "response_contract": response_contract,
            }
        ),
    )

    assert policy.is_valid(valid)
    assert all(not policy.is_valid(value) for value in invalid)


def test_selector_rejects_non_string_recognition_choice_schema() -> None:
    from app.domain.practice import ActivitySpec
    from app.domain.selection_policy import (
        CuratedActivityCandidateProvider,
        DecisionCode,
    )

    target = _curriculum_target(_target(recognition=True))

    class NonStringChoiceProvider:
        def candidates_for(self, curriculum_target):
            candidate = CuratedActivityCandidateProvider().candidates_for(
                curriculum_target
            )[0]
            snapshots = (
                {
                    "cue": 1,
                    "options": [1, 2],
                    "expected": 1,
                },
                {
                    "cue": "reč",
                    "options": ["слово", 2],
                    "expected": "слово",
                },
                {
                    "cue": "reč",
                    "options": ["слово", "речь"],
                    "expected": True,
                },
            )
            values = []
            for snapshot in snapshots:
                payload = candidate.activity_spec.to_payload()
                payload["snapshot"] = {
                    **snapshot,
                    "response_contract": {
                        "kind": "choice",
                        "max_options": 4,
                    },
                }
                values.append(
                    replace(
                        candidate,
                        activity_spec=ActivitySpec.from_payload(payload),
                    )
                )
            return tuple(values)

    decision = _service(
        (target,),
        candidate_provider=NonStringChoiceProvider(),
    ).select_next(learner_id="learner-1", now=NOW)

    assert decision.decision_code is DecisionCode.NO_VALID_CANDIDATE
    assert decision.activity_spec is None


def test_selector_rejects_snapshot_that_cannot_be_fingerprinted() -> None:
    from app.domain.practice import ActivitySpec
    from app.domain.selection_policy import (
        CuratedActivityCandidateProvider,
        DecisionCode,
    )

    target = _curriculum_target(_target())

    class FloatSnapshotProvider:
        def candidates_for(self, curriculum_target):
            candidate = CuratedActivityCandidateProvider().candidates_for(
                curriculum_target
            )[0]
            payload = candidate.activity_spec.to_payload()
            payload["snapshot"] = {
                **payload["snapshot"],
                "estimated_difficulty": 0.5,
            }
            return (
                replace(
                    candidate,
                    activity_spec=ActivitySpec.from_payload(payload),
                ),
            )

    decision = _service(
        (target,),
        candidate_provider=FloatSnapshotProvider(),
    ).select_next(learner_id="learner-1", now=NOW)

    assert decision.decision_code is DecisionCode.NO_VALID_CANDIDATE
    assert decision.activity_spec is None


def test_decision_preserves_bounded_frozen_difficulty_reason_metadata() -> None:
    from app.domain.selection_policy import CuratedActivityCandidateProvider
    from app.domain.selection_ports import MAX_DIFFICULTY_FEATURE_BYTES

    target = _curriculum_target(_target())
    first_source = {
        "surface": {"token_count": 2, "markers": ["soft", "glossed"]},
        "non_target_item_count": 1,
    }
    second_source = {
        "non_target_item_count": 1,
        "surface": {"markers": ["soft", "glossed"], "token_count": 2},
    }

    class FeatureProvider:
        def __init__(self, features):
            self.features = features

        def candidates_for(self, curriculum_target):
            candidate = CuratedActivityCandidateProvider().candidates_for(
                curriculum_target
            )[0]
            return (replace(candidate, difficulty_features=self.features),)

    first = _service(
        (target,),
        candidate_provider=FeatureProvider(first_source),
    ).select_next(learner_id="learner-1", now=NOW)
    second = _service(
        (target,),
        candidate_provider=FeatureProvider(second_source),
    ).select_next(learner_id="learner-1", now=NOW)

    expected = {
        "difficulty_features": {
            "non_target_item_count": 1,
            "surface": {"markers": ["soft", "glossed"], "token_count": 2},
        }
    }
    assert first.to_payload()["reason_metadata"] == expected
    assert first.reason_metadata == second.reason_metadata
    assert json.dumps(
        first.to_payload(), ensure_ascii=False, separators=(",", ":")
    ) == json.dumps(
        second.to_payload(), ensure_ascii=False, separators=(",", ":")
    )
    with pytest.raises(TypeError):
        first.reason_metadata["difficulty_features"]["surface"]["token_count"] = 3
    with pytest.raises(ValueError, match="difficulty_features"):
        FeatureProvider(
            {"oversized": "x" * (MAX_DIFFICULTY_FEATURE_BYTES + 1)}
        ).candidates_for(target)


def test_selector_uses_review_strengthen_acquire_assess_precedence() -> None:
    from app.domain.practice import LearningIntent, SelectionReason

    due_target = _target(target_id="33333333-3333-4333-8333-333333333333")
    weak_target = _target(target_id="44444444-4444-4444-8444-444444444444")
    acquire_target = _target(target_id="55555555-5555-4555-8555-555555555555")
    assess_target = _target(target_id="66666666-6666-4666-8666-666666666666")
    targets = {
        "due": _curriculum_target(due_target, priority=1),
        "weak": _curriculum_target(weak_target, priority=20),
        "acquire": _curriculum_target(acquire_target, priority=100),
        "assess": _curriculum_target(assess_target, priority=90),
    }
    states = {
        due_target.target_key: _native_state(
            due_target,
            due_at=NOW - timedelta(minutes=1),
        ),
        weak_target.target_key: _native_state(
            weak_target,
            due_at=NOW + timedelta(days=1),
            success=0,
            failure=2,
        ),
        assess_target.target_key: _native_state(
            assess_target,
            due_at=NOW + timedelta(days=2),
        ),
    }

    review = _service(tuple(targets.values()), states).select_next(
        learner_id="learner-1",
        now=NOW,
    )
    strengthen = _service(
        (targets["weak"], targets["acquire"], targets["assess"]),
        states,
    ).select_next(learner_id="learner-1", now=NOW)
    acquire = _service(
        (targets["acquire"], targets["assess"]),
        states,
    ).select_next(learner_id="learner-1", now=NOW)
    assess = _service((targets["assess"],), states).select_next(
        learner_id="learner-1",
        now=NOW,
    )

    assert [decision.intent for decision in (review, strengthen, acquire, assess)] == [
        LearningIntent.REVIEW,
        LearningIntent.STRENGTHEN,
        LearningIntent.ACQUIRE,
        LearningIntent.ASSESS,
    ]
    assert [decision.reason_codes for decision in (review, strengthen, acquire, assess)] == [
        (SelectionReason.DUE_REVIEW,),
        (SelectionReason.WEAK_COMPETENCE,),
        (SelectionReason.NEW_TARGET,),
        (SelectionReason.ASSESSMENT_GAP,),
    ]
    assert review.target_key == due_target.target_key
    assert strengthen.target_key == weak_target.target_key
    assert acquire.target_key == acquire_target.target_key
    assert assess.target_key == assess_target.target_key


def test_partial_deterministic_response_creates_assessment_gap() -> None:
    from types import SimpleNamespace

    from app.domain.practice import LearningIntent, SelectionReason
    from app.domain.progress import LearnerTargetState
    from app.services.learner_projection_service import project_event

    target_spec = _target(target_id="67676767-6767-4767-8767-676767676767")
    state = LearnerTargetState.neutral(
        state_id="68686868-6868-4868-8868-686868686868",
        learner_id="learner-1",
        target_key=target_spec.target_key,
        updated_at=NOW - timedelta(hours=2),
    )
    projected = project_event(
        state,
        SimpleNamespace(
            event_id="69696969-6969-4969-8969-696969696969",
            learner_id="learner-1",
            target_key=target_spec.target_key,
            occurred_at=NOW - timedelta(hours=1),
            event_type="response_evaluated",
            evaluation_source="deterministic",
            evaluation_outcome="partial",
            first_response=None,
        ),
    )

    decision = _service(
        (_curriculum_target(target_spec),),
        {target_spec.target_key: projected},
    ).select_next(learner_id="learner-1", now=NOW)

    assert decision.intent is LearningIntent.ASSESS
    assert decision.reason_codes == (SelectionReason.ASSESSMENT_GAP,)


def test_selector_prioritizes_due_state_and_does_not_mutate_projection() -> None:
    from app.domain.practice import LearningIntent, SelectionReason
    from app.domain.progress import LearnerTargetState
    from app.services.learner_projection_service import project_event

    due_target = _target(target_id="14141414-1414-4414-8414-141414141414")
    acquire_target = _target(target_id="15151515-1515-4515-8515-151515151515")
    baseline = LearnerTargetState.neutral(
        state_id="16161616-1616-4616-8616-161616161616",
        learner_id="learner-1",
        target_key=due_target.target_key,
        updated_at=NOW - timedelta(hours=3),
    )

    def event(event_id, occurred_at, outcome):
        return SimpleNamespace(
            event_id=event_id,
            learner_id="learner-1",
            target_key=due_target.target_key,
            occurred_at=occurred_at,
            event_type="response_evaluated",
            evaluation_source="deterministic",
            evaluation_outcome=outcome,
            first_response=None,
        )

    projected = project_event(
        project_event(
            baseline,
            event(
                "17171717-1717-4717-8717-171717171711",
                NOW - timedelta(hours=2),
                "correct",
            ),
        ),
        event(
            "17171717-1717-4717-8717-171717171712",
            NOW - timedelta(hours=1),
            "incorrect",
        ),
    )
    before_bytes = repr(projected).encode("utf-8")

    decision = _service(
        (
            _curriculum_target(acquire_target, priority=100),
            _curriculum_target(due_target, priority=1),
        ),
        {due_target.target_key: projected},
    ).select_next(learner_id="learner-1", now=NOW)

    assert decision.intent is LearningIntent.REVIEW
    assert decision.target_key == due_target.target_key
    assert decision.reason_codes == (SelectionReason.DUE_REVIEW,)
    assert decision.policy_version == "selector-v1"
    assert repr(projected).encode("utf-8") == before_bytes


def test_selector_returns_exact_no_activity_codes_and_respects_future_hold() -> None:
    from app.domain.curriculum import PrerequisiteKind
    from app.domain.progress import LearnerTargetState, ProjectionBaseline
    from app.domain.selection_policy import DecisionCode
    from app.domain.selection_ports import NonTargetItem
    from app.domain.shared import TargetKind

    target_spec = _target(target_id="77777777-7777-4777-8777-777777777777")
    target = _curriculum_target(target_spec)
    future_hold = LearnerTargetState.legacy_bootstrap(
        state_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        learner_id="learner-1",
        target_key=target_spec.target_key,
        baseline=ProjectionBaseline.legacy(
            memory_due_at=NOW + timedelta(days=1),
            memory_interval_days=1,
            source_ref="user_word_progress:1",
            source_fingerprint="a" * 64,
        ),
        updated_at=NOW - timedelta(days=1),
    )
    invalid_target = replace(
        target,
        non_target_items=(
            NonTargetItem(
                target_kind=TargetKind.SENSE,
                known=False,
                prerequisite_kind=PrerequisiteKind.SOFT,
                gloss="лишняя нагрузка",
            ),
        ),
    )

    decisions = (
        _service(None).select_next(learner_id="learner-1", now=NOW),
        _service(()).select_next(learner_id="learner-1", now=NOW),
        _service((replace(target, hard_ready=False),)).select_next(
            learner_id="learner-1",
            now=NOW,
        ),
        _service((replace(target, outcome_code="B1.later"),)).select_next(
            learner_id="learner-1",
            now=NOW,
        ),
        _service((target,), {target_spec.target_key: future_hold}).select_next(
            learner_id="learner-1",
            now=NOW,
        ),
        _service((invalid_target,)).select_next(
            learner_id="learner-1",
            now=NOW,
        ),
    )

    assert [decision.decision_code for decision in decisions] == [
        DecisionCode.NO_ACTIVE_CURRICULUM,
        DecisionCode.EMPTY_FRONTIER,
        DecisionCode.EMPTY_FRONTIER,
        DecisionCode.EMPTY_FRONTIER,
        DecisionCode.EMPTY_FRONTIER,
        DecisionCode.NO_VALID_CANDIDATE,
    ]
    assert all(decision.activity_spec is None for decision in decisions)
    assert all(decision.intent is None for decision in decisions)


def test_candidate_provider_cannot_substitute_a_target_outside_the_frontier() -> None:
    from app.domain.selection_policy import (
        CuratedActivityCandidateProvider,
        DecisionCode,
    )

    eligible = _curriculum_target(
        _target(target_id="12121212-1212-4212-8212-121212121212")
    )
    substituted = _curriculum_target(
        _target(target_id="13131313-1313-4313-8313-131313131313")
    )

    class SubstitutingProvider:
        def candidates_for(self, curriculum_target):
            return CuratedActivityCandidateProvider().candidates_for(substituted)

    service = _service((eligible,), candidate_provider=SubstitutingProvider())

    decision = service.select_next(learner_id="learner-1", now=NOW)

    assert decision.decision_code is DecisionCode.NO_VALID_CANDIDATE
    assert decision.target_key is None


def test_daily_budget_counts_distinct_completed_acquire_targets_only() -> None:
    from app.domain.practice import LearningIntent
    from app.domain.progress import LearnerTargetState, ProjectionBaseline
    from app.domain.selection_policy import DecisionCode
    from app.domain.selection_ports import CompletedActivity

    unseen = _target(target_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    acquired_a = _target(target_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc")
    acquired_b = _target(target_id="dddddddd-dddd-4ddd-8ddd-dddddddddddd")
    legacy_target = _target(target_id="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
    today_start = datetime(2026, 8, 27, tzinfo=timezone.utc)

    def completed(target_spec, intent, fingerprint, completed_at):
        return CompletedActivity(
            target_key=target_spec.target_key,
            intent=intent,
            activity_fingerprint=fingerprint * 64,
            completed_at=completed_at,
        )

    history = (
        completed(acquired_a, LearningIntent.ACQUIRE, "a", today_start),
        completed(
            acquired_a,
            LearningIntent.ACQUIRE,
            "b",
            today_start + timedelta(hours=1),
        ),
        completed(
            acquired_b,
            LearningIntent.ACQUIRE,
            "c",
            today_start + timedelta(hours=2),
        ),
        completed(
            unseen,
            LearningIntent.REVIEW,
            "d",
            today_start + timedelta(hours=3),
        ),
        completed(
            unseen,
            LearningIntent.ACQUIRE,
            "e",
            today_start - timedelta(microseconds=1),
        ),
    )
    legacy_hold = LearnerTargetState.legacy_bootstrap(
        state_id="ffffffff-ffff-4fff-8fff-ffffffffffff",
        learner_id="learner-1",
        target_key=legacy_target.target_key,
        baseline=ProjectionBaseline.legacy(
            memory_due_at=NOW + timedelta(days=1),
            memory_interval_days=1,
            source_ref="user_word_progress:9",
            source_fingerprint="f" * 64,
        ),
        updated_at=NOW - timedelta(days=1),
    )

    blocked = _service(
        (_curriculum_target(unseen), _curriculum_target(legacy_target)),
        {legacy_target.target_key: legacy_hold},
        activities=history,
        daily_budget=2,
    ).select_next(learner_id="learner-1", now=NOW)
    retry_deduped = _service(
        (_curriculum_target(unseen),),
        activities=history[:2],
        daily_budget=2,
    ).select_next(learner_id="learner-1", now=NOW)
    due_state = _native_state(unseen, due_at=NOW - timedelta(minutes=1))
    due_at_limit = _service(
        (_curriculum_target(unseen),),
        {unseen.target_key: due_state},
        activities=history,
        daily_budget=2,
    ).select_next(learner_id="learner-1", now=NOW)

    assert blocked.decision_code is DecisionCode.DAILY_ACQUIRE_BUDGET_REACHED
    assert blocked.intent is None
    assert retry_deduped.intent is LearningIntent.ACQUIRE
    assert due_at_limit.intent is LearningIntent.REVIEW


def test_daily_budget_counts_only_targets_first_acquired_today() -> None:
    from app.domain.practice import LearningIntent
    from app.domain.selection_ports import CompletedActivity

    unseen = _target(target_id="14141414-1414-4414-8414-141414141414")
    acquired_yesterday = _target(
        target_id="15151515-1515-4515-8515-151515151515"
    )
    first_acquired_today = _target(
        target_id="16161616-1616-4616-8616-161616161616"
    )
    today_start = datetime(2026, 8, 27, tzinfo=timezone.utc)
    history = (
        CompletedActivity(
            target_key=acquired_yesterday.target_key,
            intent=LearningIntent.ACQUIRE,
            activity_fingerprint="a" * 64,
            completed_at=today_start - timedelta(days=1),
        ),
        CompletedActivity(
            target_key=acquired_yesterday.target_key,
            intent=LearningIntent.ACQUIRE,
            activity_fingerprint="b" * 64,
            completed_at=today_start + timedelta(hours=1),
        ),
        CompletedActivity(
            target_key=first_acquired_today.target_key,
            intent=LearningIntent.ACQUIRE,
            activity_fingerprint="c" * 64,
            completed_at=today_start + timedelta(hours=2),
        ),
    )

    decision = _service(
        (_curriculum_target(unseen),),
        activities=history,
        daily_budget=2,
    ).select_next(learner_id="learner-1", now=NOW)

    assert decision.intent is LearningIntent.ACQUIRE
    assert decision.target_key == unseen.target_key


def test_activity_fingerprint_is_alg04_canonical_and_does_not_mutate_inputs() -> None:
    from app.domain.practice import GeneratorKind
    from app.domain.selection_policy import (
        CuratedActivityCandidateProvider,
        activity_fingerprint,
    )
    from app.domain.selection_ports import CurriculumTarget

    target_spec = _target()
    first_source = {
        "expected": {"text": "reč", "language": "sr"},
        "cue": {"text": "réč", "language": "ru"},
    }
    second_source = {
        "cue": {"language": "ru", "text": "réč"},
        "expected": {"language": "sr", "text": "reč"},
    }
    original_bytes = json.dumps(first_source, ensure_ascii=False)

    def context(snapshot):
        return CurriculumTarget(
            target_spec=target_spec,
            priority=50,
            outcome_code="A1.core",
            hard_ready=True,
            soft_ready_count=0,
            content_published=True,
            stimulus_snapshot=snapshot,
        )

    provider = CuratedActivityCandidateProvider()
    first = provider.candidates_for(context(first_source))[0]
    second = provider.candidates_for(context(second_source))[0]
    payload = {
        "schema_version": 1,
        "target_key": first.activity_spec.target_key,
        "activity_kind": first.activity_spec.activity_kind.value,
        "operation": first.activity_spec.operation.value,
        "input_modality": first.activity_spec.input_modality.value,
        "output_modality": first.activity_spec.output_modality.value,
        "cue_policy": first.activity_spec.cue_level.value,
        "stimulus_snapshot": first.activity_spec.to_payload()["snapshot"],
        "feedback_policy_version": first.feedback_policy_version,
        "generator_kind": GeneratorKind.CURATED.value,
        "generator_version": first.generator_version,
        "scorer_kind": first.activity_spec.scorer_kind.value,
        "scorer_version": first.scorer_version,
    }
    expected = sha256(
        json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()

    assert activity_fingerprint(first) == expected
    assert activity_fingerprint(second) == expected
    assert json.dumps(first_source, ensure_ascii=False) == original_bytes


def test_deterministic_rank_components_ties_and_byte_stable_decision() -> None:
    from app.domain.practice import LearningIntent
    from app.domain.selection_policy import (
        AcquireRankComponents,
        AssessRankComponents,
        CuratedActivityCandidateProvider,
        ReviewRankComponents,
        StrengthenRankComponents,
        activity_fingerprint,
    )
    from app.domain.selection_ports import CompletedActivity

    provider = CuratedActivityCandidateProvider()

    def fingerprint(curriculum_target):
        return activity_fingerprint(provider.candidates_for(curriculum_target)[0])

    def repeats(curriculum_target, count):
        candidate_fingerprint = fingerprint(curriculum_target)
        return tuple(
            CompletedActivity(
                target_key=curriculum_target.target_spec.target_key,
                intent=LearningIntent.REVIEW,
                activity_fingerprint=candidate_fingerprint,
                completed_at=NOW - timedelta(days=1, minutes=index),
            )
            for index in range(count)
        )

    review_early = _curriculum_target(
        _target(target_id="10101010-1010-4010-8010-101010101010"),
        priority=1,
    )
    review_late = _curriculum_target(
        _target(target_id="20202020-2020-4020-8020-202020202020"),
        priority=100,
    )
    review_states = {
        review_early.target_spec.target_key: _native_state(
            review_early.target_spec,
            due_at=NOW - timedelta(hours=2),
        ),
        review_late.target_spec.target_key: _native_state(
            review_late.target_spec,
            due_at=NOW - timedelta(hours=1),
        ),
    }
    review_history = repeats(review_early, 2)
    review = _service(
        (review_late, review_early),
        review_states,
        activities=review_history,
    ).select_next(learner_id="learner-1", now=NOW)

    strengthen_large = _curriculum_target(
        _target(target_id="30303030-3030-4030-8030-303030303030"),
        priority=1,
    )
    strengthen_small = _curriculum_target(
        _target(target_id="40404040-4040-4040-8040-404040404040"),
        priority=100,
    )
    strengthen_states = {
        strengthen_large.target_spec.target_key: _native_state(
            strengthen_large.target_spec,
            due_at=NOW + timedelta(days=1),
            success=0,
            failure=3,
        ),
        strengthen_small.target_spec.target_key: _native_state(
            strengthen_small.target_spec,
            due_at=NOW + timedelta(days=1),
            success=0,
            failure=1,
        ),
    }
    strengthen = _service(
        (strengthen_small, strengthen_large),
        strengthen_states,
    ).select_next(learner_id="learner-1", now=NOW)

    acquire_soft = _curriculum_target(
        _target(target_id="50505050-5050-4050-8050-505050505050"),
        priority=80,
        soft_ready_count=2,
    )
    acquire_plain = _curriculum_target(
        _target(target_id="60606060-6060-4060-8060-606060606060"),
        priority=80,
        soft_ready_count=1,
    )
    acquire = _service((acquire_plain, acquire_soft)).select_next(
        learner_id="learner-1",
        now=NOW,
    )

    assess_uncertain = _curriculum_target(
        _target(target_id="70707070-7070-4070-8070-707070707070"),
        priority=1,
    )
    assess_certain = _curriculum_target(
        _target(target_id="80808080-8080-4080-8080-808080808080"),
        priority=100,
    )
    assess_states = {
        assess_uncertain.target_spec.target_key: _native_state(
            assess_uncertain.target_spec,
            due_at=NOW + timedelta(days=1),
            uncertainty=0.9,
        ),
        assess_certain.target_spec.target_key: _native_state(
            assess_certain.target_spec,
            due_at=NOW + timedelta(days=1),
            uncertainty=0.2,
        ),
    }
    assess = _service(
        (assess_certain, assess_uncertain),
        assess_states,
    ).select_next(learner_id="learner-1", now=NOW)

    assert review.rank_components == ReviewRankComponents(
        memory_due_at=NOW - timedelta(hours=2),
        priority=1,
        repetition_count_7d=2,
        target_key=review_early.target_spec.target_key,
        activity_fingerprint=fingerprint(review_early),
    )
    assert strengthen.rank_components == StrengthenRankComponents(
        weakness_gap=3,
        priority=1,
        repetition_count_7d=0,
        target_key=strengthen_large.target_spec.target_key,
        activity_fingerprint=fingerprint(strengthen_large),
    )
    assert acquire.rank_components == AcquireRankComponents(
        priority=80,
        soft_ready_count=2,
        repetition_count_7d=0,
        target_key=acquire_soft.target_spec.target_key,
        activity_fingerprint=fingerprint(acquire_soft),
    )
    assert assess.rank_components == AssessRankComponents(
        uncertainty=0.9,
        last_evidence_at=NOW - timedelta(days=2),
        priority=1,
        target_key=assess_uncertain.target_spec.target_key,
        activity_fingerprint=fingerprint(assess_uncertain),
    )

    tie_low = _curriculum_target(
        _target(target_id="11111111-2222-4222-8222-222222222222"),
        priority=50,
    )
    tie_high = _curriculum_target(
        _target(target_id="99999999-2222-4222-8222-222222222222"),
        priority=50,
    )
    forward = _service((tie_high, tie_low)).select_next(
        learner_id="learner-1",
        now=NOW,
    )
    reverse = _service((tie_low, tie_high)).select_next(
        learner_id="learner-1",
        now=NOW,
    )
    forward_bytes = json.dumps(
        forward.to_payload(),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    reverse_bytes = json.dumps(
        reverse.to_payload(),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    assert forward == reverse
    assert forward.target_key == tie_low.target_spec.target_key
    assert forward.activity_fingerprint == fingerprint(tie_low)
    assert forward.reason_codes[0].value == "new_target"
    assert forward.policy_version == "selector-v1"
    assert forward_bytes == reverse_bytes
