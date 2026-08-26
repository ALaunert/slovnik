from typing import Protocol, runtime_checkable

from .progress import LearningEventView, MemoryState


@runtime_checkable
class MemoryPolicy(Protocol):
    version: str

    def apply(self, state: MemoryState, event: LearningEventView) -> MemoryState: ...
