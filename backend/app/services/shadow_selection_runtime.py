from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.curriculum_policy import CurriculumFrontierPolicy, FrontierAvailability
from app.domain.practice import ActivityStatus, LearningIntent
from app.domain.selection_policy import (
    ActivityValidityPolicy,
    CuratedActivityCandidateProvider,
)
from app.domain.selection_ports import CompletedActivity, CurriculumTarget
from app.domain.shared import Capability, TargetKind
from app.domain.target import TargetSpec
from app.domain_models.catalog import LanguageForm, LanguageLexicalUnit, LanguageSense
from app.domain_models.curriculum import CurriculumVersionRecord
from app.domain_models.practice import ActivityInstanceModel, PracticeRunModel
from app.domain_models.progress import LearnerTargetStateModel
from app.repositories.practice import _activity_to_domain
from app.repositories.progress import ProgressRepository, _to_domain
from app.repositories.curriculum import _version_value
from app.services.catalog_mapping_service import resolve_catalog_mapping
from app.services.curriculum_service import PILOT_CURRICULUM_CODE
from app.services.next_activity_service import NextActivityService
from app.services.shadow_comparison_service import (
    ApplicationComparisonLogger,
    LegacyLearningSelection,
    LegacyLearningSelectionKind,
    ShadowComparisonService,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class _ProfilePort:
    def __init__(self, session: Session) -> None:
        self._repository = ProgressRepository(session)

    def get_profile(self, learner_id: str):
        return self._repository.get_profile(learner_id)


class _ProgressPort:
    def __init__(self, session: Session) -> None:
        self._session = session

    def states_for_targets(self, *, learner_id: str, target_keys):
        keys = tuple(target_keys)
        if not keys:
            return {}
        rows = self._session.scalars(
            select(LearnerTargetStateModel).where(
                LearnerTargetStateModel.learner_id == learner_id,
                LearnerTargetStateModel.target_key.in_(keys),
            )
        )
        return {row.target_key: _to_domain(row) for row in rows}


class _CurriculumPort:
    def __init__(self, session: Session) -> None:
        self._session = session

    def active_frontier(self, profile):
        version = self._session.scalar(
            select(CurriculumVersionRecord).where(
                CurriculumVersionRecord.curriculum_code == PILOT_CURRICULUM_CODE,
                CurriculumVersionRecord.status == "active",
            )
        )
        if version is None:
            return None
        curriculum = _version_value(version)
        states = _ProgressPort(self._session).states_for_targets(
            learner_id=profile.learner_id,
            target_keys=(node.target.target_key for node in curriculum.nodes),
        )
        decisions = CurriculumFrontierPolicy().evaluate(
            curriculum,
            states_by_target_key=states,
            requested_level=profile.requested_level,
        )
        targets = []
        for decision in decisions:
            node = decision.node
            target = node.target
            snapshot = self._stimulus(target)
            targets.append(
                CurriculumTarget(
                    target_spec=target,
                    priority=node.priority,
                    outcome_code=node.outcome_code,
                    hard_ready=(
                        decision.availability is FrontierAvailability.AVAILABLE
                    ),
                    soft_ready_count=decision.soft_ready_count,
                    content_published=snapshot is not None,
                    stimulus_snapshot=snapshot or {},
                )
            )
        return tuple(targets)

    def _stimulus(self, target: TargetSpec) -> dict[str, object] | None:
        if target.target_kind is not TargetKind.SENSE:
            return None
        sense = self._session.get(LanguageSense, target.target_id)
        if sense is None or sense.status != "published" or not sense.glosses:
            return None
        lexical = self._session.get(LanguageLexicalUnit, sense.lexical_unit_id)
        form = self._session.scalar(
            select(LanguageForm)
            .where(
                LanguageForm.lexical_unit_id == sense.lexical_unit_id,
                LanguageForm.status == "published",
                LanguageForm.form_kind.in_(("citation", "fixed")),
            )
            .order_by(LanguageForm.id)
        )
        if lexical is None or lexical.status != "published" or form is None:
            return None
        gloss = str(sense.glosses[0].get("text") or "")
        serbian = next(
            (
                item.get("text")
                for item in form.orthographies
                if item.get("script") == "latin"
            ),
            None,
        )
        if not gloss or not isinstance(serbian, str) or not serbian:
            return None
        if target.capability is Capability.RETRIEVE_FORM:
            return {
                "cue": {"language": "ru", "text": gloss},
                "expected": {"language": "sr", "text": serbian},
            }
        catalog_options = tuple(
            dict.fromkeys(
                str(item.get("text") or "")
                for glosses in self._session.scalars(
                    select(LanguageSense.glosses)
                    .where(LanguageSense.status == "published")
                    .order_by(LanguageSense.id)
                )
                for item in glosses[:1]
                if item.get("text")
            )
        )
        options = tuple(dict.fromkeys((gloss, *catalog_options)))[:4]
        return {"cue": serbian, "options": options, "expected": gloss}


def _activity_fingerprint(activity) -> str:
    spec = activity.spec
    payload = {
        "schema_version": 1,
        "target_key": spec.target_key,
        "activity_kind": spec.activity_kind.value,
        "operation": None if spec.operation is None else spec.operation.value,
        "input_modality": spec.input_modality.value,
        "output_modality": (
            None if spec.output_modality is None else spec.output_modality.value
        ),
        "cue_policy": spec.cue_level.value,
        "stimulus_snapshot": spec.to_payload()["snapshot"],
        "feedback_policy_version": activity.feedback_policy_version,
        "generator_kind": activity.generator_kind.value,
        "generator_version": activity.generator_version,
        "scorer_kind": (
            None if spec.scorer_kind is None else spec.scorer_kind.value
        ),
        "scorer_version": activity.scorer_version,
    }

    def normalize(value):
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            return {normalize(key): normalize(item) for key, item in value.items()}
        return value

    serialized = json.dumps(
        normalize(payload),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class _HistoryPort:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _rows(self, learner_id: str, started_at: datetime, ended_at: datetime):
        return tuple(
            self._session.scalars(
                select(ActivityInstanceModel)
                .join(PracticeRunModel)
                .where(
                    PracticeRunModel.learner_id == learner_id,
                    ActivityInstanceModel.status == ActivityStatus.COMPLETED.value,
                    ActivityInstanceModel.terminal_at >= started_at,
                    ActivityInstanceModel.terminal_at < ended_at,
                )
                .order_by(ActivityInstanceModel.terminal_at, ActivityInstanceModel.id)
            )
        )

    def first_acquired_target_keys(self, *, learner_id, started_at, ended_at):
        return tuple(
            row.target_key
            for row in self._rows(learner_id, started_at, ended_at)
            if row.learning_intent == LearningIntent.ACQUIRE.value
        )

    def completed_activities(self, *, learner_id, started_at, ended_at):
        result = []
        for row in self._rows(learner_id, started_at, ended_at):
            activity = _activity_to_domain(row)
            if activity.terminal_at is None:
                continue
            result.append(
                CompletedActivity(
                    target_key=activity.target_key,
                    intent=activity.learning_intent,
                    activity_fingerprint=_activity_fingerprint(activity),
                    completed_at=activity.terminal_at,
                )
            )
        return tuple(result)


def run_selection_comparison(
    *,
    bind,
    learner_id: str,
    kind: LegacyLearningSelectionKind,
    word_id: int | None,
):
    if not settings.language_assistant_shadow_enabled:
        return None
    comparison_logger = ApplicationComparisonLogger()
    try:
        with Session(bind=bind) as session:
            target_key = None
            if word_id is not None:
                target_key = resolve_catalog_mapping(
                    session,
                    word_id,
                    capability=Capability.RETRIEVE_FORM,
                    lock_source=False,
                ).target.target_key
            legacy = LegacyLearningSelection(kind=kind, target_key=target_key)
            selector = NextActivityService(
                profile_port=_ProfilePort(session),
                curriculum_port=_CurriculumPort(session),
                progress_port=_ProgressPort(session),
                history_port=_HistoryPort(session),
                candidate_provider=CuratedActivityCandidateProvider(),
                validity_policy=ActivityValidityPolicy(),
            )
            return ShadowComparisonService(
                comparison_logger=comparison_logger
            ).compare(
                legacy_selection=legacy,
                select_shadow=lambda: selector.select_next(
                    learner_id=learner_id,
                    now=datetime.now(timezone.utc),
                ),
            )
    except Exception:
        comparison_logger(None)
        return None
