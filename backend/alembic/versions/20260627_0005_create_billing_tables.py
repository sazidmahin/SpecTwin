"""create billing tables

Revision ID: 20260627_0005
Revises: 20260627_0004
Create Date: 2026-06-27 00:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260627_0005"
down_revision: str | None = "20260627_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

plans_table = sa.table(
    "plans",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("description", sa.Text),
    sa.column("workspace_type", sa.String),
    sa.column("price_cents_monthly", sa.Integer),
    sa.column("max_projects", sa.Integer),
    sa.column("max_members", sa.Integer),
    sa.column("monthly_srs_generations", sa.Integer),
    sa.column("monthly_ai_diagram_generations", sa.Integer),
    sa.column("monthly_manual_diagram_saves", sa.Integer),
    sa.column("can_use_manual_drawio", sa.Boolean),
    sa.column("can_generate_srs", sa.Boolean),
    sa.column("can_generate_ai_diagrams", sa.Boolean),
    sa.column("can_export_srs", sa.Boolean),
    sa.column("can_export_diagrams", sa.Boolean),
    sa.column("is_active", sa.Boolean),
)


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("workspace_type", sa.String(length=32), nullable=False),
        sa.Column("price_cents_monthly", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_projects", sa.Integer(), nullable=False),
        sa.Column("max_members", sa.Integer(), nullable=False),
        sa.Column("monthly_srs_generations", sa.Integer(), nullable=False),
        sa.Column("monthly_ai_diagram_generations", sa.Integer(), nullable=False),
        sa.Column("monthly_manual_diagram_saves", sa.Integer(), nullable=False),
        sa.Column("can_use_manual_drawio", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("can_generate_srs", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("can_generate_ai_diagrams", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("can_export_srs", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("can_export_diagrams", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plans")),
        sa.UniqueConstraint("code", name=op.f("uq_plans_code")),
    )
    op.create_index(op.f("ix_plans_code"), "plans", ["code"])

    op.bulk_insert(
        plans_table,
        [
            {
                "id": "00000000-0000-0000-0000-000000000101",
                "code": "free_individual",
                "name": "Free Individual",
                "description": "Starter plan for personal workspaces.",
                "workspace_type": "personal",
                "price_cents_monthly": 0,
                "max_projects": 3,
                "max_members": 1,
                "monthly_srs_generations": 0,
                "monthly_ai_diagram_generations": 0,
                "monthly_manual_diagram_saves": 20,
                "can_use_manual_drawio": True,
                "can_generate_srs": False,
                "can_generate_ai_diagrams": False,
                "can_export_srs": False,
                "can_export_diagrams": False,
                "is_active": True,
            },
            {
                "id": "00000000-0000-0000-0000-000000000102",
                "code": "individual_pro",
                "name": "Individual Pro",
                "description": "Paid plan for personal AI generation and exports.",
                "workspace_type": "personal",
                "price_cents_monthly": 1900,
                "max_projects": 50,
                "max_members": 1,
                "monthly_srs_generations": 100,
                "monthly_ai_diagram_generations": 50,
                "monthly_manual_diagram_saves": 500,
                "can_use_manual_drawio": True,
                "can_generate_srs": True,
                "can_generate_ai_diagrams": True,
                "can_export_srs": True,
                "can_export_diagrams": True,
                "is_active": True,
            },
            {
                "id": "00000000-0000-0000-0000-000000000103",
                "code": "team",
                "name": "Team",
                "description": "Shared workspace plan for organizations.",
                "workspace_type": "organization",
                "price_cents_monthly": 4900,
                "max_projects": 100,
                "max_members": 10,
                "monthly_srs_generations": 500,
                "monthly_ai_diagram_generations": 200,
                "monthly_manual_diagram_saves": 1000,
                "can_use_manual_drawio": True,
                "can_generate_srs": True,
                "can_generate_ai_diagrams": True,
                "can_export_srs": True,
                "can_export_diagrams": True,
                "is_active": True,
            },
            {
                "id": "00000000-0000-0000-0000-000000000104",
                "code": "enterprise",
                "name": "Enterprise",
                "description": "High-limit organization plan.",
                "workspace_type": "organization",
                "price_cents_monthly": 19900,
                "max_projects": 100000,
                "max_members": 100000,
                "monthly_srs_generations": 100000,
                "monthly_ai_diagram_generations": 100000,
                "monthly_manual_diagram_saves": 100000,
                "can_use_manual_drawio": True,
                "can_generate_srs": True,
                "can_generate_ai_diagrams": True,
                "can_export_srs": True,
                "can_export_diagrams": True,
                "is_active": True,
            },
        ],
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("current_period_start", sa.Date(), nullable=False),
        sa.Column("current_period_end", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], name=op.f("fk_subscriptions_plan_id_plans")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name=op.f("fk_subscriptions_workspace_id_workspaces")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscriptions")),
        sa.UniqueConstraint("workspace_id", name=op.f("uq_subscriptions_workspace_id")),
    )
    op.create_index(op.f("ix_subscriptions_plan_id"), "subscriptions", ["plan_id"])
    op.create_index(op.f("ix_subscriptions_workspace_id"), "subscriptions", ["workspace_id"])

    op.create_table(
        "usage_counters",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_key", sa.String(length=7), nullable=False),
        sa.Column("srs_generations", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ai_diagram_generations", sa.Integer(), server_default="0", nullable=False),
        sa.Column("manual_diagram_saves", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name=op.f("fk_usage_counters_workspace_id_workspaces")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_counters")),
        sa.UniqueConstraint("workspace_id", "period_key", name=op.f("uq_usage_counters_workspace_id")),
    )
    op.create_index(op.f("ix_usage_counters_workspace_id"), "usage_counters", ["workspace_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_usage_counters_workspace_id"), table_name="usage_counters")
    op.drop_table("usage_counters")
    op.drop_index(op.f("ix_subscriptions_workspace_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_plan_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index(op.f("ix_plans_code"), table_name="plans")
    op.drop_table("plans")