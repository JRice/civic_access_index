from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/scores/top")
def top_scores(
    score_type: str = "civic_access_index",
    state: str | None = None,
    county: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, object]:
    return {"score_type": score_type, "state": state, "county": county, "limit": limit, "results": []}


@router.get("/scores/distribution")
def score_distribution(
    score_type: str = "civic_access_index",
    state: str | None = None,
    county: str | None = None,
) -> dict[str, object]:
    return {"score_type": score_type, "state": state, "county": county, "buckets": []}

