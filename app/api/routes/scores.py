from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analysis.metrics import ACCESS_METRIC_DEFINITIONS, VULNERABILITY_METRIC_DEFINITIONS
from app.api.dependencies import get_db
from app.api.schemas import ScoreDistributionBucket, ScoreTopResult
from app.db.models.access_metric import AccessMetric
from app.db.models.access_score import AccessScore
from app.db.models.census_tract import CensusTract

router = APIRouter()
DB_DEPENDENCY = Depends(get_db)
DEFAULT_SCORE_METRIC = "civic_access_index"
SCORE_COLUMNS = {
    "civic_access_index": AccessScore.civic_access_index,
    "composite_score": AccessScore.composite_score,
    "healthcare_access_score": AccessScore.healthcare_access_score,
    "food_access_score": AccessScore.food_access_score,
    "transit_access_score": AccessScore.transit_access_score,
    "vulnerability_score": AccessScore.vulnerability_score,
}


@router.get("/scores/top")
def top_scores(
    score_type: str = DEFAULT_SCORE_METRIC,
    state: str | None = None,
    county: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = DB_DEPENDENCY,
) -> dict[str, object]:
    if score_type in SCORE_COLUMNS:
        return _top_access_scores(score_type, state, county, limit, db)
    metric_name = _resolve_metric_name(score_type)
    query = (
        db.query(AccessMetric, CensusTract)
        .join(CensusTract, AccessMetric.census_tract_id == CensusTract.id)
        .filter(AccessMetric.metric_name == metric_name)
    )
    if state:
        query = query.filter(CensusTract.state_fips == state)
    if county:
        query = query.filter(CensusTract.county_fips == county)
    rows = (
        query.order_by(AccessMetric.percentile_statewide.desc().nullslast())
        .limit(limit)
        .all()
    )
    return {
        "score_type": metric_name,
        "state": state,
        "county": county,
        "limit": limit,
        "results": [
            ScoreTopResult(
                geoid=tract.geoid,
                tract_name=tract.name,
                county_fips=tract.county_fips,
                metric_name=metric.metric_name,
                metric_value=metric.metric_value,
                metric_unit=metric.metric_unit,
                percentile_statewide=metric.percentile_statewide,
            )
            for metric, tract in rows
        ],
    }


@router.get("/scores/distribution")
def score_distribution(
    score_type: str = DEFAULT_SCORE_METRIC,
    state: str | None = None,
    county: str | None = None,
    db: Session = DB_DEPENDENCY,
) -> dict[str, object]:
    if score_type in SCORE_COLUMNS:
        values = _score_values(score_type, state, county, db)
        return _distribution_response(score_type, state, county, values)
    metric_name = _resolve_metric_name(score_type)
    query = (
        db.query(AccessMetric.percentile_statewide)
        .join(CensusTract, AccessMetric.census_tract_id == CensusTract.id)
        .filter(
            AccessMetric.metric_name == metric_name,
            AccessMetric.percentile_statewide.is_not(None),
        )
    )
    if state:
        query = query.filter(CensusTract.state_fips == state)
    if county:
        query = query.filter(CensusTract.county_fips == county)
    values = [float(row[0]) for row in query.all()]
    return _distribution_response(metric_name, state, county, values)


def _top_access_scores(
    score_type: str,
    state: str | None,
    county: str | None,
    limit: int,
    db: Session,
) -> dict[str, object]:
    score_column = SCORE_COLUMNS[score_type]
    query = (
        db.query(AccessScore, CensusTract)
        .join(CensusTract, AccessScore.census_tract_id == CensusTract.id)
        .filter(score_column.is_not(None))
    )
    if state:
        query = query.filter(CensusTract.state_fips == state)
    if county:
        query = query.filter(CensusTract.county_fips == county)
    rows = query.order_by(score_column.desc()).limit(limit).all()
    return {
        "score_type": score_type,
        "state": state,
        "county": county,
        "limit": limit,
        "results": [
            ScoreTopResult(
                geoid=tract.geoid,
                tract_name=tract.name,
                county_fips=tract.county_fips,
                metric_name=score_type,
                metric_value=getattr(score, score_type),
                metric_unit="score",
                percentile_statewide=getattr(score, score_type),
                healthcare_access_score=score.healthcare_access_score,
                food_access_score=score.food_access_score,
                transit_access_score=score.transit_access_score,
                vulnerability_score=score.vulnerability_score,
            )
            for score, tract in rows
        ],
    }


def _score_values(
    score_type: str,
    state: str | None,
    county: str | None,
    db: Session,
) -> list[float]:
    score_column = SCORE_COLUMNS[score_type]
    query = (
        db.query(score_column)
        .join(CensusTract, AccessScore.census_tract_id == CensusTract.id)
        .filter(score_column.is_not(None))
    )
    if state:
        query = query.filter(CensusTract.state_fips == state)
    if county:
        query = query.filter(CensusTract.county_fips == county)
    return [float(row[0]) for row in query.all()]


def _distribution_response(
    score_type: str,
    state: str | None,
    county: str | None,
    values: list[float],
) -> dict[str, object]:
    buckets = [
        ScoreDistributionBucket(bucket_min=start, bucket_max=start + 20, count=0)
        for start in range(0, 100, 20)
    ]
    for value in values:
        index = min(int(value // 20), 4)
        buckets[index].count += 1
    return {
        "score_type": score_type,
        "state": state,
        "county": county,
        "count": len(values),
        "buckets": buckets,
    }


def _resolve_metric_name(score_type: str) -> str:
    if score_type in ACCESS_METRIC_DEFINITIONS or score_type in VULNERABILITY_METRIC_DEFINITIONS:
        return score_type
    raise HTTPException(
        status_code=400,
        detail=f"Unknown metric score_type {score_type!r}; use a computed access metric name.",
    )
