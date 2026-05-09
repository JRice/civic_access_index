from geoalchemy2 import Geometry
from sqlalchemy import Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import UUIDPrimaryKeyMixin


class CensusTract(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "census_tracts"

    geoid: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    state_fips: Mapped[str] = mapped_column(String(2), index=True)
    county_fips: Mapped[str] = mapped_column(String(3), index=True)
    tract_code: Mapped[str] = mapped_column(String(12))
    name: Mapped[str | None] = mapped_column(String(200))
    population: Mapped[int | None] = mapped_column(Integer)
    median_income: Mapped[int | None] = mapped_column(Integer)
    poverty_rate: Mapped[float | None] = mapped_column(Float)
    no_vehicle_household_rate: Mapped[float | None] = mapped_column(Float)
    elderly_rate: Mapped[float | None] = mapped_column(Float)
    disability_rate: Mapped[float | None] = mapped_column(Float)
    limited_english_rate: Mapped[float | None] = mapped_column(Float)
    geometry = mapped_column(Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True))
    centroid = mapped_column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True))
    properties_json: Mapped[dict | None] = mapped_column(JSONB)

    metrics = relationship("AccessMetric", back_populates="census_tract")
    score = relationship("AccessScore", back_populates="census_tract", uselist=False)

