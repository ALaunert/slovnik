from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LearnerTargetStateModel(Base):
    __tablename__ = "learner_target_states"
    __table_args__ = (
        CheckConstraint(
            "competence_success_weight >= 0",
            name="ck_learner_target_states_success_weight",
        ),
        CheckConstraint(
            "competence_failure_weight >= 0",
            name="ck_learner_target_states_failure_weight",
        ),
        CheckConstraint(
            "competence_peak >= 0 AND competence_peak <= 1",
            name="ck_learner_target_states_competence_peak",
        ),
        CheckConstraint(
            "uncertainty >= 0 AND uncertainty <= 1",
            name="ck_learner_target_states_uncertainty",
        ),
        CheckConstraint(
            "evidence_count >= 0",
            name="ck_learner_target_states_evidence_count",
        ),
        CheckConstraint(
            "baseline_kind IN ('neutral', 'legacy_bootstrap')",
            name="ck_learner_target_states_baseline_kind",
        ),
        CheckConstraint(
            "baseline_memory_interval_days >= 0",
            name="ck_learner_target_states_baseline_interval",
        ),
        CheckConstraint(
            "(evidence_count = 0 AND last_evidence_at IS NULL "
            "AND last_event_id IS NULL) OR "
            "(evidence_count > 0 AND last_evidence_at IS NOT NULL "
            "AND last_event_id IS NOT NULL)",
            name="ck_learner_target_states_evidence_cursor",
        ),
        CheckConstraint(
            "competence_success_weight + competence_failure_weight <= evidence_count",
            name="ck_learner_target_states_weight_count",
        ),
        CheckConstraint(
            "memory_interval_days >= 0",
            name="ck_learner_target_states_memory_interval",
        ),
        CheckConstraint(
            "memory_lapses >= 0",
            name="ck_learner_target_states_memory_lapses",
        ),
        UniqueConstraint(
            "learner_id",
            "target_key",
            name="uq_learner_target_states_learner_target",
        ),
        Index(
            "ix_learner_target_states_due",
            "learner_id",
            "memory_due_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    learner_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("user_profiles.user_id"), nullable=False
    )
    target_key: Mapped[str] = mapped_column(String(255), nullable=False)
    competence_success_weight: Mapped[float] = mapped_column(Float, nullable=False)
    competence_failure_weight: Mapped[float] = mapped_column(Float, nullable=False)
    competence_peak: Mapped[float] = mapped_column(Float, nullable=False)
    uncertainty: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    baseline_memory_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    baseline_memory_interval_days: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    baseline_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON(none_as_null=True), nullable=False
    )
    last_evidence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_event_id: Mapped[str | None] = mapped_column(String(36))
    memory_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    memory_interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_lapses: Mapped[int] = mapped_column(Integer, nullable=False)
    memory_policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    projection_policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
