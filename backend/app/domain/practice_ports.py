from typing import Protocol, runtime_checkable

from .practice import (
    ActivityInstance,
    Evaluation,
    EvaluationSource,
    PracticeRun,
    ResponseSubmission,
)


@runtime_checkable
class ResponseEvaluator(Protocol):
    version: str
    source: EvaluationSource

    def evaluate(
        self,
        activity: ActivityInstance,
        submission: ResponseSubmission,
    ) -> Evaluation: ...


class PracticeLifecycleRepository(Protocol):
    def add_run(self, run: PracticeRun) -> None: ...

    def get_run(self, run_id: str) -> PracticeRun | None: ...

    def get_activity(self, activity_id: str) -> ActivityInstance | None: ...

    def lock_run(self, run_id: str) -> PracticeRun | None: ...

    def lock_activity(self, activity_id: str) -> ActivityInstance | None: ...

    def list_activities(self, run_id: str) -> tuple[ActivityInstance, ...]: ...

    def lock_activities(self, run_id: str) -> tuple[ActivityInstance, ...]: ...

    def next_sequence_number(self, run_id: str) -> int: ...

    def add_activity(self, run: PracticeRun, activity: ActivityInstance) -> None: ...

    def update_run(self, run: PracticeRun) -> None: ...

    def update_activity(self, activity: ActivityInstance) -> None: ...
