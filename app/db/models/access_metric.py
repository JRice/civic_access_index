from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin


class AccessMetric(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "access_metrics"

    census_tract_id: Mapped[str] = mapped_column(ForeignKey("census_tracts.id"), index=True)
    metric_name: Mapped[str] = mapped_column(String(120), index=True)
    metric_value: Mapped[float] = mapped_column(Float)
    metric_unit: Mapped[str | None] = mapped_column(String(80))
    percentile_statewide: Mapped[float | None] = mapped_column(Float)
    percentile_county: Mapped[float | None] = mapped_column(Float)
    source_run_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    census_tract = relationship("CensusTract", back_populates="metrics")

