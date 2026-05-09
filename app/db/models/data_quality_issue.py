from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin


class DataQualityIssue(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "data_quality_issues"

    ingestion_run_id: Mapped[str | None] = mapped_column(ForeignKey("ingestion_runs.id"), index=True)
    source_record_id: Mapped[str | None] = mapped_column(String(200), index=True)
    severity: Mapped[str] = mapped_column(String(40), index=True)
    issue_type: Mapped[str] = mapped_column(String(80), index=True)
    message: Mapped[str] = mapped_column(Text)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSONB)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    ingestion_run = relationship("IngestionRun", back_populates="quality_issues")

