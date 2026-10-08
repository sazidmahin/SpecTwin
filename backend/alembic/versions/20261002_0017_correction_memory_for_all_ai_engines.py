"""correction memory for every AI engine, not just the Ollama pipeline

Two changes to generation_corrections:

- run_id becomes nullable, so the stateless Class Modeler can record a
  correction even though it has no pipeline run to hang it off.
- embedding_model records which embedder produced the stored vector. Ollama
  embeddings and the built-in lexical fallback live in different vector spaces,
  so a similarity search has to compare only rows that share an embedder.

Existing rows all came from the Ollama-only loop, so they are backfilled with
the Ollama embedding model that was in use when they were written.

Revision ID: 20261002_0017
Revises: 20260924_0016
Create Date: 2026-10-02 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261002_0017"
down_revision: str | None = "20260924_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_corrections",
        sa.Column("embedding_model", sa.String(64), nullable=False, server_default=""),
    )
    op.execute(
        "UPDATE generation_corrections SET embedding_model = 'ollama:nomic-embed-text' WHERE embedding_model = ''"
    )
    op.alter_column("generation_corrections", "run_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    # Class Modeler corrections have no run to point at, so they cannot survive
    # the column going back to NOT NULL.
    op.execute("DELETE FROM generation_corrections WHERE run_id IS NULL")
    op.alter_column("generation_corrections", "run_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("generation_corrections", "embedding_model")
