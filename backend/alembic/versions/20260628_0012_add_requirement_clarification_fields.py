"""add requirement clarification fields

Revision ID: 20260628_0012
Revises: 20260628_0011
Create Date: 2026-06-28 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260628_0012"
down_revision: str | None = "20260628_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "requirement_inputs",
        sa.Column("clarification_status", sa.String(length=32), server_default="not_required", nullable=False),
    )
    op.add_column(
        "requirement_inputs",
        sa.Column("clarifying_questions", sa.JSON(), server_default="[]", nullable=False),
    )
    op.add_column(
        "requirement_inputs",
        sa.Column("clarification_answers", sa.JSON(), server_default="[]", nullable=False),
    )
    op.add_column("requirement_inputs", sa.Column("refined_text", sa.Text(), nullable=True))
    op.add_column("requirement_inputs", sa.Column("refinement_metadata", sa.JSON(), nullable=True))
    op.create_index("ix_requirement_inputs_clarification_status", "requirement_inputs", ["clarification_status"])


def downgrade() -> None:
    op.drop_index("ix_requirement_inputs_clarification_status", table_name="requirement_inputs")
    op.drop_column("requirement_inputs", "refinement_metadata")
    op.drop_column("requirement_inputs", "refined_text")
    op.drop_column("requirement_inputs", "clarification_answers")
    op.drop_column("requirement_inputs", "clarifying_questions")
    op.drop_column("requirement_inputs", "clarification_status")
