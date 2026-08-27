from dataclasses import replace
from datetime import datetime

from app.domain.practice import ActivityInstance, PracticeRun
from app.domain.practice_ports import PracticeLifecycleRepository


class PracticeRunNotFound(ValueError):
    pass


class PracticeLifecycleConflict(ValueError):
    pass


class PracticeService:
    def __init__(self, repository: PracticeLifecycleRepository) -> None:
        self._repository = repository

    def get_run(self, learner_id: str, run_id: str) -> PracticeRun:
        return self._owned_run(learner_id, run_id)

    def start_run(self, learner_id: str, run: PracticeRun) -> PracticeRun:
        self._require_run_owner(run, learner_id)
        if run.status.is_terminal:
            raise PracticeLifecycleConflict("Practice run must start active")
        self._repository.add_run(run)
        return run

    def _owned_run(self, learner_id: str, run_id: str) -> PracticeRun:
        run = self._repository.get_run(run_id)
        if run is None:
            raise PracticeRunNotFound("Practice run not found")
        self._require_run_owner(run, learner_id)
        return run

    def lock_activity_for_submission(
        self, learner_id: str, activity_id: str
    ) -> ActivityInstance:
        _, activity = self._lock_activity_in_active_run(
            learner_id,
            activity_id,
        )
        if activity.status.is_terminal:
            raise PracticeLifecycleConflict("Practice activity is terminal")
        return activity

    def complete_run(
        self, learner_id: str, run_id: str, ended_at: datetime
    ) -> PracticeRun:
        run = self._locked_owned_run(learner_id, run_id)
        try:
            completed = run.complete(
                self._repository.list_activities(run.id),
                ended_at,
            )
        except ValueError as exc:
            raise PracticeLifecycleConflict(str(exc)) from exc
        self._repository.update_run(completed)
        return completed

    def complete_activity(
        self,
        learner_id: str,
        activity_id: str,
        terminal_at: datetime,
    ) -> ActivityInstance:
        activity = self.lock_activity_for_submission(learner_id, activity_id)
        try:
            completed = activity.complete(terminal_at)
        except ValueError as exc:
            raise PracticeLifecycleConflict(str(exc)) from exc
        self._repository.update_activity(completed)
        return completed

    def abandon_run(
        self, learner_id: str, run_id: str, ended_at: datetime
    ) -> PracticeRun:
        run = self._locked_owned_run(learner_id, run_id)
        try:
            abandoned, cancelled = run.abandon(
                self._repository.lock_activities(run.id),
                ended_at,
            )
        except ValueError as exc:
            raise PracticeLifecycleConflict(str(exc)) from exc
        for activity in cancelled:
            self._repository.update_activity(activity)
        self._repository.update_run(abandoned)
        return abandoned

    def add_activity(
        self,
        learner_id: str,
        run_id: str,
        activity: ActivityInstance,
    ) -> ActivityInstance:
        run = self._locked_owned_run(learner_id, run_id)
        self._require_active_run(run)
        self._validate_activity(run, activity)
        allocated = replace(
            activity,
            sequence_number=self._repository.next_sequence_number(run.id),
        )
        self._repository.add_activity(run, allocated)
        return allocated

    def create_retry(
        self,
        learner_id: str,
        parent_activity_id: str,
        *,
        retry_id: str,
        selected_at: datetime,
    ) -> ActivityInstance:
        run, parent = self._lock_activity_in_active_run(
            learner_id,
            parent_activity_id,
        )
        self._require_no_retry(run, parent)
        try:
            retry = parent.retry(
                retry_id=retry_id,
                sequence_number=self._repository.next_sequence_number(run.id),
                selected_at=selected_at,
            )
        except ValueError as exc:
            raise PracticeLifecycleConflict(str(exc)) from exc
        self._repository.add_activity(run, retry)
        return retry

    @staticmethod
    def _require_active_run(run: PracticeRun) -> None:
        if run.status.is_terminal:
            raise PracticeLifecycleConflict("Practice run is terminal")

    @staticmethod
    def _validate_activity(run: PracticeRun, activity: ActivityInstance) -> None:
        try:
            run.validate_new_activity(activity)
        except ValueError as exc:
            raise PracticeLifecycleConflict(str(exc)) from exc

    @staticmethod
    def _validate_existing_activity(
        run: PracticeRun,
        activity: ActivityInstance,
    ) -> None:
        try:
            run.validate_activity(activity)
        except ValueError as exc:
            raise PracticeLifecycleConflict(str(exc)) from exc

    def _locked_owned_run(self, learner_id: str, run_id: str) -> PracticeRun:
        run = self._repository.lock_run(run_id)
        if run is None:
            raise PracticeRunNotFound("Practice run not found")
        self._require_run_owner(run, learner_id)
        return run

    @staticmethod
    def _require_run_owner(run: PracticeRun, learner_id: str) -> None:
        if run.learner_id != learner_id:
            raise PracticeRunNotFound("Practice run not found")

    def _locked_activity(self, activity_id: str) -> ActivityInstance:
        activity = self._repository.lock_activity(activity_id)
        if activity is None:
            raise PracticeRunNotFound("Practice activity not found")
        return activity

    def _activity(self, activity_id: str) -> ActivityInstance:
        activity = self._repository.get_activity(activity_id)
        if activity is None:
            raise PracticeRunNotFound("Practice activity not found")
        return activity

    def _lock_activity_in_active_run(
        self,
        learner_id: str,
        activity_id: str,
    ) -> tuple[PracticeRun, ActivityInstance]:
        located = self._owned_activity_reference(learner_id, activity_id)
        run = self._locked_owned_run(learner_id, located.practice_run_id)
        self._require_active_run(run)
        activity = self._locked_activity(activity_id)
        self._validate_existing_activity(run, activity)
        return run, activity

    def _owned_activity_reference(
        self,
        learner_id: str,
        activity_id: str,
    ) -> ActivityInstance:
        activity = self._activity(activity_id)
        self._owned_run(learner_id, activity.practice_run_id)
        return activity

    def _require_no_retry(
        self,
        run: PracticeRun,
        parent: ActivityInstance,
    ) -> None:
        if any(
            activity.retry_of_activity_instance_id == parent.id
            for activity in self._repository.list_activities(run.id)
        ):
            raise PracticeLifecycleConflict(
                "Practice activity already has a retry"
            )
