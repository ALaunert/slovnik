from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class CurriculumVersionRecord(Base):
    __tablename__ = "curriculum_versions"
    __table_args__ = (
        CheckConstraint("version_number >= 1", name="ck_curriculum_versions_number"),
        CheckConstraint(
            "status IN ('draft', 'active', 'retired')",
            name="ck_curriculum_versions_status",
        ),
        CheckConstraint(
            "(status = 'draft' AND published_at IS NULL AND retired_at IS NULL) OR "
            "(status = 'active' AND published_at IS NOT NULL AND retired_at IS NULL) OR "
            "(status = 'retired' AND published_at IS NOT NULL AND retired_at IS NOT NULL)",
            name="ck_curriculum_versions_lifecycle",
        ),
        UniqueConstraint(
            "curriculum_code",
            "version_number",
            name="uq_curriculum_versions_code_number",
        ),
        Index(
            "uq_curriculum_versions_one_active",
            "curriculum_code",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    curriculum_code: Mapped[str] = mapped_column(Text, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    nodes: Mapped[list[CurriculumNodeRecord]] = relationship(
        back_populates="curriculum_version",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CurriculumNodeRecord.id",
    )
    prerequisites: Mapped[list[CurriculumPrerequisiteRecord]] = relationship(
        back_populates="curriculum_version",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CurriculumPrerequisiteRecord.id",
    )


class CurriculumNodeRecord(Base):
    __tablename__ = "curriculum_nodes"
    __table_args__ = (
        CheckConstraint(
            "target_kind IN ('sense', 'form', 'construction')",
            name="ck_curriculum_nodes_target_kind",
        ),
        CheckConstraint(
            "capability IN ('recognize_meaning', 'retrieve_form', 'apply_construction')",
            name="ck_curriculum_nodes_capability",
        ),
        CheckConstraint("modality IN ('written')", name="ck_curriculum_nodes_modality"),
        CheckConstraint(
            "priority >= 0 AND priority <= 100",
            name="ck_curriculum_nodes_priority",
        ),
        CheckConstraint(
            "substr(outcome_code, 1, 2) IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2') "
            "AND substr(outcome_code, 3, 1) = '.' AND length(outcome_code) > 3",
            name="ck_curriculum_nodes_outcome",
        ),
        UniqueConstraint(
            "curriculum_version_id",
            "target_key",
            name="uq_curriculum_nodes_version_target",
        ),
        UniqueConstraint(
            "curriculum_version_id",
            "id",
            name="uq_curriculum_nodes_version_id",
        ),
        Index("ix_curriculum_nodes_target", "target_key"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    curriculum_version_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("curriculum_versions.id"),
        nullable=False,
    )
    target_key: Mapped[str] = mapped_column(Text, nullable=False)
    target_kind: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    capability: Mapped[str] = mapped_column(Text, nullable=False)
    modality: Mapped[str] = mapped_column(Text, nullable=False)
    condition_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON(none_as_null=True), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome_code: Mapped[str] = mapped_column(Text, nullable=False)

    curriculum_version: Mapped[CurriculumVersionRecord] = relationship(
        back_populates="nodes"
    )


class CurriculumPrerequisiteRecord(Base):
    __tablename__ = "curriculum_prerequisites"
    __table_args__ = (
        ForeignKeyConstraint(
            ("curriculum_version_id", "prerequisite_node_id"),
            ("curriculum_nodes.curriculum_version_id", "curriculum_nodes.id"),
            name="fk_curriculum_prerequisites_prerequisite",
        ),
        ForeignKeyConstraint(
            ("curriculum_version_id", "dependent_node_id"),
            ("curriculum_nodes.curriculum_version_id", "curriculum_nodes.id"),
            name="fk_curriculum_prerequisites_dependent",
        ),
        CheckConstraint(
            "prerequisite_node_id <> dependent_node_id",
            name="ck_curriculum_prerequisites_distinct_nodes",
        ),
        CheckConstraint(
            "kind IN ('hard', 'soft')",
            name="ck_curriculum_prerequisites_kind",
        ),
        UniqueConstraint(
            "curriculum_version_id",
            "prerequisite_node_id",
            "dependent_node_id",
            name="uq_curriculum_prerequisites_version_pair",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    curriculum_version_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("curriculum_versions.id"),
        nullable=False,
    )
    prerequisite_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    dependent_node_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)

    curriculum_version: Mapped[CurriculumVersionRecord] = relationship(
        back_populates="prerequisites",
        foreign_keys=[curriculum_version_id],
    )
