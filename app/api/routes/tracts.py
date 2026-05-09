from fastapi import APIRouter, Query

from app.analysis.explanations import build_placeholder_explanation
from app.api.schemas import ScoreExplanation, TractSummary

router = APIRouter()


@router.get("/tracts", response_model=list[TractSummary])
def list_tracts(
    bbox: str | None = None,
    state: str | None = None,
    county: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    sort: str = "civic_access_index",
    limit: int = Query(default=50, ge=1, le=500),
) -> list[TractSummary]:
    return []


@router.get("/tracts/{geoid}", response_model=TractSummary)
def get_tract(geoid: str) -> TractSummary:
    return TractSummary(geoid=geoid, name=None, state_fips=geoid[:2], county_fips=geoid[2:5])


@router.get("/tracts/{geoid}/metrics")
def get_tract_metrics(geoid: str) -> dict[str, object]:
    return {"tract_geoid": geoid, "metrics": []}


@router.get("/tracts/{geoid}/explanation", response_model=ScoreExplanation)
def get_tract_explanation(geoid: str) -> ScoreExplanation:
    return build_placeholder_explanation(geoid)


@router.get("/tracts/{geoid}/nearby-amenities")
def get_nearby_amenities(
    geoid: str,
    category: str | None = None,
    radius_meters: int = Query(default=1609, ge=100, le=50000),
) -> dict[str, object]:
    return {
        "tract_geoid": geoid,
        "category": category,
        "radius_meters": radius_meters,
        "amenities": [],
    }
