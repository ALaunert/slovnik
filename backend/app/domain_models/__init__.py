"""Domain model registry owned by the integration workstream."""

from importlib import import_module


_DOMAIN_MODEL_MODULES = (
    "app.domain_models.catalog",
    "app.domain_models.curriculum",
    "app.domain_models.practice",
    "app.domain_models.progress",
)


def register_domain_models() -> None:
    """Load every context mapping into the shared SQLAlchemy metadata."""
    for module_name in _DOMAIN_MODEL_MODULES:
        import_module(module_name)


__all__ = ["register_domain_models"]
