from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.access_metric import AccessMetric
from app.db.models.access_score import AccessScore
from app.db.models.census_tract import CensusTract

SCORE_WEIGHTS = {
    "healthcare_gap_score": 0.35,
    "food_gap_score": 0.25,
    "transit_gap_score": 0.20,
    "socioeconomic_vulnerability_score": 0.20,
}
SCORE_VERSION = "cai_v1"
SCORE_METHODOLOGY = (
    "Weighted average of Massachusetts-relative gap percentiles; weights are renormalized "
    "across available components when a source category is not available."
)

HEALTHCARE_SCORE_METRICS = (
    "nearest_healthcare_amenity_distance_m",
    "healthcare_amenities_within_1mi",
    "healthcare_amenities_within_2mi",
    "nearest_pharmacy_distance_m",
)
FOOD_SCORE_METRICS = (
    "nearest_food_access_distance_m",
    "food_access_amenities_within_1mi",
    "food_access_amenities_within_2mi",
)
TRANSIT_SCORE_METRICS = (
    "nearest_transit_stop_distance_m",
    "transit_stops_within_half_mi",
)
VULNERABILITY_SCORE_METRICS = (
    "vulnerability_poverty_rate",
    "vulnerability_no_vehicle_household_rate",
    "vulnerability_age_65_plus_rate",
    "vulnerability_disability_rate",
    "vulnerability_median_household_income",
)

SCORE_COMPONENT_METRICS = {
    "healthcare_access_score": HEALTHCARE_SCORE_METRICS,
    "food_access_score": FOOD_SCORE_METRICS,
    "transit_access_score": TRANSIT_SCORE_METRICS,
    "vulnerability_score": VULNERABILITY_SCORE_METRICS,
}
SCORE_COMPONENT_WEIGHTS = {
    "healthcare_access_score": SCORE_WEIGHTS["healthcare_gap_score"],
    "food_access_score": SCORE_WEIGHTS["food_gap_score"],
    "transit_access_score": SCORE_WEIGHTS["transit_gap_score"],
    "vulnerability_score": SCORE_WEIGHTS["socioeconomic_vulnerability_score"],
}


def compute_civic_access_index(
    healthcare_gap_score: float,
    food_gap_score: float,
    transit_gap_score: float,
    socioeconomic_vulnerability_score: float,
) -> float:
    weighted = (
        SCORE_WEIGHTS["healthcare_gap_score"] * healthcare_gap_score
        + SCORE_WEIGHTS["food_gap_score"] * food_gap_score
        + SCORE_WEIGHTS["transit_gap_score"] * transit_gap_score
        + SCORE_WEIGHTS["socioeconomic_vulnerability_score"] * socioeconomic_vulnerability_score
    )
    return round(weighted, 2)


def mean_available_percentile(metrics: list[AccessMetric]) -> float | None:
    values = [
        metric.percentile_statewide
        for metric in metrics
        if metric.percentile_statewide is not None
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def recompute_access_scores(db: Session) -> dict[str, Any]:
    tracts = db.query(CensusTract).filter(CensusTract.state_fips == "25").all()
    metrics_by_tract = _metrics_by_tract(db)
    scores_written = 0
    scores_skipped = 0

    for tract in tracts:
        tract_metrics = metrics_by_tract.get(tract.id, {})
        healthcare_score = _component_score(tract_metrics, HEALTHCARE_SCORE_METRICS)
        food_score = _component_score(tract_metrics, FOOD_SCORE_METRICS)
        transit_score = _component_score(tract_metrics, TRANSIT_SCORE_METRICS)
        vulnerability_score = _component_score(tract_metrics, VULNERABILITY_SCORE_METRICS)

        composite_score = _weighted_composite(
            healthcare_score=healthcare_score,
            food_score=food_score,
            transit_score=transit_score,
            vulnerability_score=vulnerability_score,
        )
        if all(
            value is None
            for value in (healthcare_score, food_score, transit_score, vulnerability_score)
        ):
            scores_skipped += 1
            continue

        access_score = (
            db.query(AccessScore)
            .filter(AccessScore.census_tract_id == tract.id)
            .one_or_none()
        )
        if access_score is None:
            access_score = AccessScore(census_tract_id=tract.id)
        access_score.healthcare_access_score = healthcare_score
        access_score.food_access_score = food_score
        access_score.transit_access_score = transit_score
        access_score.vulnerability_score = vulnerability_score
        access_score.civic_access_index = composite_score
        access_score.composite_score = composite_score
        access_score.explanation_json = build_score_explanation_payload(
            tract=tract,
            metrics=list(tract_metrics.values()),
            composite_score=composite_score,
            component_scores={
                "healthcare_access_score": healthcare_score,
                "food_access_score": food_score,
                "transit_access_score": transit_score,
                "vulnerability_score": vulnerability_score,
            },
            component_metric_counts={
                component_name: _available_metric_count(tract_metrics, metric_names)
                for component_name, metric_names in SCORE_COMPONENT_METRICS.items()
            },
        )
        access_score.computed_at = datetime.now(UTC)
        db.add(access_score)
        scores_written += 1

    db.commit()
    return {
        "scores_written": scores_written,
        "scores_skipped": scores_skipped,
        "score_components": SCORE_COMPONENT_METRICS,
        "score_weights": SCORE_COMPONENT_WEIGHTS,
        "score_version": SCORE_VERSION,
    }


def build_score_explanation_payload(
    *,
    tract: CensusTract,
    metrics: list[AccessMetric],
    composite_score: float | None,
    component_scores: dict[str, float | None],
    component_metric_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    component_metric_counts = component_metric_counts or {}
    component_payload = {
        component_name: {
            "score": score,
            "weight": SCORE_COMPONENT_WEIGHTS[component_name],
            "status": "available" if score is not None else "not_available",
            "metric_count": component_metric_counts.get(component_name, 0),
        }
        for component_name, score in component_scores.items()
    }
    missing_components = [
        component_name
        for component_name, component in component_payload.items()
        if component["status"] != "available"
    ]
    drivers = [
        {
            "metric": metric.metric_name,
            "value": metric.metric_value,
            "percentile": metric.percentile_statewide,
            "interpretation": _driver_interpretation(metric),
        }
        for metric in sorted(
            metrics,
            key=lambda metric: metric.percentile_statewide or -1,
            reverse=True,
        )
        if metric.percentile_statewide is not None
    ][:5]
    return {
        "tract_geoid": tract.geoid,
        "composite_score": composite_score,
        "score_version": SCORE_VERSION,
        "methodology": SCORE_METHODOLOGY,
        "component_scores": component_payload,
        "missing_components": missing_components,
        "main_drivers": drivers,
        "limitations": _limitations(component_scores, missing_components),
    }


def _metrics_by_tract(db: Session) -> dict[str, dict[str, AccessMetric]]:
    metrics = db.query(AccessMetric).all()
    grouped: dict[str, dict[str, AccessMetric]] = {}
    for metric in metrics:
        grouped.setdefault(metric.census_tract_id, {})[metric.metric_name] = metric
    return grouped


def _component_score(
    tract_metrics: dict[str, AccessMetric],
    metric_names: tuple[str, ...],
) -> float | None:
    return mean_available_percentile(
        [tract_metrics[metric_name] for metric_name in metric_names if metric_name in tract_metrics]
    )


def _available_metric_count(
    tract_metrics: dict[str, AccessMetric],
    metric_names: tuple[str, ...],
) -> int:
    return sum(
        1
        for metric_name in metric_names
        if metric_name in tract_metrics
        and tract_metrics[metric_name].percentile_statewide is not None
    )


def _weighted_composite(
    *,
    healthcare_score: float | None,
    food_score: float | None,
    transit_score: float | None,
    vulnerability_score: float | None,
) -> float | None:
    available = {
        "healthcare_gap_score": healthcare_score,
        "food_gap_score": food_score,
        "transit_gap_score": transit_score,
        "socioeconomic_vulnerability_score": vulnerability_score,
    }
    weight_total = sum(
        SCORE_WEIGHTS[name] for name, value in available.items() if value is not None
    )
    if weight_total == 0:
        return None
    weighted = sum(
        SCORE_WEIGHTS[name] * value
        for name, value in available.items()
        if value is not None
    )
    return round(weighted / weight_total, 2)


def _driver_interpretation(metric: AccessMetric) -> str:
    if metric.metric_name.endswith("_distance_m"):
        return "Longer distance indicates a larger access gap."
    if "within" in metric.metric_name:
        return "Lower nearby amenity count indicates a larger access gap."
    if metric.metric_name == "vulnerability_median_household_income":
        return "Lower median income raises socioeconomic vulnerability."
    return "Higher percentile indicates higher relative vulnerability or access gap."


def _limitations(
    component_scores: dict[str, float | None],
    missing_components: list[str] | None = None,
) -> list[str]:
    limitations = [
        "Amenity data may be incomplete where OpenStreetMap coverage is sparse.",
        "Distance calculations do not yet account for travel time or route networks.",
        "CMS providers with null geometry are excluded from spatial proximity metrics.",
    ]
    if component_scores.get("transit_access_score") is None:
        limitations.append("Transit score is unavailable until mapped transit stop data is loaded.")
    if missing_components:
        limitations.append(
            "Composite score weights were renormalized across available components."
        )
    return limitations
