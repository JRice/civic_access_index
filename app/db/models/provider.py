from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin


class Provider(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "providers"
    __table_args__ = (
        UniqueConstraint("source_id", "source_record_id", name="uq_providers_source_record"),
    )

    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"), index=True)
    source_record_id: Mapped[str | None] = mapped_column(String(200), index=True)
    name: Mapped[str | None] = mapped_column(String(240))
    provider_type: Mapped[str] = mapped_column(String(80), index=True)
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(2), index=True)
    postal_code: Mapped[str | None] = mapped_column(String(20))
    # Nullable by design: some official provider sources have addresses but no coordinates.
    location = mapped_column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True))
    cms_rating: Mapped[float | None] = mapped_column(Float)
    accepts_medicare: Mapped[bool | None] = mapped_column(Boolean)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSONB)
