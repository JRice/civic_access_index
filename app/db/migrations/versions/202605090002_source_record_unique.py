"""Add source record uniqueness for amenities and providers.

Revision ID: 202605090002
Revises: 202605090001
Create Date: 2026-05-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "202605090002"
down_revision: str | Sequence[str] | None = "202605090001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM amenities loser
        USING amenities keeper
        WHERE loser.source_id = keeper.source_id
          AND loser.source_record_id = keeper.source_record_id
          AND loser.id < keeper.id
        """
    )
    op.execute(
        """
        DELETE FROM providers loser
        USING providers keeper
        WHERE loser.source_id = keeper.source_id
          AND loser.source_record_id = keeper.source_record_id
          AND loser.id < keeper.id
        """
    )
    op.create_unique_constraint(
        "uq_amenities_source_record",
        "amenities",
        ["source_id", "source_record_id"],
    )
    op.create_unique_constraint(
        "uq_providers_source_record",
        "providers",
        ["source_id", "source_record_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_providers_source_record", "providers", type_="unique")
    op.drop_constraint("uq_amenities_source_record", "amenities", type_="unique")
