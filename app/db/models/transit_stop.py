from geoalchemy2 import Geometry
from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin


class TransitStop(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "transit_stops"

    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"), index=True)
    stop_id: Mapped[str] = mapped_column(String(200), index=True)
    agency: Mapped[str | None] = mapped_column(String(160), index=True)
    name: Mapped[str | None] = mapped_column(String(240))
    location = mapped_column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True))
    route_count: Mapped[int | None] = mapped_column(Integer)
    service_frequency_score: Mapped[float | None] = mapped_column(Float)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSONB)

