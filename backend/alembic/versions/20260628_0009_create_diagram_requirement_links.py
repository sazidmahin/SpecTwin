"""create diagram requirement link table

Revision ID: 20260628_0009
Revises: 20260628_0008
Create Date: 2026-06-28 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260628_0009"
down_revision: str | None = "20260628_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "diagram_requirement_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("diagram_id", sa.Uuid(), nullable=False),
        sa.Column("diagram_version_id", sa.Uuid(), nullable=False),
        sa.Column("srs_document_id", sa.Uuid(), nullable=False),
        sa.Column("extracted_requirement_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_code", sa.String(length=32), nullable=False),
        sa.Column("diagram_element_id", sa.String(length=128), nullable=False),
        sa.Column("diagram_element_label", sa.String(length=255), nullable=False),
        sa.Column("link_reason", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="0.75", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["diagram_id"], ["diagrams.id"]),
        sa.ForeignKeyConstraint(["diagram_version_id"], ["diagram_versions.id"]),
        sa.ForeignKeyConstraint(["extracted_requirement_id"], ["extracted_requirements.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["srs_document_id"], ["srs_documents.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diagram_requirement_links_workspace_id", "diagram_requirement_links", ["workspace_id"])
    op.create_index("ix_diagram_requirement_links_project_id", "diagram_requirement_links", ["project_id"])
    op.create_index("ix_diagram_requirement_links_diagram_id", "diagram_requirement_links", ["diagram_id"])
    op.create_index("ix_diagram_requirement_links_diagram_version_id", "diagram_requirement_links", ["diagram_version_id"])
    op.create_index("ix_diagram_requirement_links_srs_document_id", "diagram_requirement_links", ["srs_document_id"])
    op.create_index("ix_diagram_requirement_links_extracted_requirement_id", "diagram_requirement_links", ["extracted_requirement_id"])
    op.create_index("ix_diagram_requirement_links_requirement_code", "diagram_requirement_links", ["requirement_code"])


def downgrade() -> None:
    op.drop_index("ix_diagram_requirement_links_requirement_code", table_name="diagram_requirement_links")
    op.drop_index("ix_diagram_requirement_links_extracted_requirement_id", table_name="diagram_requirement_links")
    op.drop_index("ix_diagram_requirement_links_srs_document_id", table_name="diagram_requirement_links")
    op.drop_index("ix_diagram_requirement_links_diagram_version_id", table_name="diagram_requirement_links")
    op.drop_index("ix_diagram_requirement_links_diagram_id", table_name="diagram_requirement_links")
    op.drop_index("ix_diagram_requirement_links_project_id", table_name="diagram_requirement_links")
    op.drop_index("ix_diagram_requirement_links_workspace_id", table_name="diagram_requirement_links")
    op.drop_table("diagram_requirement_links")