"""Read-only v1 evidence labels must not turn retries or missing context into mastery."""

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.domain.evidence import EvidenceClass, EvidenceObservation, classify_observation
from app.services.evidence_diagnostics import diagnose_observations, observe_learning_event


FIXTURE = Path(__file__).parent / "fixtures" / "learning" / "baseline-v1.json"


def _observation(row, event_id):
    return EvidenceObservation(
        event_id=event_id,
        target_key=row["target"],
        occurred_at=datetime.fromisoformat(row["at"]),
        event_type="exposure" if row["kind"] == "exposure" else "response_evaluated",
        evaluation_source=row.get("source"),
        evaluation_outcome=(
            "unknown" if row.get("source") == "self_report" else row.get("outcome")
        ),
        has_first_response=row["kind"] == "response",
        hints=() if row.get("support", "none") == "none" else (row["support"],),
        retry_of_activity_id=row.get("repair_of"),
        attempt_number=row.get("ordinal", 1),
        context_family_id=row.get("context_family"),
        content_revision_id="fixture-v1",
        activity_instance_id=row.get("activity_id"),
        support_timing=row.get("support_timing"),
        held_out=row.get("held_out"),
    )


def test_diagnostics_reconcile_with_frozen_learning_histories():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    observations = [
        _observation(row, f"{case['id']}:{index}")
        for case in fixture["cases"]
        for index, row in enumerate(case["events"])
    ]
    result = diagnose_observations(observations)
    assert result.version == 1
    assert result.first_eligible == 5
    assert result.first_correct == 4
    assert result.recovered == 1
    assert result.assisted_correct == 1
    assert result.self_reports == 1
    assert result.unresolved == 1
    assert result.distinct_contexts == 4
    assert result.targets_with_multiple_contexts == 1
    assert result.delayed_new_context_eligible == 1
    assert result.delayed_new_context_correct == 1


def test_unversioned_shadow_context_cannot_prove_independent_occasion():
    event = SimpleNamespace(
        event_id="old-event", target_key="target-1",
        occurred_at=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        event_type="response_evaluated", evaluation_source="deterministic",
        evaluation_outcome="correct", first_response=object(), hints=(),
    )
    activity = SimpleNamespace(
        retry_of_activity_instance_id=None, attempt_number=1,
        spec=SimpleNamespace(snapshot={"legacy_question_type": "ru_to_sr_typing"}),
    )
    observation = observe_learning_event(activity, event)
    assert classify_observation(observation) is EvidenceClass.FIRST_UNAIDED_CORRECT
    result = diagnose_observations([observation])
    assert result.first_correct == 1
    assert result.distinct_contexts == 0
    assert result.context_unknown == 1


def test_missing_support_or_retry_metadata_stays_unknown():
    base = _observation(
        {"kind": "response", "target": "t", "at": "2026-01-01T00:00:00+00:00",
         "source": "deterministic", "outcome": "correct", "ordinal": 1},
        "event-1",
    )
    assert classify_observation(replace(base, hints=None)) is EvidenceClass.UNKNOWN
    assert classify_observation(replace(base, attempt_number=None)) is EvidenceClass.UNKNOWN
    assert classify_observation(replace(base, evaluation_source="model_assisted")) is EvidenceClass.UNRESOLVED
    assert classify_observation(replace(base, evaluation_outcome="partial")) is EvidenceClass.UNRESOLVED


def test_out_of_order_and_duplicate_events_keep_counts_stable():
    early = _observation(
        {"kind": "response", "target": "t", "context_family": "first",
         "at": "2026-01-01T00:00:00+00:00", "source": "deterministic",
         "outcome": "incorrect", "ordinal": 1}, "event-1",
    )
    late = _observation(
        {"kind": "response", "target": "t", "context_family": "later",
         "at": "2026-01-09T00:00:00+00:00", "source": "deterministic",
         "outcome": "correct", "ordinal": 1, "held_out": True}, "event-2",
    )
    result = diagnose_observations([late, early, late])
    assert (result.first_eligible, result.first_correct) == (2, 1)
    assert (result.delayed_new_context_eligible, result.delayed_new_context_correct) == (1, 1)


def test_read_only_history_adapter_loads_only_own_shadow_events(client, db_session, seeded_words, monkeypatch):
    from sqlalchemy import func, select
    from app.config import settings
    from app.domain_models.practice import LearningEventModel
    from app.services.domain_bootstrap_service import bootstrap_catalog
    from app.services.evidence_diagnostics import diagnose_learner_history

    bootstrap_catalog(db_session)
    monkeypatch.setattr(settings, "language_assistant_shadow_enabled", True)
    response = client.post(
        "/api/learning/learner-1/new-words/complete",
        json={"word_ids": [seeded_words[0].id, seeded_words[1].id]},
    )
    assert response.status_code == 200
    before = db_session.scalar(select(func.count()).select_from(LearningEventModel))
    result = diagnose_learner_history(db_session, "learner-1")
    other = diagnose_learner_history(db_session, "learner-2")

    assert result.counts == {"exposure": 2}
    assert result.first_eligible == 0
    assert other.counts == {}
    assert db_session.scalar(select(func.count()).select_from(LearningEventModel)) == before
    assert not db_session.dirty


def test_mixed_final_response_and_unknown_hint_timing_cannot_prove_first_success():
    first = _observation(
        {"kind": "response", "target": "t", "activity_id": "activity",
         "at": "2026-01-01T00:00:00+00:00", "source": "deterministic",
         "outcome": "correct", "ordinal": 1}, "mixed",
    )
    assert classify_observation(replace(first, has_final_response=True)) is EvidenceClass.UNKNOWN
    assert classify_observation(replace(first, repair_outcome="repaired")) is EvidenceClass.UNKNOWN
    assert classify_observation(replace(first, hints=("cue",))) is EvidenceClass.UNKNOWN
    assert classify_observation(replace(first, hints=("cue",), support_timing="before_first")) is EvidenceClass.ASSISTED_CORRECT


def test_recovery_requires_matching_incorrect_parent_activity():
    first = _observation(
        {"kind": "response", "target": "t", "activity_id": "activity",
         "at": "2026-01-01T00:00:00+00:00", "source": "deterministic",
         "outcome": "correct", "ordinal": 1}, "first",
    )
    retry = _observation(
        {"kind": "response", "target": "t", "activity_id": "retry",
         "at": "2026-01-01T00:01:00+00:00", "source": "deterministic",
         "outcome": "correct", "ordinal": 2, "repair_of": "activity"}, "second",
    )
    assert diagnose_observations([first, retry]).recovered == 0
    assert diagnose_observations([retry]).recovered == 0
    assert diagnose_observations([replace(first, evaluation_outcome="incorrect"), retry]).recovered == 1


def test_delayed_probe_requires_known_prior_family_and_explicit_holdout():
    old_unknown = _observation(
        {"kind": "response", "target": "t", "activity_id": "old",
         "at": "2026-01-01T00:00:00+00:00", "source": "deterministic",
         "outcome": "correct", "ordinal": 1}, "old",
    )
    new = _observation(
        {"kind": "response", "target": "t", "activity_id": "new",
         "context_family": "new", "held_out": True,
         "at": "2026-01-09T00:00:00+00:00", "source": "deterministic",
         "outcome": "correct", "ordinal": 1}, "new",
    )
    assert diagnose_observations([old_unknown, new]).delayed_new_context_eligible == 0
    known_prior = replace(old_unknown, context_family_id="old")
    assert diagnose_observations([known_prior, replace(new, held_out=None)]).delayed_new_context_eligible == 0
    assert diagnose_observations([known_prior, new]).delayed_new_context_eligible == 1


def test_persisted_mixed_event_does_not_infer_first_verdict_or_hint_order():
    event = SimpleNamespace(
        event_id="mixed", target_key="target-1", activity_instance_id="activity-1",
        occurred_at=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        event_type="response_evaluated", evaluation_source="deterministic",
        evaluation_outcome="correct", first_response=object(), final_response=object(),
        repair_outcome="repaired", hints=(SimpleNamespace(kind="cue"),),
    )
    activity = SimpleNamespace(
        retry_of_activity_instance_id=None, attempt_number=1,
        spec=SimpleNamespace(snapshot={
            "context_family_id": "known", "content_revision_id": "r1",
            "support_timing": "before_first", "held_out": True,
        }),
    )
    observation = observe_learning_event(activity, event)
    assert observation.support_timing is None
    assert observation.has_final_response is True
    assert observation.repair_outcome == "repaired"
    assert classify_observation(observation) is EvidenceClass.UNKNOWN
    assert diagnose_observations([observation]).first_eligible == 0
