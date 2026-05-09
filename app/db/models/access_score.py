from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin


class AccessScore(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "access_scores"

    census_tract_id: Mapped[str] = mapped_column(ForeignKey("census_tracts.id"), unique=True, index=True)
    food_access_score: Mapped[float | None] = mapped_column(Float)
    healthcare_access_score: Mapped[float | None] = mapped_column(Float)
    transit_access_score: Mapped[float | None] = mapped_column(Float)
    digital_access_score: Mapped[float | None] = mapped_column(Float)
    civic_access_index: Mapped[float | None] = mapped_column(Float, index=True)
    vulnerability_score: Mapped[float | None] = mapped_column(Float)
    composite_score: Mapped[float | None] = mapped_column(Float, index=True)
    explanation_json: Mapped[dict | None] = mapped_column(JSONB)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    census_tract = relationship("CensusTract", back_populates="score")

