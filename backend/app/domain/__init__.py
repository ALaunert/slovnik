from importlib import import_module
from types import ModuleType

from .shared import Capability, Modality, TargetKind
from .target import TargetSpec

_CONTEXT_MODULES = {"catalog", "curriculum", "practice", "progress"}


def __getattr__(name: str) -> ModuleType:
    if name not in _CONTEXT_MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module


__all__ = [
    "Capability",
    "Modality",
    "TargetKind",
    "TargetSpec",
    "catalog",
    "curriculum",
    "practice",
    "progress",
]
