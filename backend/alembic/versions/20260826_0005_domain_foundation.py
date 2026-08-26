"""Add language-assistant domain foundation.

Revision ID: 20260826_0005
Revises: 20260725_0004
Create Date: 2026-08-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260826_0005"
down_revision: str | None = "20260725_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONTENT_STATUS = "status IN ('draft', 'published', 'retired')"


def upgrade() -> None:
    op.create_table(
        "language_lexical_units",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("legacy_vocabulary_item_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('word', 'mwe')", name="ck_lexical_unit_kind"),
        sa.CheckConstraint(CONTENT_STATUS, name="ck_lexical_unit_status"),
        sa.CheckConstraint("revision >= 1", name="ck_lexical_unit_revision"),
        sa.ForeignKeyConstraint(
            ["legacy_vocabulary_item_id"],
            ["vocabulary_items.id"],
            name="fk_lexical_unit_legacy_vocabulary_item",
        ),
        sa.UniqueConstraint(
            "legacy_vocabulary_item_id",
            name="uq_lexical_unit_legacy_vocabulary_item",
        ),
    )
    op.create_table(
        "language_senses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("lexical_unit_id", sa.String(36), nullable=False),
        sa.Column("glosses", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("examples", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.CheckConstraint(CONTENT_STATUS, name="ck_language_sense_status"),
        sa.CheckConstraint("revision >= 1", name="ck_language_sense_revision"),
        sa.ForeignKeyConstraint(
            ["lexical_unit_id"],
            ["language_lexical_units.id"],
            name="fk_language_sense_lexical_unit",
        ),
    )
    op.create_index(
        "ix_language_senses_lexical_unit",
        "language_senses",
        ["lexical_unit_id"],
    )
    op.create_table(
        "language_forms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("lexical_unit_id", sa.String(36), nullable=False),
        sa.Column("form_kind", sa.String(16), nullable=False),
        sa.Column("orthographies", sa.JSON(), nullable=False),
        sa.Column("morph_features", sa.JSON(), nullable=False),
        sa.Column("stress_pattern", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "form_kind IN ('citation', 'inflected', 'fixed')",
            name="ck_language_form_kind",
        ),
        sa.CheckConstraint(CONTENT_STATUS, name="ck_language_form_status"),
        sa.CheckConstraint("revision >= 1", name="ck_language_form_revision"),
        sa.ForeignKeyConstraint(
            ["lexical_unit_id"],
            ["language_lexical_units.id"],
            name="fk_language_form_lexical_unit",
        ),
    )
    op.create_index(
        "ix_language_forms_lexical_unit",
        "language_forms",
        ["lexical_unit_id"],
    )
    op.create_table(
        "language_constructions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("morph_features", sa.JSON(), nullable=False),
        sa.Column("examples", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.CheckConstraint(CONTENT_STATUS, name="ck_language_construction_status"),
        sa.CheckConstraint(
            "revision >= 1",
            name="ck_language_construction_revision",
        ),
        sa.UniqueConstraint("code", name="uq_language_construction_code"),
    )
    op.create_table(
        "curriculum_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("curriculum_code", sa.Text(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "version_number >= 1",
            name="ck_curriculum_version_number",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'retired')",
            name="ck_curriculum_version_status",
        ),
        sa.CheckConstraint(
            "(status = 'draft' AND published_at IS NULL AND retired_at IS NULL) OR "
            "(status = 'active' AND published_at IS NOT NULL AND retired_at IS NULL) OR "
            "(status = 'retired' AND published_at IS NOT NULL AND retired_at IS NOT NULL)",
            name="ck_curriculum_version_lifecycle",
        ),
        sa.UniqueConstraint(
            "curriculum_code",
            "version_number",
            name="uq_curriculum_version_code_number",
        ),
    )
    op.create_index(
        "uq_curriculum_versions_one_active",
        "curriculum_versions",
        ["curriculum_code"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "curriculum_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("curriculum_version_id", sa.String(36), nullable=False),
        sa.Column("target_key", sa.String(255), nullable=False),
        sa.Column("target_kind", sa.String(20), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("capability", sa.String(32), nullable=False),
        sa.Column("modality", sa.String(16), nullable=False),
        sa.Column("condition_payload", sa.JSON(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("outcome_code", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "target_kind IN ('sense', 'form', 'construction')",
            name="ck_curriculum_node_target_kind",
        ),
        sa.CheckConstraint(
            "capability IN ('recognize_meaning', 'retrieve_form', "
            "'apply_construction')",
            name="ck_curriculum_node_capability",
        ),
        sa.CheckConstraint("modality IN ('written')", name="ck_curriculum_node_modality"),
        sa.CheckConstraint(
            "priority >= 0 AND priority <= 100",
            name="ck_curriculum_node_priority",
        ),
        sa.CheckConstraint(
            "substr(outcome_code, 1, 2) IN ('A1', 'A2', 'B1', 'B2', 'C1', 'C2') "
            "AND substr(outcome_code, 3, 1) = '.' AND length(outcome_code) > 3",
            name="ck_curriculum_node_outcome_code",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_version_id"],
            ["curriculum_versions.id"],
            name="fk_curriculum_node_version",
        ),
        sa.UniqueConstraint(
            "curriculum_version_id",
            "target_key",
            name="uq_curriculum_node_version_target",
        ),
        sa.UniqueConstraint(
            "curriculum_version_id",
            "id",
            name="uq_curriculum_node_version_id",
        ),
    )
    op.create_index(
        "ix_curriculum_nodes_target",
        "curriculum_nodes",
        ["target_key"],
    )
    op.create_table(
        "curriculum_prerequisites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("curriculum_version_id", sa.String(36), nullable=False),
        sa.Column("prerequisite_node_id", sa.String(36), nullable=False),
        sa.Column("dependent_node_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.CheckConstraint("kind IN ('hard', 'soft')", name="ck_curriculum_prerequisite_kind"),
        sa.CheckConstraint(
            "prerequisite_node_id <> dependent_node_id",
            name="ck_curriculum_prerequisite_distinct_nodes",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_version_id"],
            ["curriculum_versions.id"],
            name="fk_curriculum_prerequisite_version",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_version_id", "prerequisite_node_id"],
            ["curriculum_nodes.curriculum_version_id", "curriculum_nodes.id"],
            name="fk_curriculum_prerequisite_source",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_version_id", "dependent_node_id"],
            ["curriculum_nodes.curriculum_version_id", "curriculum_nodes.id"],
            name="fk_curriculum_prerequisite_dependent",
        ),
        sa.UniqueConstraint(
            "curriculum_version_id",
            "prerequisite_node_id",
            "dependent_node_id",
            name="uq_curriculum_prerequisite_edge",
        ),
    )
    op.create_table(
        "practice_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("learner_id", sa.String(80), nullable=False),
        sa.Column("curriculum_version_id", sa.String(36), nullable=True),
        sa.Column("legacy_quiz_attempt_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("selection_policy_version", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'abandoned')",
            name="ck_practice_run_status",
        ),
        sa.CheckConstraint(
            "(status = 'active' AND ended_at IS NULL) OR "
            "(status IN ('completed', 'abandoned') AND ended_at IS NOT NULL)",
            name="ck_practice_run_lifecycle",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["user_profiles.user_id"],
            name="fk_practice_run_learner",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_version_id"],
            ["curriculum_versions.id"],
            name="fk_practice_run_curriculum_version",
        ),
        sa.ForeignKeyConstraint(
            ["legacy_quiz_attempt_id"],
            ["quiz_attempts.id"],
            name="fk_practice_run_legacy_quiz_attempt",
        ),
        sa.UniqueConstraint(
            "legacy_quiz_attempt_id",
            name="uq_practice_run_legacy_quiz_attempt",
        ),
        sa.UniqueConstraint("id", "learner_id", name="uq_practice_run_learner"),
        sa.UniqueConstraint(
            "id",
            "selection_policy_version",
            name="uq_practice_run_selection_policy",
        ),
    )
    op.create_index(
        "ix_practice_runs_learner_status",
        "practice_runs",
        ["learner_id", "status"],
    )
    op.create_table(
        "activity_instances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("practice_run_id", sa.String(36), nullable=False),
        sa.Column("target_key", sa.String(255), nullable=False),
        sa.Column("learning_intent", sa.String(16), nullable=False),
        sa.Column("activity_kind", sa.String(16), nullable=False),
        sa.Column("operation", sa.String(16), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("retry_of_activity_instance_id", sa.String(36), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("spec_payload", sa.JSON(), nullable=False),
        sa.Column("selection_policy_version", sa.Text(), nullable=False),
        sa.Column("selection_reason_payload", sa.JSON(), nullable=False),
        sa.Column("selection_propensity", sa.Float(), nullable=True),
        sa.Column("generator_kind", sa.String(24), nullable=False),
        sa.Column("generator_version", sa.Text(), nullable=False),
        sa.Column("scorer_kind", sa.String(24), nullable=True),
        sa.Column("scorer_version", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "learning_intent IN ('acquire', 'review', 'strengthen', 'assess')",
            name="ck_activity_instance_learning_intent",
        ),
        sa.CheckConstraint(
            "activity_kind IN ('exposure', 'exercise')",
            name="ck_activity_instance_kind",
        ),
        sa.CheckConstraint(
            "operation IN ('recognize', 'retrieve', 'complete', 'transform')",
            name="ck_activity_instance_operation",
        ),
        sa.CheckConstraint(
            "sequence_number >= 1",
            name="ck_activity_instance_sequence",
        ),
        sa.CheckConstraint(
            "attempt_number >= 1",
            name="ck_activity_instance_attempt",
        ),
        sa.CheckConstraint(
            "selection_propensity IS NULL OR "
            "(selection_propensity >= 0 AND selection_propensity <= 1)",
            name="ck_activity_instance_propensity",
        ),
        sa.CheckConstraint(
            "generator_kind IN ('curated', 'model_assisted')",
            name="ck_activity_instance_generator_kind",
        ),
        sa.CheckConstraint(
            "scorer_kind IN ('deterministic', 'self_report', 'model_assisted')",
            name="ck_activity_instance_scorer_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'cancelled')",
            name="ck_activity_instance_status",
        ),
        sa.CheckConstraint(
            "(activity_kind = 'exposure' AND operation IS NULL AND "
            "scorer_kind IS NULL AND scorer_version IS NULL) OR "
            "(activity_kind = 'exercise' AND operation IS NOT NULL AND "
            "scorer_kind IS NOT NULL AND scorer_version IS NOT NULL)",
            name="ck_activity_instance_shape",
        ),
        sa.CheckConstraint(
            "(retry_of_activity_instance_id IS NULL AND attempt_number = 1) OR "
            "(retry_of_activity_instance_id IS NOT NULL AND "
            "retry_of_activity_instance_id <> id AND attempt_number >= 2)",
            name="ck_activity_instance_retry",
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND terminal_at IS NULL) OR "
            "(status IN ('completed', 'cancelled') AND terminal_at IS NOT NULL)",
            name="ck_activity_instance_lifecycle",
        ),
        sa.ForeignKeyConstraint(
            ["practice_run_id", "selection_policy_version"],
            ["practice_runs.id", "practice_runs.selection_policy_version"],
            name="fk_activity_instance_run_policy",
        ),
        sa.ForeignKeyConstraint(
            ["practice_run_id", "retry_of_activity_instance_id", "target_key"],
            [
                "activity_instances.practice_run_id",
                "activity_instances.id",
                "activity_instances.target_key",
            ],
            name="fk_activity_instance_retry",
        ),
        sa.UniqueConstraint(
            "practice_run_id",
            "sequence_number",
            name="uq_activity_instance_run_sequence",
        ),
        sa.UniqueConstraint(
            "practice_run_id",
            "id",
            "target_key",
            name="uq_activity_instance_run_target",
        ),
        sa.UniqueConstraint(
            "practice_run_id",
            "id",
            "target_key",
            "activity_kind",
            name="uq_activity_instance_event_owner",
        ),
    )
    op.create_index(
        "ix_activity_instances_retry",
        "activity_instances",
        ["retry_of_activity_instance_id"],
    )
    op.create_table(
        "learning_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("learner_id", sa.String(80), nullable=False),
        sa.Column("practice_run_id", sa.String(36), nullable=False),
        sa.Column("activity_instance_id", sa.String(36), nullable=False),
        sa.Column("target_key", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(24), nullable=False),
        sa.Column("activity_kind", sa.String(16), nullable=False),
        sa.Column("observation_payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("schema_version >= 1", name="ck_learning_event_schema_version"),
        sa.CheckConstraint(
            "event_type IN ('exposure', 'response_evaluated')",
            name="ck_learning_event_type",
        ),
        sa.CheckConstraint(
            "activity_kind IN ('exposure', 'exercise')",
            name="ck_learning_event_activity_kind",
        ),
        sa.CheckConstraint(
            "(activity_kind = 'exposure' AND event_type = 'exposure') OR "
            "(activity_kind = 'exercise' AND event_type = 'response_evaluated')",
            name="ck_learning_event_shape",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["user_profiles.user_id"],
            name="fk_learning_event_learner",
        ),
        sa.ForeignKeyConstraint(
            ["practice_run_id", "learner_id"],
            ["practice_runs.id", "practice_runs.learner_id"],
            name="fk_learning_event_run_learner",
        ),
        sa.ForeignKeyConstraint(
            [
                "practice_run_id",
                "activity_instance_id",
                "target_key",
                "activity_kind",
            ],
            [
                "activity_instances.practice_run_id",
                "activity_instances.id",
                "activity_instances.target_key",
                "activity_instances.activity_kind",
            ],
            name="fk_learning_event_activity",
        ),
        sa.UniqueConstraint(
            "learner_id",
            "idempotency_key",
            name="uq_learning_event_idempotency",
        ),
        sa.UniqueConstraint(
            "activity_instance_id",
            name="uq_learning_event_activity_instance",
        ),
    )
    op.create_index(
        "ix_learning_events_learner_time",
        "learning_events",
        ["learner_id", "occurred_at"],
    )
    op.create_index(
        "ix_learning_events_learner_target_time",
        "learning_events",
        ["learner_id", "target_key", "occurred_at", "id"],
    )
    op.create_table(
        "learner_target_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("learner_id", sa.String(80), nullable=False),
        sa.Column("target_key", sa.String(255), nullable=False),
        sa.Column("competence_success_weight", sa.Float(), nullable=False),
        sa.Column("competence_failure_weight", sa.Float(), nullable=False),
        sa.Column("competence_peak", sa.Float(), nullable=False),
        sa.Column("uncertainty", sa.Float(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("baseline_kind", sa.String(24), nullable=False),
        sa.Column("baseline_memory_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("baseline_memory_interval_days", sa.Integer(), nullable=False),
        sa.Column("baseline_payload", sa.JSON(), nullable=False),
        sa.Column("last_evidence_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_id", sa.String(36), nullable=True),
        sa.Column("memory_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("memory_interval_days", sa.Integer(), nullable=False),
        sa.Column("memory_lapses", sa.Integer(), nullable=False),
        sa.Column("memory_policy_version", sa.Text(), nullable=False),
        sa.Column("projection_policy_version", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "competence_success_weight >= 0",
            name="ck_learner_target_state_success_weight",
        ),
        sa.CheckConstraint(
            "competence_failure_weight >= 0",
            name="ck_learner_target_state_failure_weight",
        ),
        sa.CheckConstraint(
            "competence_peak >= 0 AND competence_peak <= 1",
            name="ck_learner_target_state_competence_peak",
        ),
        sa.CheckConstraint(
            "uncertainty >= 0 AND uncertainty <= 1",
            name="ck_learner_target_state_uncertainty",
        ),
        sa.CheckConstraint(
            "evidence_count >= 0",
            name="ck_learner_target_state_evidence_count",
        ),
        sa.CheckConstraint(
            "baseline_kind IN ('neutral', 'legacy_bootstrap')",
            name="ck_learner_target_state_baseline_kind",
        ),
        sa.CheckConstraint(
            "baseline_memory_interval_days >= 0",
            name="ck_learner_target_state_baseline_interval",
        ),
        sa.CheckConstraint(
            "memory_interval_days >= 0",
            name="ck_learner_target_state_memory_interval",
        ),
        sa.CheckConstraint(
            "memory_lapses >= 0",
            name="ck_learner_target_state_memory_lapses",
        ),
        sa.CheckConstraint(
            "(evidence_count = 0 AND last_evidence_at IS NULL AND "
            "last_event_id IS NULL) OR "
            "(evidence_count > 0 AND last_evidence_at IS NOT NULL AND "
            "last_event_id IS NOT NULL)",
            name="ck_learner_target_state_evidence_shape",
        ),
        sa.CheckConstraint(
            "competence_success_weight + competence_failure_weight <= evidence_count",
            name="ck_learner_target_state_weight_sum",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["user_profiles.user_id"],
            name="fk_learner_target_state_learner",
        ),
        sa.UniqueConstraint(
            "learner_id",
            "target_key",
            name="uq_learner_target_states_learner_target",
        ),
    )
    op.create_index(
        "ix_learner_target_states_due",
        "learner_target_states",
        ["learner_id", "memory_due_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_learner_target_states_due", table_name="learner_target_states")
    op.drop_table("learner_target_states")
    op.drop_index(
        "ix_learning_events_learner_target_time",
        table_name="learning_events",
    )
    op.drop_index("ix_learning_events_learner_time", table_name="learning_events")
    op.drop_table("learning_events")
    op.drop_index("ix_activity_instances_retry", table_name="activity_instances")
    op.drop_table("activity_instances")
    op.drop_index("ix_practice_runs_learner_status", table_name="practice_runs")
    op.drop_table("practice_runs")
    op.drop_table("curriculum_prerequisites")
    op.drop_index("ix_curriculum_nodes_target", table_name="curriculum_nodes")
    op.drop_table("curriculum_nodes")
    op.drop_index(
        "uq_curriculum_versions_one_active",
        table_name="curriculum_versions",
    )
    op.drop_table("curriculum_versions")
    op.drop_table("language_constructions")
    op.drop_index("ix_language_forms_lexical_unit", table_name="language_forms")
    op.drop_table("language_forms")
    op.drop_index("ix_language_senses_lexical_unit", table_name="language_senses")
    op.drop_table("language_senses")
    op.drop_table("language_lexical_units")
