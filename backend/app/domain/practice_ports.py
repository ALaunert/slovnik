from typing import Protocol, runtime_checkable

from .practice import (
    ActivityInstance,
    Evaluation,
    EvaluationSource,
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
