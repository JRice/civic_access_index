from app.api.schemas import ScoreDriver, ScoreExplanation


DEFAULT_LIMITATIONS = [
    "Amenity data may be incomplete where OpenStreetMap coverage is sparse.",
    "Distance calculations do not yet account for travel time or route networks.",
]


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

