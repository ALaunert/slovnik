from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PracticeRunModel(Base):
    __tablename__ = "practice_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'completed', 'abandoned')",
            name="ck_practice_runs_status",
        ),
        CheckConstraint(
            "(status = 'active' AND ended_at IS NULL) OR "
            "(status IN ('completed', 'abandoned') AND ended_at IS NOT NULL)",
            name="ck_practice_runs_terminal",
        ),
        UniqueConstraint("id", "learner_id", name="uq_practice_runs_owner"),
        UniqueConstraint(
            "id",
            "selection_policy_version",
            name="uq_practice_runs_selection_policy",
        ),
        UniqueConstraint(
            "legacy_quiz_attempt_id",
            name="uq_practice_run_legacy_quiz_attempt",
        ),
        Index("ix_practice_runs_learner_status", "learner_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    learner_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.user_id", name="fk_practice_run_learner"),
        nullable=False,
    )
    curriculum_version_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "curriculum_versions.id",
            name="fk_practice_run_curriculum_version",
        )
    )
    legacy_quiz_attempt_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "quiz_attempts.id",
            name="fk_practice_run_legacy_quiz_attempt",
        )
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    selection_policy_version: Mapped[str] = mapped_column(String(120), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActivityInstanceModel(Base):
    __tablename__ = "activity_instances"
    __table_args__ = (
        ForeignKeyConstraint(
            ["practice_run_id", "selection_policy_version"],
            ["practice_runs.id", "practice_runs.selection_policy_version"],
            name="fk_activity_instances_run_policy",
        ),
        ForeignKeyConstraint(
            ["practice_run_id", "retry_of_activity_instance_id", "target_key"],
            [
                "activity_instances.practice_run_id",
                "activity_instances.id",
                "activity_instances.target_key",
            ],
            name="fk_activity_instances_retry_owner",
        ),
        CheckConstraint(
            "learning_intent IN ('acquire', 'review', 'strengthen', 'assess')",
            name="ck_activity_instances_learning_intent",
        ),
        CheckConstraint(
            "activity_kind IN ('exposure', 'exercise')",
            name="ck_activity_instances_kind",
        ),
        CheckConstraint(
            "operation IS NULL OR operation IN ('recognize', 'retrieve', 'complete', 'transform')",
            name="ck_activity_instances_operation",
        ),
        CheckConstraint("sequence_number >= 1", name="ck_activity_instances_sequence"),
        CheckConstraint("attempt_number >= 1", name="ck_activity_instances_attempt"),
        CheckConstraint(
            "selection_propensity IS NULL OR "
            "(selection_propensity >= 0 AND selection_propensity <= 1)",
            name="ck_activity_instances_propensity",
        ),
        CheckConstraint(
            "generator_kind IN ('curated', 'model_assisted')",
            name="ck_activity_instances_generator_kind",
        ),
        CheckConstraint(
            "scorer_kind IS NULL OR "
            "scorer_kind IN ('deterministic', 'self_report', 'model_assisted')",
            name="ck_activity_instances_scorer_kind",
        ),
        CheckConstraint(
            "status IN ('pending', 'completed', 'cancelled')",
            name="ck_activity_instances_status",
        ),
        CheckConstraint(
            "(activity_kind = 'exposure' AND operation IS NULL AND "
            "scorer_kind IS NULL AND scorer_version IS NULL) OR "
            "(activity_kind = 'exercise' AND operation IS NOT NULL AND "
            "scorer_kind IS NOT NULL AND scorer_version IS NOT NULL)",
            name="ck_activity_instances_shape",
        ),
        CheckConstraint(
            "(retry_of_activity_instance_id IS NULL AND attempt_number = 1) OR "
            "(retry_of_activity_instance_id IS NOT NULL AND "
            "retry_of_activity_instance_id <> id AND attempt_number >= 2)",
            name="ck_activity_instances_retry",
        ),
        CheckConstraint(
            "(status = 'pending' AND terminal_at IS NULL) OR "
            "(status IN ('completed', 'cancelled') AND terminal_at IS NOT NULL)",
            name="ck_activity_instances_terminal",
        ),
        UniqueConstraint(
            "practice_run_id", "sequence_number", name="uq_activity_instances_run_sequence"
        ),
        UniqueConstraint(
            "practice_run_id",
            "id",
            "target_key",
            name="uq_activity_instances_run_target",
        ),
        UniqueConstraint(
            "practice_run_id",
            "id",
            "target_key",
            "activity_kind",
            name="uq_activity_instances_event_owner",
        ),
        Index("ix_activity_instances_retry", "retry_of_activity_instance_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    practice_run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_key: Mapped[str] = mapped_column(String(255), nullable=False)
    learning_intent: Mapped[str] = mapped_column(String(20), nullable=False)
    activity_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    operation: Mapped[str | None] = mapped_column(String(20))
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    retry_of_activity_instance_id: Mapped[str | None] = mapped_column(String(36))
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    spec_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON(none_as_null=True), nullable=False
    )
    selection_policy_version: Mapped[str] = mapped_column(String(120), nullable=False)
    selection_reason_payload: Mapped[list[str]] = mapped_column(
        JSON(none_as_null=True), nullable=False
    )
    selection_propensity: Mapped[float | None] = mapped_column(Float)
    generator_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    generator_version: Mapped[str] = mapped_column(String(120), nullable=False)
    scorer_kind: Mapped[str | None] = mapped_column(String(20))
    scorer_version: Mapped[str | None] = mapped_column(String(120))
    feedback_policy_version: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LearningEventModel(Base):
    __tablename__ = "learning_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["practice_run_id", "learner_id"],
            ["practice_runs.id", "practice_runs.learner_id"],
            name="fk_learning_events_run_owner",
        ),
        ForeignKeyConstraint(
            ["practice_run_id", "activity_instance_id", "target_key", "activity_kind"],
            [
                "activity_instances.practice_run_id",
                "activity_instances.id",
                "activity_instances.target_key",
                "activity_instances.activity_kind",
            ],
            name="fk_learning_events_activity_owner",
        ),
        CheckConstraint("schema_version >= 1", name="ck_learning_events_schema_version"),
        CheckConstraint(
            "event_type IN ('exposure', 'response_evaluated')",
            name="ck_learning_events_type",
        ),
        CheckConstraint(
            "activity_kind IN ('exposure', 'exercise')",
            name="ck_learning_events_activity_kind",
        ),
        CheckConstraint(
            "(activity_kind = 'exposure' AND event_type = 'exposure') OR "
            "(activity_kind = 'exercise' AND event_type = 'response_evaluated')",
            name="ck_learning_events_shape",
        ),
        UniqueConstraint(
            "learner_id", "idempotency_key", name="uq_learning_events_idempotency"
        ),
        UniqueConstraint("activity_instance_id", name="uq_learning_events_activity"),
        Index("ix_learning_events_learner_time", "learner_id", "occurred_at"),
        Index(
            "ix_learning_events_learner_target_time",
            "learner_id",
            "target_key",
            "occurred_at",
            "id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    learner_id: Mapped[str] = mapped_column(
        ForeignKey("user_profiles.user_id", name="fk_learning_event_learner"),
        nullable=False,
    )
    practice_run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    activity_instance_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_key: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    activity_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    observation_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON(none_as_null=True), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
