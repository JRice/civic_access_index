from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/amenities")
def list_amenities(
    category: str | None = None,
    near: str | None = None,
    radius_meters: int = Query(default=1609, ge=100, le=50000),
    bbox: str | None = None,
    q: str | None = None,
) -> dict[str, object]:
    return {
        "category": category,
        "near": near,
        "radius_meters": radius_meters,
        "bbox": bbox,
        "q": q,
        "results": [],
    }


@router.get("/providers")
def list_providers(
    provider_type: str | None = None,
    near: str | None = None,
    radius_meters: int = Query(default=1609, ge=100, le=50000),
    q: str | None = None,
) -> dict[str, object]:
    return {
        "provider_type": provider_type,
        "near": near,
        "radius_meters": radius_meters,
        "q": q,
        "results": [],
    }

