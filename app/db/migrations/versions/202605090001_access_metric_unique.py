"""Add idempotent access metric uniqueness.

Revision ID: 202605090001
Revises: 202605080001
Create Date: 2026-05-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "202605090001"
down_revision: str | Sequence[str] | None = "202605080001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM access_metrics loser
        USING access_metrics keeper
        WHERE loser.census_tract_id = keeper.census_tract_id
          AND loser.metric_name = keeper.metric_name
          AND (
            loser.computed_at < keeper.computed_at
            OR (loser.computed_at = keeper.computed_at AND loser.id < keeper.id)
          )
        """
    )
    op.create_unique_constraint(
        "uq_access_metrics_tract_metric",
        "access_metrics",
        ["census_tract_id", "metric_name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_access_metrics_tract_metric", "access_metrics", type_="unique")
