import hashlib
import logging
import unicodedata
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
    LearningIntent,
    LearningEvent,
    LearningEventRequest,
    PracticeRun,
    PracticeRunStatus,
    ResponseKind,
    ResponseSnapshot,
    ScorerKind,
    SelfReportRating,
    SelectionMetadata,
    SelectionReason,
    build_learning_event,
)
from app.domain.progress import MEMORY_POLICY_VERSION
from app.domain.shared import Capability, Modality, TargetKind
from app.domain.target import TargetSpec
from app.domain_models.practice import LearningEventModel, PracticeRunModel
from app.models import QuizAnswer, QuizAttempt
from app.repositories.practice import PracticeRepository
from app.repositories.progress import ProgressRepository
from app.services.domain_shadow_contracts import (
    QuizAnswerIdempotencyInput,
    ShadowLegacySourceKind,
    ShadowLegacySourceRef,
    ShadowPolicyVersion,
)
from app.services.learner_projection_service import LearnerProjectionService
from app.services.catalog_mapping_service import CatalogMappingError, resolve_catalog_mapping


SHADOW_QUIZ_NAMESPACE = UUID("283932b6-0867-5b81-9118-1cc3f1354795")
logger = logging.getLogger(__name__)


class ShadowQuizFailure(RuntimeError):
    pass


def _stable_id(attempt_id: int, entity: str) -> str:
    return str(uuid5(SHADOW_QUIZ_NAMESPACE, f"quiz-attempt:{attempt_id}:{entity}"))


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class ShadowQuizService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = PracticeRepository(session)
        self._answer_activity: ActivityInstance | None = None
        self._enrolled = False

    @property
    def enrolled(self) -> bool:
        return self._enrolled

    def start(self, attempt, questions: list[dict[str, object]]) -> PracticeRun:
        run = PracticeRun(
            id=_stable_id(attempt.id, "run"),
            learner_id=attempt.user_id,
            curriculum_version_id=None,
            legacy_quiz_attempt_id=attempt.id,
            status=PracticeRunStatus.ACTIVE,
            selection_policy_version=ShadowPolicyVersion.LEGACY_QUIZ_V1.value,
            started_at=_utc(attempt.started_at),
            ended_at=None,
        )
        self._repository.add_run(run)
        for index, question in enumerate(questions):
            activity = self._activity_for_question(run, question, index)
            run.validate_new_activity(activity)
            self._repository.add_activity(run, activity)
        return run

    def _activity_for_question(
        self,
        run: PracticeRun,
        question: dict[str, object],
        index: int,
    ) -> ActivityInstance:
        question_type = str(question["question_type"])
        scorer_kind = (
            ScorerKind.SELF_REPORT
            if question_type == "remembered_forgot_self_check"
            else ScorerKind.DETERMINISTIC
        )
        operation = (
            ExerciseOperation.RETRIEVE
            if question_type == "ru_to_sr_typing"
            else ExerciseOperation.RECOGNIZE
        )
        target_spec = TargetSpec(
            target_kind=TargetKind.SENSE,
            target_id=resolve_catalog_mapping(
                self._session,
                int(question["word_id"]),
                capability=(
                    Capability.RETRIEVE_FORM
                    if question_type == "ru_to_sr_typing"
                    else Capability.RECOGNIZE_MEANING
                ),
            ).target.target_id,
            capability=(
                Capability.RETRIEVE_FORM
                if question_type == "ru_to_sr_typing"
                else Capability.RECOGNIZE_MEANING
            ),
            modality=Modality.WRITTEN,
            condition={},
        )
        spec = ActivitySpec(
            target_spec=target_spec,
            activity_kind=ActivityKind.EXERCISE,
            operation=operation,
            output_modality=Modality.WRITTEN,
            cue_level=CueLevel.FULL,
            scorer_kind=scorer_kind,
            snapshot={
                "answer_version": 1,
                "choices": question.get("choices", []),
                "legacy_question_type": question_type,
                "legacy_word_id": int(question["word_id"]),
                "plan_index": index,
                "prompt": str(question["prompt"]),
            },
        )
        return ActivityInstance(
            id=_stable_id(run.legacy_quiz_attempt_id, f"activity:{index}"),
            practice_run_id=run.id,
            spec=spec,
            learning_intent=LearningIntent.ASSESS,
            sequence_number=index + 1,
            retry_of_activity_instance_id=None,
            attempt_number=1,
            selection=SelectionMetadata(
                policy_version=ShadowPolicyVersion.LEGACY_QUIZ_V1.value,
                reasons=(SelectionReason.LEGACY_QUIZ,),
            ),
            generator_kind=GeneratorKind.CURATED,
            generator_version="legacy-quiz-v1",
            scorer_version=(
                MEMORY_POLICY_VERSION
                if scorer_kind is ScorerKind.SELF_REPORT
                else "legacy-quiz-v1"
            ),
            feedback_policy_version="legacy-quiz-v1",
            status=ActivityStatus.PENDING,
            selected_at=run.started_at,
            terminal_at=None,
        )

    def lock_for_answer(
        self,
        *,
        learner_id: str,
        attempt_id: int,
        word_id: int,
        question_type: str,
    ) -> QuizAttempt:
        attempt = self._session.scalar(
            select(QuizAttempt)
            .where(
                QuizAttempt.id == attempt_id,
                QuizAttempt.user_id == learner_id,
            )
            .with_for_update()
        )
        if attempt is None:
            raise ValueError("Quiz attempt not found")
        if not self._enroll(attempt):
            self._answer_activity = None
            return attempt
        self._enrolled = True
        run_row = self._session.scalar(
            select(PracticeRunModel).where(
                PracticeRunModel.legacy_quiz_attempt_id == attempt_id
            )
        )
        assert run_row is not None
        run = self._repository.get_run(run_row.id)
        if run is None:
            raise RuntimeError("Linked shadow quiz run not found")
        if run.status is not PracticeRunStatus.ACTIVE:
            self._answer_activity = None
            return attempt
        matches = tuple(
            activity
            for activity in self._repository.lock_activities(run.id)
            if activity.status is ActivityStatus.PENDING
            and activity.spec.snapshot.get("legacy_word_id") == word_id
            and activity.spec.snapshot.get("legacy_question_type") == question_type
        )
        if len(matches) > 1:
            raise RuntimeError("Quiz question has multiple pending shadow activities")
        self._answer_activity = matches[0] if matches else None
        return attempt

    def _enroll(self, attempt: QuizAttempt) -> bool:
        run_row = self._session.scalar(
            select(PracticeRunModel)
            .where(PracticeRunModel.legacy_quiz_attempt_id == attempt.id)
            .with_for_update()
        )
        if run_row is None or run_row.learner_id != attempt.user_id:
            return False
        run = self._repository.get_run(run_row.id)
        if run is None or run.status is not PracticeRunStatus.ACTIVE:
            return False
        expected_answer_ids = set(
            self._session.scalars(
                select(QuizAnswer.id).where(QuizAnswer.quiz_attempt_id == attempt.id)
            )
        )
        event_rows = tuple(
            self._session.scalars(
                select(LearningEventModel).where(
                    LearningEventModel.practice_run_id == run.id
                )
            )
        )
        actual_answer_ids: set[int] = set()
        valid = True
        for event in event_rows:
            legacy_source = event.observation_payload.get("legacy_source")
            if not isinstance(legacy_source, dict):
                valid = False
                break
            reference = legacy_source.get("reference")
            try:
                answer_id = int(reference)
            except (TypeError, ValueError):
                valid = False
                break
            if (
                legacy_source.get("kind") != ShadowLegacySourceKind.QUIZ_ANSWER.value
                or event.idempotency_key != f"legacy:quiz-answer:{answer_id}"
            ):
                valid = False
                break
            actual_answer_ids.add(answer_id)
        if valid and actual_answer_ids == expected_answer_ids:
            return True
        at = self._repository.database_now()
        activities = self._repository.lock_activities(run.id)
        abandoned, cancelled = run.abandon(activities, at)
        for activity in cancelled:
            self._repository.update_activity(activity)
        self._repository.update_run(abandoned)
        logger.warning("quiz_shadow_enrollment_gap")
        return False

    def record_answer(
        self,
        answer: QuizAnswer,
        *,
        create_retry: bool,
    ) -> LearningEvent:
        if answer.id is None or answer.answered_at is None:
            raise RuntimeError("Quiz answer must be flushed before shadow mapping")
        idempotency_key = QuizAnswerIdempotencyInput(answer_id=answer.id).key
        learner_id = self._session.scalar(
            select(QuizAttempt.user_id).where(
                QuizAttempt.id == answer.quiz_attempt_id
            )
        )
        if learner_id is None:
            raise RuntimeError("Quiz answer has no owning attempt")
        duplicate = self._repository.get_learning_event(
            learner_id,
            idempotency_key,
        )
        if duplicate is not None:
            legacy_source = duplicate.legacy_source
            if (
                legacy_source is None
                or legacy_source.kind != ShadowLegacySourceKind.QUIZ_ANSWER.value
                or legacy_source.reference != str(answer.id)
            ):
                raise RuntimeError("Quiz answer idempotency key has conflicting evidence")
            return duplicate
        activity = self._answer_activity
        if activity is None:
            raise RuntimeError("Quiz answer has no pending shadow activity")
        current_mapping = resolve_catalog_mapping(
            self._session,
            answer.word_id,
            capability=activity.target_spec.capability,
        )
        if current_mapping.target.target_key != activity.target_key:
            raise CatalogMappingError("stale")
        occurred_at = self._chronological_occurred_at(
            activity,
            _utc(answer.answered_at),
        )
        response, evaluation = _response_and_evaluation(answer)
        request = LearningEventRequest(
            event_id=_stable_id(answer.quiz_attempt_id, f"event:{answer.id}"),
            learner_id=learner_id,
            activity_instance_id=activity.id,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
            first_response=response,
            evaluation=evaluation,
            legacy_source=ShadowLegacySourceRef(
                kind=ShadowLegacySourceKind.QUIZ_ANSWER,
                reference=str(answer.id),
            ).to_domain(),
        )
        received_at = self._repository.database_now()
        event = build_learning_event(
            activity,
            request,
            created_at=received_at,
            received_at=received_at,
        )
        self._repository.add_learning_event(event)
        completed = activity.complete(occurred_at)
        self._repository.update_activity(completed)
        LearnerProjectionService(
            ProgressRepository(self._session),
            _StoredQuizEventSource(self._session, self._repository),
        ).apply_event(event)
        if create_retry:
            run = self._repository.get_run(activity.practice_run_id)
            if run is None:
                raise RuntimeError("Linked shadow quiz run not found")
            retry = completed.retry(
                retry_id=_stable_id(
                    answer.quiz_attempt_id,
                    f"retry:{activity.id}",
                ),
                sequence_number=self._repository.next_sequence_number(run.id),
                selected_at=occurred_at,
            )
            self._repository.add_activity(run, retry)
        return event

    def _chronological_occurred_at(
        self,
        activity: ActivityInstance,
        proposed: datetime,
    ) -> datetime:
        latest = self._session.scalar(
            select(func.max(LearningEventModel.occurred_at)).where(
                LearningEventModel.practice_run_id == activity.practice_run_id
            )
        )
        if latest is None:
            return proposed
        latest_utc = _utc(latest)
        if proposed > latest_utc:
            return proposed
        return latest_utc + timedelta(microseconds=1)

    def complete(self, attempt: QuizAttempt) -> PracticeRun | None:
        locked_attempt = self._session.scalar(
            select(QuizAttempt)
            .where(
                QuizAttempt.id == attempt.id,
                QuizAttempt.user_id == attempt.user_id,
            )
            .with_for_update()
        )
        if locked_attempt is None:
            raise ValueError("Quiz attempt not found")
        if not self._enroll(locked_attempt):
            return None
        run_row = self._session.scalar(
            select(PracticeRunModel)
            .where(PracticeRunModel.legacy_quiz_attempt_id == attempt.id)
            .with_for_update()
        )
        if run_row is None or run_row.learner_id != attempt.user_id:
            raise RuntimeError("Linked shadow quiz run not found")
        run = self._repository.lock_run(run_row.id)
        if run is None:
            raise RuntimeError("Linked shadow quiz run not found")
        activities = self._repository.lock_activities(run.id)
        if attempt.completed_at is None:
            raise RuntimeError("Legacy quiz must be complete before its shadow run")
        completed = run.complete(activities, _utc(attempt.completed_at))
        self._repository.update_run(completed)
        return completed


class _StoredQuizEventSource:
    def __init__(self, session: Session, repository: PracticeRepository) -> None:
        self._session = session
        self._repository = repository

    def events_for_target(
        self,
        learner_id: str,
        target_key: str,
    ) -> tuple[LearningEvent, ...]:
        keys = tuple(
            self._session.scalars(
                select(LearningEventModel.idempotency_key)
                .where(
                    LearningEventModel.learner_id == learner_id,
                    LearningEventModel.target_key == target_key,
                )
                .order_by(LearningEventModel.occurred_at, LearningEventModel.id)
            )
        )
        events = tuple(
            self._repository.get_learning_event(learner_id, key) for key in keys
        )
        if any(event is None for event in events):
            raise RuntimeError("Stored shadow quiz event disappeared")
        return tuple(event for event in events if event is not None)


def _response_and_evaluation(
    answer: QuizAnswer,
) -> tuple[ResponseSnapshot, Evaluation]:
    if answer.question_type == "remembered_forgot_self_check":
        rating = (
            SelfReportRating.GOOD if answer.is_correct else SelfReportRating.AGAIN
        )
        return (
            ResponseSnapshot(kind=ResponseKind.RATING, value=rating.value),
            Evaluation(
                source=EvaluationSource.SELF_REPORT,
                outcome=EvaluationOutcome.UNKNOWN,
            ),
        )
    response_kind = (
        ResponseKind.CHOICE
        if answer.question_type == "sr_to_ru_choice"
        else ResponseKind.TEXT
    )
    response = (
        _bounded_choice_response(answer.answer)
        if response_kind is ResponseKind.CHOICE
        else ResponseSnapshot.from_input(kind=response_kind, value=answer.answer)
    )
    return (
        response,
        Evaluation(
            source=EvaluationSource.DETERMINISTIC,
            outcome=(
                EvaluationOutcome.CORRECT
                if answer.is_correct
                else EvaluationOutcome.INCORRECT
            ),
        ),
    )


def _bounded_choice_response(value: str) -> ResponseSnapshot:
    normalized = unicodedata.normalize("NFC", value)
    if normalized and len(normalized) <= 120:
        return ResponseSnapshot(kind=ResponseKind.CHOICE, value=normalized)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return ResponseSnapshot(
        kind=ResponseKind.CHOICE,
        value=f"legacy-choice-sha256:{digest}",
    )
