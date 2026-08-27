from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


_STATUS_CHECK = "status IN ('draft', 'published', 'retired')"


class LanguageLexicalUnit(Base):
    __tablename__ = "language_lexical_units"
    __table_args__ = (
        CheckConstraint("kind IN ('word', 'mwe')", name="ck_language_lexical_units_kind"),
        CheckConstraint(_STATUS_CHECK, name="ck_language_lexical_units_status"),
        CheckConstraint("revision >= 1", name="ck_language_lexical_units_revision"),
        UniqueConstraint(
            "legacy_vocabulary_item_id",
            name="uq_lexical_unit_legacy_vocabulary_item",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    legacy_vocabulary_item_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "vocabulary_items.id",
            name="fk_lexical_unit_legacy_vocabulary_item",
        )
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    senses: Mapped[list[LanguageSense]] = relationship(
        back_populates="lexical_unit", cascade="all, delete-orphan", lazy="selectin"
    )
    forms: Mapped[list[LanguageForm]] = relationship(
        back_populates="lexical_unit", cascade="all, delete-orphan", lazy="selectin"
    )


class LanguageSense(Base):
    __tablename__ = "language_senses"
    __table_args__ = (
        CheckConstraint(_STATUS_CHECK, name="ck_language_senses_status"),
        CheckConstraint("revision >= 1", name="ck_language_senses_revision"),
        Index("ix_language_senses_lexical_unit", "lexical_unit_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    lexical_unit_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey(
            "language_lexical_units.id",
            name="fk_language_sense_lexical_unit",
        ),
        nullable=False,
    )
    glosses: Mapped[list[dict[str, Any]]] = mapped_column(JSON(none_as_null=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    examples: Mapped[list[dict[str, Any]]] = mapped_column(JSON(none_as_null=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)

    lexical_unit: Mapped[LanguageLexicalUnit] = relationship(back_populates="senses")


class LanguageForm(Base):
    __tablename__ = "language_forms"
    __table_args__ = (
        CheckConstraint(
            "form_kind IN ('citation', 'inflected', 'fixed')",
            name="ck_language_forms_form_kind",
        ),
        CheckConstraint(_STATUS_CHECK, name="ck_language_forms_status"),
        CheckConstraint("revision >= 1", name="ck_language_forms_revision"),
        Index("ix_language_forms_lexical_unit", "lexical_unit_id"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    lexical_unit_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey(
            "language_lexical_units.id",
            name="fk_language_form_lexical_unit",
        ),
        nullable=False,
    )
    form_kind: Mapped[str] = mapped_column(Text, nullable=False)
    orthographies: Mapped[list[dict[str, str]]] = mapped_column(
        JSON(none_as_null=True), nullable=False
    )
    morph_features: Mapped[dict[str, Any]] = mapped_column(
        JSON(none_as_null=True), nullable=False
    )
    stress_pattern: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)

    lexical_unit: Mapped[LanguageLexicalUnit] = relationship(back_populates="forms")


class LanguageConstruction(Base):
    __tablename__ = "language_constructions"
    __table_args__ = (
        CheckConstraint(_STATUS_CHECK, name="ck_language_constructions_status"),
        CheckConstraint("revision >= 1", name="ck_language_constructions_revision"),
        UniqueConstraint("code", name="uq_language_construction_code"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    morph_features: Mapped[dict[str, Any]] = mapped_column(
        JSON(none_as_null=True), nullable=False
    )
    examples: Mapped[list[dict[str, Any]]] = mapped_column(JSON(none_as_null=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
