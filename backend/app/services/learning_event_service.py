from typing import Protocol

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.practice import (
    ActivityInstance,
    LearningEvent,
    LearningEventRequest,
    PracticeRun,
    build_learning_event,
)
from app.repositories.practice import PracticeRepository


class LearningEventProjector(Protocol):
    def project(self, event: LearningEvent) -> None: ...


class LearningEventNotFound(ValueError):
    pass


class LearningEventConflict(ValueError):
    pass


class LearningEventIdempotencyConflict(LearningEventConflict):
    pass


class LearningEventService:
    def __init__(
        self,
        session: Session,
        *,
        projector: LearningEventProjector,
        repository: PracticeRepository | None = None,
    ) -> None:
        self._session = session
        self._repository = repository or PracticeRepository(session)
        self._projector = projector

    def record(self, request: LearningEventRequest) -> LearningEvent:
        received_at = self._repository.database_now()
        try:
            duplicate = self._repository.get_learning_event(
                request.learner_id,
                request.idempotency_key,
            )
            if duplicate is not None:
                return self._return_duplicate(duplicate, request)

            run, activity = self._lock_owned_activity(request)
            duplicate = self._repository.get_learning_event(
                request.learner_id,
                request.idempotency_key,
            )
            if duplicate is not None:
                return self._return_duplicate(duplicate, request)
            if activity.status.is_terminal:
                raise LearningEventConflict("Practice activity is terminal")

            event = build_learning_event(
                activity,
                request,
                created_at=received_at,
                received_at=received_at,
            )
            try:
                completed = activity.complete(event.occurred_at)
            except ValueError as exc:
                raise LearningEventConflict(str(exc)) from exc
            self._repository.add_learning_event(event)
            self._repository.update_activity(completed)
            self._projector.project(event)
            self._session.commit()
            return event
        except IntegrityError as exc:
            self._session.rollback()
            return self._recover_idempotency_conflict(exc, request)
        except Exception:
            self._session.rollback()
            raise

    def _lock_owned_activity(
        self,
        request: LearningEventRequest,
    ) -> tuple[PracticeRun, ActivityInstance]:
        reference = self._repository.get_activity(request.activity_instance_id)
        if reference is None:
            raise LearningEventNotFound("Practice activity not found")
        run_reference = self._repository.get_run(reference.practice_run_id)
        self._require_owned_run(run_reference, request.learner_id)

        run = self._repository.lock_run(reference.practice_run_id)
        self._require_owned_run(run, request.learner_id)
        assert run is not None
        if run.status.is_terminal:
            raise LearningEventConflict("Practice run is terminal")
        activity = self._repository.lock_activity(request.activity_instance_id)
        if activity is None:
            raise LearningEventNotFound("Practice activity not found")
        try:
            run.validate_activity(activity)
        except ValueError as exc:
            raise LearningEventConflict(str(exc)) from exc
        return run, activity

    @staticmethod
    def _require_owned_run(run: PracticeRun | None, learner_id: str) -> None:
        if run is None or run.learner_id != learner_id:
            raise LearningEventNotFound("Practice activity not found")

    def _return_duplicate(
        self,
        event: LearningEvent,
        request: LearningEventRequest,
    ) -> LearningEvent:
        if event.semantic_fingerprint != request.semantic_fingerprint:
            self._session.rollback()
            raise LearningEventIdempotencyConflict(
                "Idempotency key was already used for another semantic request"
            )
        self._session.commit()
        return event

    def _recover_idempotency_conflict(
        self,
        error: IntegrityError,
        request: LearningEventRequest,
    ) -> LearningEvent:
        if not _is_idempotency_violation(error):
            raise error
        duplicate = self._repository.get_learning_event(
            request.learner_id,
            request.idempotency_key,
        )
        if duplicate is None:
            raise error
        return self._return_duplicate(duplicate, request)


def _is_idempotency_violation(error: IntegrityError) -> bool:
    diagnostic = getattr(error.orig, "diag", None)
    if getattr(diagnostic, "constraint_name", None) == "uq_learning_events_idempotency":
        return True
    message = str(error.orig).lower()
    return (
        "learning_events.learner_id, learning_events.idempotency_key" in message
        or "uq_learning_events_idempotency" in message
    )
