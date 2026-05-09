from app.api.schemas import ScoreDriver, ScoreExplanation
from app.db.models.access_score import AccessScore

DEFAULT_LIMITATIONS = [
    "Amenity data may be incomplete where OpenStreetMap coverage is sparse.",
    "Distance calculations do not yet account for travel time or route networks.",
]


def build_score_explanation(access_score: AccessScore) -> ScoreExplanation:
    payload = access_score.explanation_json or {}
    return ScoreExplanation(
        tract_geoid=access_score.census_tract.geoid,
        composite_score=access_score.composite_score or 0.0,
        main_drivers=[
            ScoreDriver(
                metric=driver.get("metric", "unknown"),
                value=driver.get("value"),
                percentile=driver.get("percentile"),
                interpretation=driver.get("interpretation", ""),
            )
            for driver in payload.get("main_drivers", [])
        ],
        limitations=payload.get("limitations", DEFAULT_LIMITATIONS),
    )


def build_placeholder_explanation(tract_geoid: str) -> ScoreExplanation:
    return ScoreExplanation(
        tract_geoid=tract_geoid,
        composite_score=0.0,
        main_drivers=[
            ScoreDriver(
                metric="no_vehicle_household_rate",
                value=None,
                percentile=None,
                interpretation="Vehicle-access vulnerability will be computed from ACS fields.",
            )
        ],
        limitations=DEFAULT_LIMITATIONS,
    )
