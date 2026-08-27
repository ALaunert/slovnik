from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.catalog import ContentStatus, FormKind
from app.domain.practice import (
    ActivityInstance,
    ActivityKind,
    ActivitySpec,
    ActivityStatus,
    CueLevel,
    Evaluation,
    EvaluationOutcome,
    EvaluationSource,
    ExerciseOperation,
    GeneratorKind,
    LearningEvent,
    LearningEventRequest,
    LearningIntent,
    PracticeRun,
    PracticeRunStatus,
    ResponseKind,
    ResponseSnapshot,
    ScorerKind,
    SelectionMetadata,
    SelectionReason,
    SelfReportRating,
    build_learning_event,
)
from app.domain.shared import Capability, Modality, TargetKind
from app.domain.progress import MEMORY_POLICY_VERSION
from app.domain.target import TargetSpec
from app.domain_models.catalog import LanguageForm, LanguageLexicalUnit, LanguageSense
from app.domain_models.practice import LearningEventModel
from app.models import UserWordProgress
from app.repositories.practice import PracticeRepository
from app.repositories.progress import ProgressRepository
from app.services.domain_shadow_contracts import (
    NewWordIdempotencyInput,
    ReviewIdempotencyInput,
    ShadowAdapterResult,
    ShadowAdapterStatus,
    ShadowLegacySourceKind,
    ShadowLegacySourceRef,
    ShadowPolicyVersion,
)
from app.services.learner_projection_service import LearnerProjectionService


GENERATOR_KIND = GeneratorKind.CURATED
NEW_WORD_POLICY = ShadowPolicyVersion.LEGACY_NEW_WORD_V1.value
REVIEW_POLICY = ShadowPolicyVersion.LEGACY_REVIEW_V1.value


class ShadowLearningFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class _LexicalMapping:
    target: TargetSpec
    citation_form_snapshot: dict[str, object]


class _PracticeEventSource:
    def __init__(self, session: Session, repository: PracticeRepository) -> None:
        self._session = session
        self._repository = repository

    def events_for_target(
        self,
        *,
        learner_id: str,
        target_key: str,
    ) -> tuple[LearningEvent, ...]:
        keys = self._session.execute(
            select(
                LearningEventModel.learner_id,
                LearningEventModel.idempotency_key,
            )
            .where(
                LearningEventModel.learner_id == learner_id,
                LearningEventModel.target_key == target_key,
            )
            .order_by(LearningEventModel.occurred_at, LearningEventModel.id)
        )
        events = tuple(
            self._repository.get_learning_event(event_learner_id, idempotency_key)
            for event_learner_id, idempotency_key in keys
        )
        if any(event is None for event in events):
            raise ShadowLearningFailure("Stored shadow evidence disappeared")
        return tuple(event for event in events if event is not None)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _resolve_mapping(session: Session, word_id: int) -> _LexicalMapping:
    sense_ids = tuple(
        session.scalars(
            select(LanguageSense.id)
            .join(LanguageLexicalUnit)
            .where(
                LanguageLexicalUnit.legacy_vocabulary_item_id == word_id,
                LanguageLexicalUnit.status == ContentStatus.PUBLISHED.value,
                LanguageSense.status == ContentStatus.PUBLISHED.value,
            )
            .order_by(LanguageSense.id)
        )
    )
    forms = tuple(
        session.scalars(
            select(LanguageForm)
            .join(LanguageLexicalUnit)
            .where(
                LanguageLexicalUnit.legacy_vocabulary_item_id == word_id,
                LanguageLexicalUnit.status == ContentStatus.PUBLISHED.value,
                LanguageForm.status == ContentStatus.PUBLISHED.value,
                LanguageForm.form_kind == FormKind.CITATION.value,
            )
            .order_by(LanguageForm.id)
        )
    )
    if len(sense_ids) != 1 or len(forms) != 1:
        raise ShadowLearningFailure("Legacy word has no unique published lexical mapping")
    form = forms[0]
    return _LexicalMapping(
        target=TargetSpec(
            target_kind=TargetKind.SENSE,
            target_id=sense_ids[0],
            capability=Capability.RETRIEVE_FORM,
            modality=Modality.WRITTEN,
        ),
        citation_form_snapshot={
            "id": form.id,
            "form_kind": form.form_kind,
            "orthographies": form.orthographies,
        },
    )


def _selection(policy_version: str, reason: SelectionReason) -> SelectionMetadata:
    return SelectionMetadata(policy_version=policy_version, reasons=(reason,))


def _new_word_activity(
    *,
    run_id: str,
    sequence_number: int,
    mapping: _LexicalMapping,
    occurred_at: datetime,
) -> ActivityInstance:
    return ActivityInstance(
        id=str(uuid4()),
        practice_run_id=run_id,
        spec=ActivitySpec(
            target_spec=mapping.target,
            activity_kind=ActivityKind.EXPOSURE,
            operation=None,
            cue_level=CueLevel.FULL,
            output_modality=None,
            scorer_kind=None,
            snapshot={"citation_form": mapping.citation_form_snapshot},
        ),
        learning_intent=LearningIntent.ACQUIRE,
        sequence_number=sequence_number,
        retry_of_activity_instance_id=None,
        attempt_number=1,
        selection=_selection(NEW_WORD_POLICY, SelectionReason.LEGACY_NEW_WORD),
        generator_kind=GENERATOR_KIND,
        generator_version=NEW_WORD_POLICY,
        scorer_version=None,
        status=ActivityStatus.PENDING,
        selected_at=occurred_at,
        terminal_at=None,
    )


def _review_activity(
    *,
    run_id: str,
    mapping: _LexicalMapping,
    occurred_at: datetime,
) -> ActivityInstance:
    return ActivityInstance(
        id=str(uuid4()),
        practice_run_id=run_id,
        spec=ActivitySpec(
            target_spec=mapping.target,
            activity_kind=ActivityKind.EXERCISE,
            operation=ExerciseOperation.RETRIEVE,
            cue_level=CueLevel.MINIMAL,
            output_modality=Modality.WRITTEN,
            scorer_kind=ScorerKind.SELF_REPORT,
            snapshot={
                "citation_form": mapping.citation_form_snapshot,
                "response_contract": {"kind": ResponseKind.RATING.value},
            },
        ),
        learning_intent=LearningIntent.REVIEW,
        sequence_number=1,
        retry_of_activity_instance_id=None,
        attempt_number=1,
        selection=_selection(REVIEW_POLICY, SelectionReason.LEGACY_REVIEW),
        generator_kind=GENERATOR_KIND,
        generator_version=REVIEW_POLICY,
        scorer_version=MEMORY_POLICY_VERSION,
        status=ActivityStatus.PENDING,
        selected_at=occurred_at,
        terminal_at=None,
    )


def _duplicate_result(events: tuple[LearningEvent, ...]) -> ShadowAdapterResult:
    run_ids = {event.practice_run_id for event in events}
    if len(run_ids) != 1:
        raise ShadowLearningFailure("Shadow idempotency keys span multiple practice runs")
    return ShadowAdapterResult(
        status=ShadowAdapterStatus.DUPLICATE,
        practice_run_id=next(iter(run_ids)),
        activity_instance_ids=tuple(event.activity_instance_id for event in events),
        event_ids=tuple(event.event_id for event in events),
    )


def _new_word_idempotency_key(
    learner_id: str,
    progress: UserWordProgress,
) -> str:
    if progress.first_seen_at is None:
        raise ShadowLearningFailure("Legacy new-word progress has no first_seen_at")
    return NewWordIdempotencyInput(
        learner_ref=learner_id,
        progress_id=progress.id,
        first_seen_at=_utc(progress.first_seen_at),
    ).key


def _review_idempotency_key(
    progress: UserWordProgress,
    locked_due_at: datetime | None,
    rating: str,
) -> tuple[str, SelfReportRating]:
    try:
        rating_value = SelfReportRating(rating)
    except ValueError as exc:
        raise ShadowLearningFailure("Legacy review rating is invalid") from exc
    return (
        ReviewIdempotencyInput(
            progress_id=progress.id,
            locked_due_at=locked_due_at,
            rating=rating_value,
        ).key,
        rating_value,
    )


def record_new_word_batch(
    session: Session,
    *,
    learner_id: str,
    progress_rows: tuple[UserWordProgress, ...],
    occurred_at: datetime,
) -> ShadowAdapterResult:
    if not progress_rows:
        raise ShadowLearningFailure("Shadow new-word batch must not be empty")
    at = _utc(occurred_at)
    repository = PracticeRepository(session)
    idempotency_keys = tuple(
        _new_word_idempotency_key(learner_id, row) for row in progress_rows
    )
    duplicates = tuple(
        repository.get_learning_event(learner_id, key) for key in idempotency_keys
    )
    if all(event is not None for event in duplicates):
        return _duplicate_result(tuple(event for event in duplicates if event is not None))
    if any(event is not None for event in duplicates):
        raise ShadowLearningFailure("Shadow new-word batch is partially duplicated")
    mappings = tuple(_resolve_mapping(session, row.word_id) for row in progress_rows)

    run = PracticeRun(
        id=str(uuid4()),
        learner_id=learner_id,
        curriculum_version_id=None,
        legacy_quiz_attempt_id=None,
        status=PracticeRunStatus.ACTIVE,
        selection_policy_version=NEW_WORD_POLICY,
        started_at=at,
        ended_at=None,
    )
    repository.add_run(run)
    projector = LearnerProjectionService(
        ProgressRepository(session),
        _PracticeEventSource(session, repository),
    )
    completed_activities: list[ActivityInstance] = []
    events: list[LearningEvent] = []
    for sequence_number, (row, mapping, idempotency_key) in enumerate(
        zip(progress_rows, mappings, idempotency_keys, strict=True),
        start=1,
    ):
        activity = _new_word_activity(
            run_id=run.id,
            sequence_number=sequence_number,
            mapping=mapping,
            occurred_at=at,
        )
        repository.add_activity(run, activity)
        received_at = repository.database_now()
        event = build_learning_event(
            activity,
            LearningEventRequest(
                event_id=str(uuid4()),
                learner_id=learner_id,
                activity_instance_id=activity.id,
                idempotency_key=idempotency_key,
                occurred_at=at,
                legacy_source=ShadowLegacySourceRef(
                    kind=ShadowLegacySourceKind.NEW_WORD,
                    reference=f"user_word_progress:{row.id}",
                ).to_domain(),
            ),
            created_at=received_at,
            received_at=received_at,
        )
        completed = activity.complete(at)
        repository.add_learning_event(event)
        repository.update_activity(completed)
        projector.apply_event(event)
        completed_activities.append(completed)
        events.append(event)
    repository.update_run(run.complete(tuple(completed_activities), at))
    return ShadowAdapterResult(
        status=ShadowAdapterStatus.RECORDED,
        practice_run_id=run.id,
        activity_instance_ids=tuple(activity.id for activity in completed_activities),
        event_ids=tuple(event.event_id for event in events),
    )


def record_review_rating(
    session: Session,
    *,
    learner_id: str,
    progress: UserWordProgress,
    locked_due_at: datetime | None,
    rating: str,
    occurred_at: datetime,
) -> ShadowAdapterResult:
    at = _utc(occurred_at)
    idempotency_key, rating_value = _review_idempotency_key(
        progress,
        locked_due_at,
        rating,
    )
    repository = PracticeRepository(session)
    duplicate = repository.get_learning_event(learner_id, idempotency_key)
    if duplicate is not None:
        return _duplicate_result((duplicate,))

    mapping = _resolve_mapping(session, progress.word_id)
    run = PracticeRun(
        id=str(uuid4()),
        learner_id=learner_id,
        curriculum_version_id=None,
        legacy_quiz_attempt_id=None,
        status=PracticeRunStatus.ACTIVE,
        selection_policy_version=REVIEW_POLICY,
        started_at=at,
        ended_at=None,
    )
    repository.add_run(run)
    activity = _review_activity(
        run_id=run.id,
        mapping=mapping,
        occurred_at=at,
    )
    repository.add_activity(run, activity)
    response = ResponseSnapshot(kind=ResponseKind.RATING, value=rating_value.value)
    received_at = repository.database_now()
    event = build_learning_event(
        activity,
        LearningEventRequest(
            event_id=str(uuid4()),
            learner_id=learner_id,
            activity_instance_id=activity.id,
            idempotency_key=idempotency_key,
            occurred_at=at,
            first_response=response,
            evaluation=Evaluation(
                source=EvaluationSource.SELF_REPORT,
                outcome=EvaluationOutcome.UNKNOWN,
            ),
            legacy_source=ShadowLegacySourceRef(
                kind=ShadowLegacySourceKind.REVIEW,
                reference=f"user_word_progress:{progress.id}",
            ).to_domain(),
        ),
        created_at=received_at,
        received_at=received_at,
    )
    completed = activity.complete(at)
    repository.add_learning_event(event)
    repository.update_activity(completed)
    LearnerProjectionService(
        ProgressRepository(session),
        _PracticeEventSource(session, repository),
    ).apply_event(event)
    repository.update_run(run.complete((completed,), at))
    return ShadowAdapterResult(
        status=ShadowAdapterStatus.RECORDED,
        practice_run_id=run.id,
        activity_instance_ids=(activity.id,),
        event_ids=(event.event_id,),
    )
