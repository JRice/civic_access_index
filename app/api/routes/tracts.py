from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analysis.explanations import build_placeholder_explanation, build_score_explanation
from app.analysis.metrics import ACCESS_METRIC_DEFINITIONS, VULNERABILITY_METRIC_DEFINITIONS
from app.api.dependencies import get_db
from app.api.schemas import ScoreExplanation, TractMetricRead, TractSummary
from app.db.models.access_metric import AccessMetric
from app.db.models.access_score import AccessScore
from app.db.models.census_tract import CensusTract

router = APIRouter()
DB_DEPENDENCY = Depends(get_db)
TRACT_SORT_COLUMNS = {
    "geoid": CensusTract.geoid,
    "civic_access_index": AccessScore.civic_access_index,
    "composite_score": AccessScore.composite_score,
    "vulnerability_score": AccessScore.vulnerability_score,
    "healthcare_access_score": AccessScore.healthcare_access_score,
    "food_access_score": AccessScore.food_access_score,
    "transit_access_score": AccessScore.transit_access_score,
}


@router.get("/tracts", response_model=list[TractSummary])
def list_tracts(
    bbox: str | None = None,
    state: str | None = None,
    county: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    sort: str = "civic_access_index",
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = DB_DEPENDENCY,
) -> list[TractSummary]:
    query = db.query(CensusTract).outerjoin(
        AccessScore,
        AccessScore.census_tract_id == CensusTract.id,
    )
    if state:
        query = query.filter(CensusTract.state_fips == state)
    if county:
        query = query.filter(CensusTract.county_fips == county)
    if min_score is not None:
        query = query.filter(AccessScore.civic_access_index >= min_score)
    if max_score is not None:
        query = query.filter(AccessScore.civic_access_index <= max_score)
    sort_desc = sort.startswith("-")
    sort_name = sort[1:] if sort_desc else sort
    sort_column = TRACT_SORT_COLUMNS.get(sort_name)
    if sort_column is None:
        raise HTTPException(status_code=400, detail=f"Unsupported tract sort: {sort}")
    order_expr = sort_column.desc().nullslast() if sort_desc else sort_column.asc().nullslast()
    tracts = query.order_by(order_expr, CensusTract.geoid.asc()).limit(limit).all()
    return [_tract_summary(tract) for tract in tracts]


@router.get("/tracts.geojson")
def list_tracts_geojson(
    state: str | None = "25",
    county: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    limit: int = Query(default=2000, ge=1, le=5000),
    db: Session = DB_DEPENDENCY,
) -> dict[str, object]:
    query = (
        db.query(CensusTract, AccessScore, func.ST_AsGeoJSON(CensusTract.geometry))
        .outerjoin(AccessScore, AccessScore.census_tract_id == CensusTract.id)
        .filter(CensusTract.geometry.is_not(None))
    )
    if state:
        query = query.filter(CensusTract.state_fips == state)
    if county:
        query = query.filter(CensusTract.county_fips == county)
    if min_score is not None:
        query = query.filter(AccessScore.civic_access_index >= min_score)
    if max_score is not None:
        query = query.filter(AccessScore.civic_access_index <= max_score)
    rows = query.order_by(CensusTract.geoid.asc()).limit(limit).all()
    return {
        "type": "FeatureCollection",
        "features": [
            _tract_feature(tract, score, geometry_json)
            for tract, score, geometry_json in rows
            if geometry_json is not None
        ],
    }


@router.get("/tracts/{geoid}", response_model=TractSummary)
def get_tract(geoid: str, db: Session = DB_DEPENDENCY) -> TractSummary:
    tract = db.query(CensusTract).filter(CensusTract.geoid == geoid).one_or_none()
    if tract is None:
        raise HTTPException(status_code=404, detail="Census tract not found.")
    return _tract_summary(tract)


@router.get("/tracts/{geoid}/metrics")
def get_tract_metrics(geoid: str, db: Session = DB_DEPENDENCY) -> dict[str, object]:
    tract = db.query(CensusTract).filter(CensusTract.geoid == geoid).one_or_none()
    if tract is None:
        raise HTTPException(status_code=404, detail="Census tract not found.")
    rows = (
        db.query(AccessMetric)
        .filter(AccessMetric.census_tract_id == tract.id)
        .order_by(AccessMetric.metric_name.asc())
        .all()
    )
    available = {row.metric_name: row for row in rows}
    expected_metric_names = sorted(
        set(ACCESS_METRIC_DEFINITIONS) | set(VULNERABILITY_METRIC_DEFINITIONS)
    )
    metrics = [
        _metric_read(metric_name, available.get(metric_name))
        for metric_name in expected_metric_names
    ]
    return {
        "tract_geoid": geoid,
        "tract_name": tract.name,
        "metrics": metrics,
        "caveats": [
            "CMS providers with null geometry are excluded from spatial proximity metrics.",
            "OSM healthcare amenities currently drive spatial healthcare-access metrics.",
            "Transit metrics are not_available until transit stop data is loaded.",
        ],
    }


@router.get("/tracts/{geoid}/explanation", response_model=ScoreExplanation)
def get_tract_explanation(geoid: str, db: Session = DB_DEPENDENCY) -> ScoreExplanation:
    tract = db.query(CensusTract).filter(CensusTract.geoid == geoid).one_or_none()
    if tract is None:
        raise HTTPException(status_code=404, detail="Census tract not found.")
    access_score = (
        db.query(AccessScore)
        .filter(AccessScore.census_tract_id == tract.id)
        .one_or_none()
    )
    if access_score is None:
        return build_placeholder_explanation(geoid)
    access_score.census_tract = tract
    return build_score_explanation(access_score)


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


def _tract_summary(tract: CensusTract) -> TractSummary:
    return TractSummary(
        geoid=tract.geoid,
        name=tract.name,
        state_fips=tract.state_fips,
        county_fips=tract.county_fips,
        population=tract.population,
        civic_access_index=tract.score.civic_access_index if tract.score else None,
        vulnerability_score=tract.score.vulnerability_score if tract.score else None,
    )


def _tract_feature(
    tract: CensusTract,
    score: AccessScore | None,
    geometry_json: str,
) -> dict[str, object]:
    import json

    return {
        "type": "Feature",
        "id": tract.geoid,
        "geometry": json.loads(geometry_json),
        "properties": {
            "geoid": tract.geoid,
            "name": tract.name,
            "state_fips": tract.state_fips,
            "county_fips": tract.county_fips,
            "population": tract.population,
            "civic_access_index": score.civic_access_index if score else None,
            "healthcare_access_score": score.healthcare_access_score if score else None,
            "food_access_score": score.food_access_score if score else None,
            "transit_access_score": score.transit_access_score if score else None,
            "vulnerability_score": score.vulnerability_score if score else None,
        },
    }


def _metric_read(metric_name: str, row: AccessMetric | None) -> TractMetricRead:
    definition = ACCESS_METRIC_DEFINITIONS.get(metric_name) or VULNERABILITY_METRIC_DEFINITIONS[
        metric_name
    ]
    if row is None:
        caveat = "Metric has not been computed or source data is not available."
        if metric_name.startswith("nearest_transit") or metric_name.startswith("transit_"):
            caveat = "Transit stop data has not been loaded; metric is not available."
        return TractMetricRead(
            metric_name=metric_name,
            metric_unit=definition["unit"],
            status="not_available",
            caveat=caveat,
        )
    return TractMetricRead(
        metric_name=row.metric_name,
        metric_value=row.metric_value,
        metric_unit=row.metric_unit,
        percentile_statewide=row.percentile_statewide,
        percentile_county=row.percentile_county,
        status="available",
    )
