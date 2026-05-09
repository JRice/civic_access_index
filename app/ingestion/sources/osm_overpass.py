import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy.orm import Session

from app.db.models.amenity import Amenity
from app.db.models.data_source import DataSource
from app.db.session import SessionLocal
from app.ingestion.base import IngestionResult, SourceAdapter
from app.logging import get_logger

LOGGER = get_logger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
REQUEST_TIMEOUT_SECONDS = 180.0
MAX_ATTEMPTS = 3

OSM_AMENITIES = (
    "hospital",
    "clinic",
    "doctors",
    "dentist",
    "pharmacy",
    "food_bank",
    "library",
    "community_centre",
    "social_facility",
)
OSM_SHOPS = ("supermarket", "grocery", "convenience")
OVERPASS_QUERY = f"""
[out:json][timeout:180];
area["ISO3166-2"="US-MA"][admin_level=4]->.searchArea;
(
  node["amenity"~"^({'|'.join(OSM_AMENITIES)})$"](area.searchArea);
  way["amenity"~"^({'|'.join(OSM_AMENITIES)})$"](area.searchArea);
  relation["amenity"~"^({'|'.join(OSM_AMENITIES)})$"](area.searchArea);
  node["shop"~"^({'|'.join(OSM_SHOPS)})$"](area.searchArea);
  way["shop"~"^({'|'.join(OSM_SHOPS)})$"](area.searchArea);
  relation["shop"~"^({'|'.join(OSM_SHOPS)})$"](area.searchArea);
);
out tags center;
"""


def normalize_osm_element(element: dict[str, Any]) -> dict[str, Any]:
    element_type = element.get("type")
    element_id = element.get("id")
    tags = element.get("tags") or {}
    lon = element.get("lon") or (element.get("center") or {}).get("lon")
    lat = element.get("lat") or (element.get("center") or {}).get("lat")
    amenity_type = tags.get("amenity") or tags.get("shop")

    if element_type not in {"node", "way", "relation"} or element_id is None:
        raise ValueError("OSM element is missing stable type/id.")
    if amenity_type is None:
        raise ValueError(f"OSM element {element_type}/{element_id} has no amenity or shop tag.")
    if lon is None or lat is None:
        raise ValueError(
            f"OSM element {element_type}/{element_id} has no point or center coordinate."
        )

    longitude = float(lon)
    latitude = float(lat)
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        raise ValueError(f"OSM element {element_type}/{element_id} has invalid coordinates.")

    return {
        "source_record_id": f"osm:{element_type}/{element_id}",
        "name": tags.get("name"),
        "category": amenity_type,
        "normalized_category": _normalize_category(tags),
        "address": _format_address(tags),
        "city": tags.get("addr:city"),
        "state": (tags.get("addr:state") or "MA")[:2].upper(),
        "postal_code": tags.get("addr:postcode"),
        "longitude": longitude,
        "latitude": latitude,
        "raw_payload_json": {
            "osm_type": element_type,
            "osm_id": element_id,
            "tags": tags,
        },
    }


def _normalize_category(tags: dict[str, Any]) -> str:
    value = tags.get("amenity") or tags.get("shop")
    if value in {"hospital", "clinic", "doctors", "dentist", "pharmacy"}:
        return "healthcare"
    if value in {"supermarket", "grocery", "convenience", "food_bank"}:
        return "food_access"
    return "civic_service"


def _format_address(tags: dict[str, Any]) -> str | None:
    house_number = tags.get("addr:housenumber")
    street = tags.get("addr:street")
    if house_number and street:
        return f"{house_number} {street}"
    return street or tags.get("addr:full")


def _upsert_amenity(db: Session, source: DataSource, parsed: dict[str, Any]) -> bool:
    amenity = (
        db.query(Amenity)
        .filter(
            Amenity.source_id == source.id,
            Amenity.source_record_id == parsed["source_record_id"],
        )
        .one_or_none()
    )
    created = amenity is None
    if amenity is None:
        amenity = Amenity(
            source_id=source.id,
            source_record_id=parsed["source_record_id"],
        )

    amenity.name = parsed["name"]
    amenity.category = parsed["category"]
    amenity.normalized_category = parsed["normalized_category"]
    amenity.address = parsed["address"]
    amenity.city = parsed["city"]
    amenity.state = parsed["state"]
    amenity.postal_code = parsed["postal_code"]
    amenity.location = from_shape(Point(parsed["longitude"], parsed["latitude"]), srid=4326)
    amenity.raw_payload_json = parsed["raw_payload_json"]
    amenity.confidence_score = 1.0
    amenity.last_seen_at = datetime.now(UTC)
    db.add(amenity)
    return created


class OSMOverpassAdapter(SourceAdapter):
    name = "osm_overpass"
    source_type = "amenity"
    homepage_url = "https://www.openstreetmap.org"
    api_url = OVERPASS_URL
    license = "OpenStreetMap data is available under the Open Database License"
    refresh_strategy = "manual or scheduled refresh with Overpass courtesy limits"

    async def fetch(self) -> list[dict[str, Any]]:
        LOGGER.info("osm_overpass_fetch_started", url=OVERPASS_URL)
        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                    response = await client.post(OVERPASS_URL, data={"data": OVERPASS_QUERY})
                    response.raise_for_status()
                    payload = response.json()
                records = payload.get("elements", [])
                LOGGER.info("osm_overpass_fetch_completed", records=len(records), attempt=attempt)
                return records
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code not in {429, 500, 502, 503, 504}:
                    raise
            except httpx.HTTPError as exc:
                last_error = exc
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(2**attempt)

        raise RuntimeError(f"Overpass request failed after {MAX_ATTEMPTS} attempts: {last_error}")

    async def normalize(self, records: list[dict[str, Any]]) -> IngestionResult:
        created = 0
        updated = 0
        rejected = 0

        with SessionLocal() as db:
            source = db.query(DataSource).filter(DataSource.name == self.name).one()
            for record in records:
                try:
                    parsed = normalize_osm_element(record)
                    if _upsert_amenity(db, source, parsed):
                        created += 1
                    else:
                        updated += 1
                except Exception as exc:
                    rejected += 1
                    LOGGER.warning(
                        "osm_overpass_record_rejected",
                        error=str(exc),
                        osm_type=record.get("type"),
                        osm_id=record.get("id"),
                    )
            db.commit()

        return IngestionResult(
            records_seen=len(records),
            records_created=created,
            records_updated=updated,
            records_rejected=rejected,
            metadata={
                "state": "MA",
                "amenities": OSM_AMENITIES,
                "shops": OSM_SHOPS,
                "note": "Ways and relations use Overpass center coordinates.",
            },
        )
