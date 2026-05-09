from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.schemas import AmenityRead, ProviderRead
from app.db.models.amenity import Amenity
from app.db.models.provider import Provider

router = APIRouter()
DB_DEPENDENCY = Depends(get_db)


@router.get("/amenities")
def list_amenities(
    category: str | None = None,
    type: str | None = None,
    state: str | None = None,
    city: str | None = None,
    radius_meters: int = Query(default=1609, ge=100, le=50000),
    bbox: str | None = None,
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = DB_DEPENDENCY,
) -> dict[str, object]:
    query = db.query(
        Amenity,
        func.ST_X(Amenity.location).label("longitude"),
        func.ST_Y(Amenity.location).label("latitude"),
    )
    if category:
        query = query.filter(
            or_(Amenity.normalized_category == category, Amenity.category == category)
        )
    if type:
        query = query.filter(Amenity.category == type)
    if state:
        query = query.filter(Amenity.state == state.upper())
    if city:
        query = query.filter(Amenity.city.ilike(f"%{city}%"))
    if q:
        query = query.filter(Amenity.name.ilike(f"%{q}%"))
    if bbox:
        minx, miny, maxx, maxy = _parse_bbox(bbox)
        query = query.filter(
            func.ST_Intersects(
                Amenity.location,
                func.ST_MakeEnvelope(minx, miny, maxx, maxy, 4326),
            )
        )

    rows = query.order_by(Amenity.name.asc().nullslast()).offset(offset).limit(limit).all()
    return {
        "category": category,
        "type": type,
        "state": state,
        "city": city,
        "bbox": bbox,
        "q": q,
        "limit": limit,
        "offset": offset,
        "results": [
            _amenity_read(amenity, longitude, latitude)
            for amenity, longitude, latitude in rows
        ],
    }


@router.get("/providers")
def list_providers(
    provider_type: str | None = None,
    state: str | None = None,
    county: str | None = None,
    city: str | None = None,
    radius_meters: int = Query(default=1609, ge=100, le=50000),
    bbox: str | None = None,
    q: str | None = None,
    mappable_only: bool = False,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = DB_DEPENDENCY,
) -> dict[str, object]:
    query = db.query(
        Provider,
        func.ST_X(Provider.location).label("longitude"),
        func.ST_Y(Provider.location).label("latitude"),
    )
    if provider_type:
        query = query.filter(Provider.provider_type.ilike(f"%{provider_type}%"))
    if state:
        query = query.filter(Provider.state == state.upper())
    if county:
        query = query.filter(Provider.raw_payload_json["county"].astext.ilike(f"%{county}%"))
    if city:
        query = query.filter(Provider.city.ilike(f"%{city}%"))
    if q:
        query = query.filter(Provider.name.ilike(f"%{q}%"))
    if mappable_only:
        query = query.filter(Provider.location.is_not(None))
    if bbox:
        minx, miny, maxx, maxy = _parse_bbox(bbox)
        query = query.filter(
            Provider.location.is_not(None),
            func.ST_Intersects(
                Provider.location,
                func.ST_MakeEnvelope(minx, miny, maxx, maxy, 4326),
            )
        )

    rows = query.order_by(Provider.name.asc().nullslast()).offset(offset).limit(limit).all()
    return {
        "provider_type": provider_type,
        "state": state,
        "county": county,
        "city": city,
        "bbox": bbox,
        "q": q,
        "mappable_only": mappable_only,
        "limit": limit,
        "offset": offset,
        "results": [
            _provider_read(provider, longitude, latitude) for provider, longitude, latitude in rows
        ],
    }


def _parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    try:
        minx, miny, maxx, maxy = [float(part.strip()) for part in bbox.split(",")]
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="bbox must be four comma-separated numbers: min_lon,min_lat,max_lon,max_lat",
        ) from exc
    if minx >= maxx or miny >= maxy:
        raise HTTPException(status_code=400, detail="bbox min values must be less than max values.")
    return minx, miny, maxx, maxy


def _amenity_read(amenity: Amenity, longitude: float | None, latitude: float | None) -> AmenityRead:
    return AmenityRead(
        id=amenity.id,
        source_record_id=amenity.source_record_id,
        name=amenity.name,
        category=amenity.category,
        normalized_category=amenity.normalized_category,
        address=amenity.address,
        city=amenity.city,
        state=amenity.state,
        postal_code=amenity.postal_code,
        longitude=longitude,
        latitude=latitude,
    )


def _provider_read(
    provider: Provider,
    longitude: float | None,
    latitude: float | None,
) -> ProviderRead:
    raw_payload = provider.raw_payload_json or {}
    is_mappable = longitude is not None and latitude is not None
    return ProviderRead(
        id=provider.id,
        source_record_id=provider.source_record_id,
        name=provider.name,
        provider_type=provider.provider_type,
        address=provider.address,
        city=provider.city,
        state=provider.state,
        postal_code=provider.postal_code,
        phone=raw_payload.get("phone"),
        cms_rating=provider.cms_rating,
        accepts_medicare=provider.accepts_medicare,
        longitude=longitude,
        latitude=latitude,
        is_mappable=is_mappable,
        mapping_status="mappable" if is_mappable else "not_mappable",
    )
