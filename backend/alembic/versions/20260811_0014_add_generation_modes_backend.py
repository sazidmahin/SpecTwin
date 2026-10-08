"""add BYOK settings and editable generation pipelines

Revision ID: 20260811_0014
Revises: 20260806_0013
Create Date: 2026-08-11 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0014"
down_revision: str | None = "20260806_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_ai_provider_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("key_last_four", sa.String(8), nullable=False),
        sa.Column("selected_model", sa.String(255), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(32), nullable=False, server_default="configured"),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_ai_provider_credentials_user_provider"),
    )
    op.create_index(
        "ix_user_ai_provider_credentials_user_id", "user_ai_provider_credentials", ["user_id"]
    )
    op.create_index(
        "ix_user_ai_provider_credentials_provider", "user_ai_provider_credentials", ["provider"]
    )

    op.create_table(
        "generation_pipeline_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("requirement_input_id", sa.Uuid(), sa.ForeignKey("requirement_inputs.id"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("generation_mode", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("model_name", sa.String(255), nullable=True),
        sa.Column(
            "provider_credential_id",
            sa.Uuid(),
            sa.ForeignKey("user_ai_provider_credentials.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("current_stage", sa.String(64), nullable=False, server_default="input"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ready_for_review"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in (
        "workspace_id",
        "project_id",
        "requirement_input_id",
        "generation_mode",
        "status",
        "created_by_user_id",
    ):
        op.create_index(f"ix_generation_pipeline_runs_{column}", "generation_pipeline_runs", [column])

    op.create_table(
        "generation_stage_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("generation_pipeline_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("stage_name", sa.String(64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "parent_revision_id",
            sa.Uuid(),
            sa.ForeignKey("generation_stage_revisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="ready_for_review"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "run_id", "stage_name", "version_number", name="uq_generation_stage_revision_version"
        ),
    )
    for column in ("run_id", "workspace_id", "project_id", "stage_name", "status"):
        op.create_index(
            f"ix_generation_stage_revisions_{column}", "generation_stage_revisions", [column]
        )


def downgrade() -> None:
    op.drop_table("generation_stage_revisions")
    op.drop_table("generation_pipeline_runs")
    op.drop_table("user_ai_provider_credentials")
