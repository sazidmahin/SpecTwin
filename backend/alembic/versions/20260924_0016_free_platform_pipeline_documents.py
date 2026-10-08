"""make the platform free and publish SRS documents from pipeline runs

Drops billing (plans, subscriptions, usage counters), the standalone rule-system API tables and the
legacy platform-key SRS generation tables. SRS documents now point at the pipeline run that
produced them and at the class diagram published alongside them; LLM calls point at pipeline runs.

This migration is irreversible: the dropped features no longer exist in the application.

Revision ID: 20260924_0016
Revises: 20260921_0015
Create Date: 2026-09-24 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0016"
down_revision: str | None = "20260921_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RULE_SYSTEM_TABLES = (
    "rule_attribute_definitions",
    "rule_method_definitions",
    "rule_relationship_definitions",
    "rule_class_definitions",
    "rule_requirements",
    "rule_clarification_answers",
    "rule_clarification_questions",
    "rule_extracted_facts",
    "rule_clauses",
    "rule_sentences",
    "rule_stage_approvals",
    "rule_xml_revisions",
    "rule_class_model_revisions",
    "rule_requirement_revisions",
    "rule_final_story_revisions",
    "rule_story_revisions",
    "rule_dictionary_entries",
    "rule_dictionary_versions",
    "rule_definitions",
    "rule_versions",
    "rule_audit_events",
    "rule_projects",
)


def upgrade() -> None:
    # Legacy requirement links and extracted requirements hang off the old generation jobs.
    op.execute("DROP TABLE IF EXISTS diagram_requirement_links")
    op.execute("DROP TABLE IF EXISTS extracted_requirements")

    # SRS documents: detach from legacy generation tables, attach to pipeline runs + diagrams.
    op.drop_column("srs_documents", "requirement_input_id")
    op.drop_column("srs_documents", "generation_job_id")
    op.add_column("srs_documents", sa.Column("pipeline_run_id", sa.Uuid(), nullable=True))
    op.add_column("srs_documents", sa.Column("diagram_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_srs_documents_pipeline_run_id_generation_pipeline_runs",
        "srs_documents",
        "generation_pipeline_runs",
        ["pipeline_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_srs_documents_diagram_id_diagrams",
        "srs_documents",
        "diagrams",
        ["diagram_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_srs_documents_pipeline_run_id", "srs_documents", ["pipeline_run_id"], unique=True)

    # LLM calls: record the pipeline run instead of the legacy job.
    op.drop_column("llm_calls", "generation_job_id")
    op.add_column("llm_calls", sa.Column("pipeline_run_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_llm_calls_pipeline_run_id_generation_pipeline_runs",
        "llm_calls",
        "generation_pipeline_runs",
        ["pipeline_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_llm_calls_pipeline_run_id", "llm_calls", ["pipeline_run_id"])

    op.drop_column("generation_pipeline_runs", "requirement_input_id")
    op.execute("DROP TABLE IF EXISTS generation_jobs")
    op.execute("DROP TABLE IF EXISTS requirement_inputs")

    # Billing: the platform is free.
    op.execute("DROP TABLE IF EXISTS usage_counters")
    op.execute("DROP TABLE IF EXISTS subscriptions")
    op.execute("DROP TABLE IF EXISTS plans")

    # Standalone, unauthenticated rule-system API (superseded by the generation pipeline).
    for table in RULE_SYSTEM_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


def downgrade() -> None:
    raise NotImplementedError("20260924_0016 is irreversible: billing and legacy generation were removed")
