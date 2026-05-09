from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import ZipFile

import geopandas as gpd
import httpx
from geoalchemy2.shape import from_shape
from shapely import from_wkt
from shapely.geometry import MultiPolygon, Polygon
from sqlalchemy.orm import Session

from app.db.models.census_tract import CensusTract
from app.db.session import SessionLocal
from app.ingestion.base import IngestionResult, SourceAdapter
from app.logging import get_logger

LOGGER = get_logger(__name__)

MASSACHUSETTS_STATE_FIPS = "25"
TIGER_YEAR = "2024"
TIGER_TRACT_URL = (
    f"https://www2.census.gov/geo/tiger/TIGER{TIGER_YEAR}/TRACT/"
    f"tl_{TIGER_YEAR}_{MASSACHUSETTS_STATE_FIPS}_tract.zip"
)
REQUEST_TIMEOUT_SECONDS = 60.0


def parse_tiger_tract_record(record: dict[str, Any]) -> dict[str, Any]:
    geoid = str(record.get("GEOID") or "").strip()
    state_fips = str(record.get("STATEFP") or geoid[:2]).strip()
    county_fips = str(record.get("COUNTYFP") or geoid[2:5]).strip()
    tract_code = str(record.get("TRACTCE") or geoid[5:]).strip()
    geometry_wkt = record.get("geometry_wkt")

    if len(geoid) != 11 or state_fips != MASSACHUSETTS_STATE_FIPS:
        raise ValueError(f"Invalid Massachusetts tract GEOID: {geoid!r}")
    if not county_fips or not tract_code or not geometry_wkt:
        raise ValueError(f"Incomplete TIGER tract record for GEOID {geoid!r}")

    geometry = from_wkt(str(geometry_wkt))
    if isinstance(geometry, Polygon):
        geometry = MultiPolygon([geometry])
    if not isinstance(geometry, MultiPolygon) or geometry.is_empty:
        raise ValueError(f"Invalid tract geometry for GEOID {geoid!r}")

    return {
        "geoid": geoid,
        "state_fips": state_fips,
        "county_fips": county_fips,
        "tract_code": tract_code,
        "name": record.get("NAMELSAD") or record.get("NAME"),
        "aland": _parse_int(record.get("ALAND")),
        "awater": _parse_int(record.get("AWATER")),
        "geometry": geometry,
    }


def _parse_int(value: Any) -> int | None:
    if value in (None, "", "null"):
        return None
    return int(value)


def _upsert_tiger_record(db: Session, parsed: dict[str, Any]) -> bool:
    tract = db.query(CensusTract).filter(CensusTract.geoid == parsed["geoid"]).one_or_none()
    created = tract is None
    if tract is None:
        tract = CensusTract(geoid=parsed["geoid"])

    geometry = parsed["geometry"]
    tract.state_fips = parsed["state_fips"]
    tract.county_fips = parsed["county_fips"]
    tract.tract_code = parsed["tract_code"]
    tract.name = parsed["name"]
    tract.geometry = from_shape(geometry, srid=4326)
    tract.centroid = from_shape(geometry.centroid, srid=4326)
    tract.properties_json = {
        **(tract.properties_json or {}),
        "aland": parsed["aland"],
        "awater": parsed["awater"],
        "tiger_year": TIGER_YEAR,
    }
    db.add(tract)
    return created


class CensusTigerAdapter(SourceAdapter):
    name = "census_tiger"
    source_type = "census-geography"
    homepage_url = "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html"
    api_url = TIGER_TRACT_URL
    license = "U.S. Census Bureau public data"
    refresh_strategy = "annual"

    async def fetch(self) -> list[dict[str, Any]]:
        LOGGER.info("census_tiger_fetch_started", url=TIGER_TRACT_URL)
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            response = await client.get(TIGER_TRACT_URL)
            response.raise_for_status()

        with TemporaryDirectory() as temp_dir:
            with ZipFile(BytesIO(response.content)) as archive:
                archive.extractall(temp_dir)
            shapefile = next(Path(temp_dir).glob("*.shp"))
            frame = gpd.read_file(shapefile).to_crs(epsg=4326)

        records: list[dict[str, Any]] = []
        for raw in frame.to_dict("records"):
            geometry = raw.pop("geometry", None)
            if geometry is not None:
                raw["geometry_wkt"] = geometry.wkt
            records.append(raw)

        LOGGER.info("census_tiger_fetch_completed", records=len(records))
        return records

    async def normalize(self, records: list[dict[str, Any]]) -> IngestionResult:
        created = 0
        updated = 0
        rejected = 0

        with SessionLocal() as db:
            for record in records:
                try:
                    parsed = parse_tiger_tract_record(record)
                    if _upsert_tiger_record(db, parsed):
                        created += 1
                    else:
                        updated += 1
                except Exception as exc:
                    rejected += 1
                    LOGGER.warning(
                        "census_tiger_record_rejected",
                        error=str(exc),
                        geoid=record.get("GEOID"),
                    )
            db.commit()

        return IngestionResult(
            records_seen=len(records),
            records_created=created,
            records_updated=updated,
            records_rejected=rejected,
            metadata={"state_fips": MASSACHUSETTS_STATE_FIPS, "tiger_year": TIGER_YEAR},
        )
