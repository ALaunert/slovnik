from __future__ import annotations

from types import SimpleNamespace
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select


def _decision(*, intent=None, target_key=None, reasons=(), decision_code=None):
    from app.domain.practice import LearningIntent, SelectionReason
    from app.domain.selection_policy import DecisionCode

    return SimpleNamespace(
        policy_version="selector-v1",
        intent=None if intent is None else LearningIntent(intent),
        target_key=target_key,
        reason_codes=tuple(SelectionReason(reason) for reason in reasons),
        decision_code=(
            None if decision_code is None else DecisionCode(decision_code)
        ),
    )


@pytest.mark.parametrize(
    (
        "legacy_kind",
        "legacy_target",
        "shadow_decision",
        "expected_legacy_intent",
        "expected_category",
        "expected_reasons",
    ),
    [
        (
            "due",
            "v1:sense:target-a",
            _decision(
                intent="review",
                target_key="v1:sense:target-a",
                reasons=("due_review",),
            ),
            "review",
            "agreement",
            ("legacy_review", "due_review"),
        ),
        (
            "new",
            "v1:sense:target-a",
            _decision(
                intent="acquire",
                target_key="v1:sense:target-b",
                reasons=("new_target",),
            ),
            "acquire",
            "target_difference",
            ("legacy_new_word", "new_target"),
        ),
        (
            "weak",
            "v1:sense:target-a",
            _decision(
                intent="strengthen",
                target_key="v1:sense:target-a",
                reasons=("weak_competence",),
            ),
            "review",
            "intent_difference",
            ("legacy_review", "weak_competence"),
        ),
        (
            "due",
            "v1:sense:target-a",
            _decision(decision_code="no_active_curriculum"),
            "review",
            "shadow_no_activity",
            ("legacy_review", "due_review", "no_active_curriculum"),
        ),
        (
            "none",
            None,
            _decision(
                intent="acquire",
                target_key="v1:sense:target-b",
                reasons=("new_target",),
            ),
            None,
            "legacy_no_activity",
            ("new_target",),
        ),
    ],
)
def test_due_new_and_weak_comparisons_have_stable_categories_and_reasons(
    legacy_kind,
    legacy_target,
    shadow_decision,
    expected_legacy_intent,
    expected_category,
    expected_reasons,
) -> None:
    from app.services.shadow_comparison_service import (
        LegacyLearningSelection,
        LegacyLearningSelectionKind,
        build_shadow_comparison,
    )

    legacy = LegacyLearningSelection(
        kind=LegacyLearningSelectionKind(legacy_kind),
        target_key=legacy_target,
    )

    comparison = build_shadow_comparison(legacy, shadow_decision)

    assert comparison.policy_version == "selector-v1"
    assert (
        None if comparison.legacy_intent is None else comparison.legacy_intent.value
    ) == expected_legacy_intent
    assert comparison.shadow_intent is shadow_decision.intent
    assert comparison.selected_target_key == shadow_decision.target_key
    assert comparison.category.value == expected_category
    assert tuple(reason.value for reason in comparison.reason_codes) == expected_reasons


class _ProfilePort:
    def __init__(self, profile) -> None:
        self.profile = profile

    def get_profile(self, learner_id):
        return self.profile


class _CurriculumPort:
    def __init__(self, frontier) -> None:
        self.frontier = frontier

    def active_frontier(self, profile):
        return self.frontier


class _ProgressPort:
    def __init__(self, states) -> None:
        self.states = states

    def states_for_targets(self, *, learner_id, target_keys):
        return {key: self.states[key] for key in target_keys if key in self.states}


class _HistoryPort:
    def __init__(self, completed) -> None:
        self.completed = completed

    def first_acquired_target_keys(self, **kwargs):
        return ()

    def completed_activities(self, **kwargs):
        return tuple(self.completed)


def _selector_fixture():
    from app.domain.progress import LearnerProfile
    from app.domain.selection_policy import (
        ActivityValidityPolicy,
        CuratedActivityCandidateProvider,
    )
    from app.domain.selection_ports import CurriculumTarget
    from app.domain.shared import Capability, Modality, TargetKind
    from app.domain.target import TargetSpec
    from app.services.next_activity_service import NextActivityService

    target_spec = TargetSpec(
        target_kind=TargetKind.SENSE,
        target_id="11111111-1111-4111-8111-111111111111",
        capability=Capability.RETRIEVE_FORM,
        modality=Modality.WRITTEN,
    )
    frontier = [
        CurriculumTarget(
            target_spec=target_spec,
            priority=50,
            outcome_code="A1.core",
            hard_ready=True,
            soft_ready_count=0,
            content_published=True,
            stimulus_snapshot={
                "cue": {"language": "ru", "text": "word"},
                "expected": {"language": "sr", "text": "reč"},
            },
        )
    ]
    states = {}
    completed = []
    service = NextActivityService(
        profile_port=_ProfilePort(
            LearnerProfile(
                learner_id="learner-1",
                l1="ru",
                requested_level="A1",
                daily_budget=5,
            )
        ),
        curriculum_port=_CurriculumPort(frontier),
        progress_port=_ProgressPort(states),
        history_port=_HistoryPort(completed),
        candidate_provider=CuratedActivityCandidateProvider(),
        validity_policy=ActivityValidityPolicy(),
    )
    return service, target_spec.target_key, frontier, states, completed


def _selection_snapshot(frontier, states, completed):
    return {
        "catalog": tuple(repr(target.stimulus_snapshot) for target in frontier),
        "curriculum": tuple(
            (
                target.target_spec.target_key,
                target.priority,
                target.outcome_code,
                target.hard_ready,
                target.soft_ready_count,
                target.content_published,
            )
            for target in frontier
        ),
        "states": tuple(sorted(states.items())),
        "history": tuple(completed),
    }


def test_comparison_does_not_mutate_selector_inputs(monkeypatch) -> None:
    from app.config import settings
    from app.services.shadow_comparison_service import (
        LegacyLearningSelection,
        LegacyLearningSelectionKind,
        ShadowComparisonService,
    )

    selector, target_key, frontier, states, completed = _selector_fixture()
    metrics = []
    logs = []
    comparison_service = ShadowComparisonService(
        metrics_recorder=metrics.append,
        comparison_logger=logs.append,
    )
    before = _selection_snapshot(frontier, states, completed)
    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)

    result = selector.compare_non_authoritatively(
        learner_id="learner-1",
        now=datetime(2026, 8, 27, 12, tzinfo=timezone.utc),
        legacy_selection=LegacyLearningSelection(
            LegacyLearningSelectionKind.NEW,
            target_key,
        ),
        comparison_service=comparison_service,
    )

    assert result.category.value == "agreement"
    assert _selection_snapshot(frontier, states, completed) == before
    assert metrics == [result]
    assert logs == [result]


@pytest.mark.parametrize("failure", ["selector", "metrics", "logger"])
def test_selector_metrics_and_logger_failures_are_best_effort(
    monkeypatch,
    failure,
) -> None:
    from app.config import settings
    from app.services.shadow_comparison_service import (
        LegacyLearningSelection,
        LegacyLearningSelectionKind,
        ShadowComparisonService,
    )

    valid_state = {"event_count": 1, "projection_count": 1}
    decision = _decision(
        intent="acquire",
        target_key="v1:sense:target-a",
        reasons=("new_target",),
    )

    def select_shadow():
        if failure == "selector":
            raise RuntimeError("selector failed")
        return decision

    def record_metric(comparison):
        if failure == "metrics":
            raise RuntimeError("metrics failed")

    def record_log(comparison):
        if failure == "logger":
            raise RuntimeError("logger failed")

    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)
    service = ShadowComparisonService(
        metrics_recorder=record_metric,
        comparison_logger=record_log,
    )

    result = service.compare(
        legacy_selection=LegacyLearningSelection(
            LegacyLearningSelectionKind.NEW,
            "v1:sense:target-a",
        ),
        select_shadow=select_shadow,
    )

    if failure == "selector":
        assert result is None
    else:
        assert result is not None
    assert valid_state == {"event_count": 1, "projection_count": 1}


@pytest.mark.parametrize("failure", ["selector", "metrics", "logger"])
def test_diagnostic_failure_does_not_rollback_committed_event_or_projection(
    client,
    db_session,
    monkeypatch,
    failure,
) -> None:
    from app.config import settings
    from app.domain_models.practice import LearningEventModel
    from app.domain_models.progress import LearnerTargetStateModel
    from app.models import UserWordProgress, VocabularyItem
    from app.services.domain_bootstrap_service import bootstrap_catalog
    from app.services.shadow_comparison_service import (
        LegacyLearningSelection,
        LegacyLearningSelectionKind,
        ShadowComparisonService,
    )

    word = VocabularyItem(
        serbian_cyrillic="реч",
        serbian_latin="reč",
        russian_translation="слово",
        cefr_level="A1",
        theme="comparison",
    )
    db_session.add(word)
    db_session.commit()
    bootstrap_catalog(db_session)
    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)
    response = client.post(
        "/api/learning/comparison-valid/new-words/complete",
        json={"word_ids": [word.id]},
    )
    before = (
        db_session.scalar(select(func.count()).select_from(UserWordProgress)),
        db_session.scalar(select(func.count()).select_from(LearningEventModel)),
        db_session.scalar(select(func.count()).select_from(LearnerTargetStateModel)),
    )

    def select_shadow():
        if failure == "selector":
            raise RuntimeError("selector failed")
        return _decision(
            intent="acquire",
            target_key="v1:sense:target-a",
            reasons=("new_target",),
        )

    def record_metric(comparison):
        if failure == "metrics":
            raise RuntimeError("metrics failed")

    def record_log(comparison):
        if failure == "logger":
            raise RuntimeError("logger failed")

    result = ShadowComparisonService(
        metrics_recorder=record_metric,
        comparison_logger=record_log,
    ).compare(
        legacy_selection=LegacyLearningSelection(
            LegacyLearningSelectionKind.NEW,
            "v1:sense:target-a",
        ),
        select_shadow=select_shadow,
    )

    after = (
        db_session.scalar(select(func.count()).select_from(UserWordProgress)),
        db_session.scalar(select(func.count()).select_from(LearningEventModel)),
        db_session.scalar(select(func.count()).select_from(LearnerTargetStateModel)),
    )
    assert response.status_code == 200
    if failure == "selector":
        assert result is None
    else:
        assert result is not None
    assert before == after == (1, 1, 1)


def test_disabled_comparison_does_zero_selector_metrics_or_logger_work(
    monkeypatch,
) -> None:
    from app.config import settings
    from app.services.shadow_comparison_service import (
        LegacyLearningSelection,
        LegacyLearningSelectionKind,
        ShadowComparisonService,
    )

    calls = {"selector": 0, "metrics": 0, "logger": 0}

    def select_shadow():
        calls["selector"] += 1
        return _decision(
            intent="acquire",
            target_key="v1:sense:target-a",
            reasons=("new_target",),
        )

    def record_metric(comparison):
        calls["metrics"] += 1

    def record_log(comparison):
        calls["logger"] += 1

    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", False)
    service = ShadowComparisonService(
        metrics_recorder=record_metric,
        comparison_logger=record_log,
    )

    result = service.compare(
        legacy_selection=LegacyLearningSelection(
            LegacyLearningSelectionKind.NEW,
            "v1:sense:target-a",
        ),
        select_shadow=select_shadow,
    )

    assert result is None
    assert calls == {"selector": 0, "metrics": 0, "logger": 0}


def test_comparison_logs_are_redacted(monkeypatch, caplog) -> None:
    from app.config import settings
    from app.services.shadow_comparison_service import (
        ApplicationComparisonLogger,
        LegacyLearningSelection,
        LegacyLearningSelectionKind,
        ShadowComparisonService,
    )

    learner_secret = "private-learner-id"
    response_secret = "raw-response-secret"
    translation_secret = "secret-russian-translation"

    def fail_selector():
        raise RuntimeError(
            f"{learner_secret} {response_secret} {translation_secret}"
        )

    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)
    result = ShadowComparisonService(
        comparison_logger=ApplicationComparisonLogger(),
    ).compare(
        legacy_selection=LegacyLearningSelection(
            LegacyLearningSelectionKind.NEW,
            "v1:sense:target-a",
        ),
        select_shadow=fail_selector,
    )

    messages = " ".join(record.getMessage() for record in caplog.records)
    record_payloads = " ".join(repr(record.__dict__) for record in caplog.records)
    assert result is None
    assert "Shadow selection comparison failed" in messages
    assert all(record.exc_info is None for record in caplog.records)
    for secret in (learner_secret, response_secret, translation_secret):
        assert secret not in messages
        assert secret not in record_payloads
