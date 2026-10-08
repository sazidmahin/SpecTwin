"""create srs document and extracted requirement tables

Revision ID: 20260628_0008
Revises: 20260628_0007
Create Date: 2026-06-28 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260628_0008"
down_revision: str | None = "20260628_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "srs_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_input_id", sa.Uuid(), nullable=False),
        sa.Column("generation_job_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["generation_job_id"], ["generation_jobs.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["requirement_input_id"], ["requirement_inputs.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_srs_documents_workspace_id", "srs_documents", ["workspace_id"])
    op.create_index("ix_srs_documents_project_id", "srs_documents", ["project_id"])
    op.create_index("ix_srs_documents_requirement_input_id", "srs_documents", ["requirement_input_id"])
    op.create_index("ix_srs_documents_generation_job_id", "srs_documents", ["generation_job_id"])
    op.create_index("ix_srs_documents_status", "srs_documents", ["status"])
    op.create_index("ix_srs_documents_created_by_user_id", "srs_documents", ["created_by_user_id"])

    op.create_table(
        "extracted_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("srs_document_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_input_id", sa.Uuid(), nullable=False),
        sa.Column("generation_job_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_code", sa.String(length=32), nullable=False),
        sa.Column("requirement_text", sa.Text(), nullable=False),
        sa.Column("requirement_type", sa.String(length=32), nullable=False),
        sa.Column("nfr_subtype", sa.String(length=64), nullable=True),
        sa.Column("source_trace", sa.Text(), nullable=False),
        sa.Column("extraction_reason", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="0.8", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["generation_job_id"], ["generation_jobs.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["requirement_input_id"], ["requirement_inputs.id"]),
        sa.ForeignKeyConstraint(["srs_document_id"], ["srs_documents.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_extracted_requirements_workspace_id", "extracted_requirements", ["workspace_id"])
    op.create_index("ix_extracted_requirements_project_id", "extracted_requirements", ["project_id"])
    op.create_index("ix_extracted_requirements_srs_document_id", "extracted_requirements", ["srs_document_id"])
    op.create_index("ix_extracted_requirements_requirement_input_id", "extracted_requirements", ["requirement_input_id"])
    op.create_index("ix_extracted_requirements_generation_job_id", "extracted_requirements", ["generation_job_id"])
    op.create_index("ix_extracted_requirements_requirement_code", "extracted_requirements", ["requirement_code"])
    op.create_index("ix_extracted_requirements_requirement_type", "extracted_requirements", ["requirement_type"])
    op.create_index("ix_extracted_requirements_nfr_subtype", "extracted_requirements", ["nfr_subtype"])


def downgrade() -> None:
    op.drop_index("ix_extracted_requirements_nfr_subtype", table_name="extracted_requirements")
    op.drop_index("ix_extracted_requirements_requirement_type", table_name="extracted_requirements")
    op.drop_index("ix_extracted_requirements_requirement_code", table_name="extracted_requirements")
    op.drop_index("ix_extracted_requirements_generation_job_id", table_name="extracted_requirements")
    op.drop_index("ix_extracted_requirements_requirement_input_id", table_name="extracted_requirements")
    op.drop_index("ix_extracted_requirements_srs_document_id", table_name="extracted_requirements")
    op.drop_index("ix_extracted_requirements_project_id", table_name="extracted_requirements")
    op.drop_index("ix_extracted_requirements_workspace_id", table_name="extracted_requirements")
    op.drop_table("extracted_requirements")
    op.drop_index("ix_srs_documents_created_by_user_id", table_name="srs_documents")
    op.drop_index("ix_srs_documents_status", table_name="srs_documents")
    op.drop_index("ix_srs_documents_generation_job_id", table_name="srs_documents")
    op.drop_index("ix_srs_documents_requirement_input_id", table_name="srs_documents")
    op.drop_index("ix_srs_documents_project_id", table_name="srs_documents")
    op.drop_index("ix_srs_documents_workspace_id", table_name="srs_documents")
    op.drop_table("srs_documents")