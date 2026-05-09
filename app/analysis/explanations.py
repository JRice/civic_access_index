from app.api.schemas import ScoreComponent, ScoreDriver, ScoreExplanation
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
        score_version=payload.get("score_version", "cai_v1"),
        methodology=payload.get("methodology"),
        component_scores=_component_scores(payload.get("component_scores", {})),
        missing_components=payload.get("missing_components", []),
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
        methodology="Scores have not been computed for this tract yet.",
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


def _component_scores(raw_components: dict) -> dict[str, ScoreComponent]:
    components: dict[str, ScoreComponent] = {}
    for name, value in raw_components.items():
        if isinstance(value, dict):
            components[name] = ScoreComponent(**value)
        else:
            components[name] = ScoreComponent(
                score=value,
                weight=0.0,
                status="available" if value is not None else "not_available",
                metric_count=0,
            )
    return components
