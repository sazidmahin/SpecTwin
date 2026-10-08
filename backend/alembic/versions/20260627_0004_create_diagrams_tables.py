"""create diagrams tables

Revision ID: 20260627_0004
Revises: 20260627_0003
Create Date: 2026-06-27 00:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260627_0004"
down_revision: str | None = "20260627_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "diagrams",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("diagram_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_diagrams_created_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_diagrams_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_diagrams_workspace_id_workspaces"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_diagrams")),
    )
    op.create_index(op.f("ix_diagrams_created_by_user_id"), "diagrams", ["created_by_user_id"])
    op.create_index(op.f("ix_diagrams_project_id"), "diagrams", ["project_id"])
    op.create_index(op.f("ix_diagrams_status"), "diagrams", ["status"])
    op.create_index(op.f("ix_diagrams_workspace_id"), "diagrams", ["workspace_id"])

    op.create_table(
        "diagram_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("diagram_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("drawio_xml", sa.Text(), nullable=False),
        sa.Column("diagram_json", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_diagram_versions_created_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["diagram_id"],
            ["diagrams.id"],
            name=op.f("fk_diagram_versions_diagram_id_diagrams"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_diagram_versions_project_id_projects"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_diagram_versions_workspace_id_workspaces"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_diagram_versions")),
        sa.UniqueConstraint(
            "diagram_id", "version_number", name=op.f("uq_diagram_versions_diagram_id")
        ),
    )
    op.create_index(
        op.f("ix_diagram_versions_created_by_user_id"),
        "diagram_versions",
        ["created_by_user_id"],
    )
    op.create_index(op.f("ix_diagram_versions_diagram_id"), "diagram_versions", ["diagram_id"])
    op.create_index(op.f("ix_diagram_versions_project_id"), "diagram_versions", ["project_id"])
    op.create_index(op.f("ix_diagram_versions_workspace_id"), "diagram_versions", ["workspace_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_diagram_versions_workspace_id"), table_name="diagram_versions")
    op.drop_index(op.f("ix_diagram_versions_project_id"), table_name="diagram_versions")
    op.drop_index(op.f("ix_diagram_versions_diagram_id"), table_name="diagram_versions")
    op.drop_index(op.f("ix_diagram_versions_created_by_user_id"), table_name="diagram_versions")
    op.drop_table("diagram_versions")
    op.drop_index(op.f("ix_diagrams_workspace_id"), table_name="diagrams")
    op.drop_index(op.f("ix_diagrams_status"), table_name="diagrams")
    op.drop_index(op.f("ix_diagrams_project_id"), table_name="diagrams")
    op.drop_index(op.f("ix_diagrams_created_by_user_id"), table_name="diagrams")
    op.drop_table("diagrams")