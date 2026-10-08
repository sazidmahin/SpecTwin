"""create deterministic rule system tables

Revision ID: 20260806_0013
Revises: 20260628_0012
Create Date: 2026-08-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260806_0013"
down_revision: str | None = "20260628_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def ts(name: str = "created_at") -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def revision_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("rule_projects.id"), nullable=False, index=True),
        ts(),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("dictionary_version_id", sa.String(64), nullable=False, server_default="dict_v1"),
        sa.Column("rule_version_id", sa.String(64), nullable=False, server_default="rules_v1"),
    ]


def upgrade() -> None:
    op.create_table(
        "rule_projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("dictionary_version_id", sa.String(64), nullable=False, server_default="dict_v1"),
        sa.Column("rule_version_id", sa.String(64), nullable=False, server_default="rules_v1"),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        ts(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table("rule_story_revisions", *revision_columns(), sa.Column("original_text", sa.Text(), nullable=False), sa.Column("normalized_text", sa.Text(), nullable=True))
    op.create_table(
        "rule_sentences",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("rule_projects.id"), nullable=False, index=True),
        sa.Column("story_revision_id", sa.Uuid(), sa.ForeignKey("rule_story_revisions.id"), nullable=False),
        sa.Column("stable_id", sa.String(64), nullable=False, index=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("sentence_index", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("end_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_rule_id", sa.String(64), nullable=False),
    )
    op.create_table(
        "rule_clauses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("rule_projects.id"), nullable=False, index=True),
        sa.Column("sentence_id", sa.Uuid(), sa.ForeignKey("rule_sentences.id"), nullable=False),
        sa.Column("stable_id", sa.String(64), nullable=False, index=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("sentence_index", sa.Integer(), nullable=False),
        sa.Column("clause_index", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("end_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_rule_id", sa.String(64), nullable=False),
    )
    op.create_table(
        "rule_extracted_facts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("rule_projects.id"), nullable=False, index=True),
        sa.Column("story_revision_id", sa.Uuid(), sa.ForeignKey("rule_story_revisions.id"), nullable=False),
        sa.Column("stable_id", sa.String(64), nullable=False, index=True),
        sa.Column("source_sentence_id", sa.String(64), nullable=False),
        sa.Column("source_clause_id", sa.String(64), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("matched_rule_id", sa.String(64), nullable=False),
        sa.Column("extraction_type", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        ts(),
    )
    op.create_table(
        "rule_clarification_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("rule_projects.id"), nullable=False, index=True),
        sa.Column("story_revision_id", sa.Uuid(), sa.ForeignKey("rule_story_revisions.id"), nullable=True),
        sa.Column("source_fact_id", sa.String(64), nullable=True, index=True),
        sa.Column("stable_id", sa.String(64), nullable=False, index=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_sentence", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("triggered_rule_id", sa.String(64), nullable=False),
        sa.Column("related_actor", sa.String(255), nullable=True),
        sa.Column("related_action", sa.String(255), nullable=True),
        sa.Column("related_object", sa.String(255), nullable=True),
        sa.Column("suggested_options", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("answer_mapping", sa.String(64), nullable=True),
        ts(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "rule_clarification_answers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("rule_projects.id"), nullable=False, index=True),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("rule_clarification_questions.id"), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="answered"),
        sa.Column("applied_slot", sa.String(64), nullable=True),
        ts(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table("rule_final_story_revisions", *revision_columns(), sa.Column("data", sa.JSON(), nullable=False))
    op.create_table("rule_requirement_revisions", *revision_columns(), sa.Column("data", sa.JSON(), nullable=False))
    op.create_table(
        "rule_requirements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("rule_projects.id"), nullable=False, index=True),
        sa.Column("revision_id", sa.Uuid(), sa.ForeignKey("rule_requirement_revisions.id"), nullable=True),
        sa.Column("requirement_id", sa.String(64), nullable=False, index=True),
        sa.Column("requirement_type", sa.String(32), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        ts(),
    )
    op.create_table("rule_class_model_revisions", *revision_columns(), sa.Column("data", sa.JSON(), nullable=False))
    op.create_table(
        "rule_class_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("rule_projects.id"), nullable=False, index=True),
        sa.Column("revision_id", sa.Uuid(), sa.ForeignKey("rule_class_model_revisions.id"), nullable=True),
        sa.Column("class_id", sa.String(128), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table("rule_attribute_definitions", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("rule_projects.id"), nullable=False, index=True), sa.Column("class_id", sa.String(128), nullable=False, index=True), sa.Column("attribute_id", sa.String(128), nullable=False, index=True), sa.Column("name", sa.String(255), nullable=False), sa.Column("data", sa.JSON(), nullable=False))
    op.create_table("rule_method_definitions", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("rule_projects.id"), nullable=False, index=True), sa.Column("class_id", sa.String(128), nullable=False, index=True), sa.Column("method_id", sa.String(128), nullable=False, index=True), sa.Column("name", sa.String(255), nullable=False), sa.Column("data", sa.JSON(), nullable=False))
    op.create_table("rule_relationship_definitions", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("rule_projects.id"), nullable=False, index=True), sa.Column("revision_id", sa.Uuid(), sa.ForeignKey("rule_class_model_revisions.id"), nullable=True), sa.Column("relationship_id", sa.String(128), nullable=False, index=True), sa.Column("source_class_id", sa.String(128), nullable=False, index=True), sa.Column("target_class_id", sa.String(128), nullable=False, index=True), sa.Column("relationship_type", sa.String(32), nullable=False), sa.Column("data", sa.JSON(), nullable=False))
    op.create_table("rule_xml_revisions", *revision_columns(), sa.Column("xml_text", sa.Text(), nullable=False), sa.Column("class_model", sa.JSON(), nullable=False), sa.Column("validation", sa.JSON(), nullable=False), sa.Column("manual_override", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("rule_stage_approvals", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("rule_projects.id"), nullable=False, index=True), sa.Column("stage_name", sa.String(64), nullable=False, index=True), sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"), sa.Column("current_draft_version", sa.Integer(), nullable=False, server_default="0"), sa.Column("approved_version", sa.Integer(), nullable=True), sa.Column("dictionary_version_id", sa.String(64), nullable=False, server_default="dict_v1"), sa.Column("rule_version_id", sa.String(64), nullable=False, server_default="rules_v1"), sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("rule_dictionary_versions", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("version_id", sa.String(64), nullable=False, unique=True), sa.Column("status", sa.String(32), nullable=False, server_default="active"), sa.Column("data", sa.JSON(), nullable=False), ts(), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("rule_dictionary_entries", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("dictionary_name", sa.String(128), nullable=False, index=True), sa.Column("version_id", sa.String(64), nullable=False, index=True), sa.Column("key", sa.String(255), nullable=False), sa.Column("value", sa.JSON(), nullable=False), sa.Column("priority", sa.Integer(), nullable=False, server_default="100"), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("rule_projects.id"), nullable=True), ts(), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("rule_versions", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("version_id", sa.String(64), nullable=False, unique=True), sa.Column("status", sa.String(32), nullable=False, server_default="active"), sa.Column("data", sa.JSON(), nullable=False), ts())
    op.create_table("rule_definitions", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("rule_id", sa.String(128), nullable=False, unique=True), sa.Column("version_id", sa.String(64), nullable=False, index=True), sa.Column("description", sa.Text(), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("data", sa.JSON(), nullable=False), ts(), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("rule_audit_events", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("project_id", sa.Uuid(), sa.ForeignKey("rule_projects.id"), nullable=True, index=True), sa.Column("actor", sa.String(255), nullable=False, server_default="system"), sa.Column("entity_type", sa.String(128), nullable=False), sa.Column("entity_id", sa.String(128), nullable=True), sa.Column("action", sa.String(128), nullable=False), sa.Column("before_value", sa.JSON(), nullable=True), sa.Column("after_value", sa.JSON(), nullable=True), ts())


def downgrade() -> None:
    for table_name in [
        "rule_audit_events", "rule_definitions", "rule_versions", "rule_dictionary_entries", "rule_dictionary_versions",
        "rule_stage_approvals", "rule_xml_revisions", "rule_relationship_definitions", "rule_method_definitions",
        "rule_attribute_definitions", "rule_class_definitions", "rule_class_model_revisions", "rule_requirements",
        "rule_requirement_revisions", "rule_final_story_revisions", "rule_clarification_answers",
        "rule_clarification_questions", "rule_extracted_facts", "rule_clauses", "rule_sentences",
        "rule_story_revisions", "rule_projects",
    ]:
        op.drop_table(table_name)
