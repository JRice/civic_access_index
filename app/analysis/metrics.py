"""Metric computation entry points."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import RowMapping, func, text
from sqlalchemy.orm import Session

from app.analysis.percentiles import percentile_map
from app.analysis.scoring import recompute_access_scores
from app.db.models.access_metric import AccessMetric
from app.db.models.census_tract import CensusTract
from app.db.models.transit_stop import TransitStop
from app.logging import get_logger

LOGGER = get_logger(__name__)

MASSACHUSETTS_STATE_FIPS = "25"
ONE_MILE_METERS = 1609.34
TWO_MILES_METERS = 3218.69
HALF_MILE_METERS = 804.67

ACCESS_METRIC_DEFINITIONS: dict[str, dict[str, Any]] = {
    "nearest_healthcare_amenity_distance_m": {
        "unit": "meters",
        "higher_percentile_is_more_gap": True,
        "category": "healthcare_access",
    },
    "healthcare_amenities_within_1mi": {
        "unit": "count",
        "higher_percentile_is_more_gap": False,
        "category": "healthcare_access",
    },
    "healthcare_amenities_within_2mi": {
        "unit": "count",
        "higher_percentile_is_more_gap": False,
        "category": "healthcare_access",
    },
    "nearest_pharmacy_distance_m": {
        "unit": "meters",
        "higher_percentile_is_more_gap": True,
        "category": "healthcare_access",
    },
    "nearest_food_access_distance_m": {
        "unit": "meters",
        "higher_percentile_is_more_gap": True,
        "category": "food_access",
    },
    "food_access_amenities_within_1mi": {
        "unit": "count",
        "higher_percentile_is_more_gap": False,
        "category": "food_access",
    },
    "food_access_amenities_within_2mi": {
        "unit": "count",
        "higher_percentile_is_more_gap": False,
        "category": "food_access",
    },
    "nearest_transit_stop_distance_m": {
        "unit": "meters",
        "higher_percentile_is_more_gap": True,
        "category": "transit_access",
    },
    "transit_stops_within_half_mi": {
        "unit": "count",
        "higher_percentile_is_more_gap": False,
        "category": "transit_access",
    },
}

VULNERABILITY_METRIC_DEFINITIONS: dict[str, dict[str, Any]] = {
    "vulnerability_poverty_rate": {
        "source_column": "poverty_rate",
        "unit": "rate",
        "higher_percentile_is_more_gap": True,
    },
    "vulnerability_no_vehicle_household_rate": {
        "source_column": "no_vehicle_household_rate",
        "unit": "rate",
        "higher_percentile_is_more_gap": True,
    },
    "vulnerability_age_65_plus_rate": {
        "source_column": "elderly_rate",
        "unit": "rate",
        "higher_percentile_is_more_gap": True,
    },
    "vulnerability_disability_rate": {
        "source_column": "disability_rate",
        "unit": "rate",
        "higher_percentile_is_more_gap": True,
    },
    "vulnerability_median_household_income": {
        "source_column": "median_income",
        "unit": "dollars",
        "higher_percentile_is_more_gap": False,
    },
}

SPATIAL_ACCESS_SQL = text(
    """
    WITH tract_points AS (
        SELECT id, geoid, ST_PointOnSurface(geometry) AS point
        FROM census_tracts
        WHERE state_fips = :state_fips
          AND geometry IS NOT NULL
    ),
    mapped_healthcare AS (
        SELECT location
        FROM amenities
        WHERE location IS NOT NULL
          AND normalized_category = 'healthcare'
    ),
    mapped_pharmacies AS (
        SELECT location
        FROM amenities
        WHERE location IS NOT NULL
          AND category = 'pharmacy'
    ),
    mapped_food AS (
        SELECT location
        FROM amenities
        WHERE location IS NOT NULL
          AND normalized_category = 'food_access'
    ),
    mapped_transit AS (
        SELECT location
        FROM transit_stops
        WHERE location IS NOT NULL
    )
    SELECT
        tract_points.id AS census_tract_id,
        tract_points.geoid AS geoid,
        (
            SELECT ST_Distance(tract_points.point::geography, location::geography)
            FROM mapped_healthcare
            ORDER BY tract_points.point <-> location
            LIMIT 1
        ) AS nearest_healthcare_amenity_distance_m,
        (
            SELECT COUNT(*)
            FROM mapped_healthcare
            WHERE ST_DWithin(tract_points.point::geography, location::geography, :one_mile_m)
        ) AS healthcare_amenities_within_1mi,
        (
            SELECT COUNT(*)
            FROM mapped_healthcare
            WHERE ST_DWithin(tract_points.point::geography, location::geography, :two_miles_m)
        ) AS healthcare_amenities_within_2mi,
        (
            SELECT ST_Distance(tract_points.point::geography, location::geography)
            FROM mapped_pharmacies
            ORDER BY tract_points.point <-> location
            LIMIT 1
        ) AS nearest_pharmacy_distance_m,
        (
            SELECT ST_Distance(tract_points.point::geography, location::geography)
            FROM mapped_food
            ORDER BY tract_points.point <-> location
            LIMIT 1
        ) AS nearest_food_access_distance_m,
        (
            SELECT COUNT(*)
            FROM mapped_food
            WHERE ST_DWithin(tract_points.point::geography, location::geography, :one_mile_m)
        ) AS food_access_amenities_within_1mi,
        (
            SELECT COUNT(*)
            FROM mapped_food
            WHERE ST_DWithin(tract_points.point::geography, location::geography, :two_miles_m)
        ) AS food_access_amenities_within_2mi,
        (
            SELECT ST_Distance(tract_points.point::geography, location::geography)
            FROM mapped_transit
            ORDER BY tract_points.point <-> location
            LIMIT 1
        ) AS nearest_transit_stop_distance_m,
        (
            SELECT COUNT(*)
            FROM mapped_transit
            WHERE ST_DWithin(tract_points.point::geography, location::geography, :half_mile_m)
        ) AS transit_stops_within_half_mi
    FROM tract_points
    """
)


@dataclass(frozen=True)
class MetricComputationResult:
    tracts_seen: int
    metrics_written: int
    metrics_skipped: int
    transit_available: bool
    metadata: dict[str, Any]


def recompute_tract_metrics(db: Session) -> MetricComputationResult:
    LOGGER.info("tract_metric_recompute_started", state_fips=MASSACHUSETTS_STATE_FIPS)
    tracts = (
        db.query(CensusTract)
        .filter(CensusTract.state_fips == MASSACHUSETTS_STATE_FIPS)
        .order_by(CensusTract.geoid.asc())
        .all()
    )
    tract_ids = [tract.id for tract in tracts]
    rows = db.execute(
        SPATIAL_ACCESS_SQL,
        {
            "state_fips": MASSACHUSETTS_STATE_FIPS,
            "one_mile_m": ONE_MILE_METERS,
            "two_miles_m": TWO_MILES_METERS,
            "half_mile_m": HALF_MILE_METERS,
        },
    ).mappings().all()
    transit_stop_count = (
        db.query(func.count(TransitStop.id)).filter(TransitStop.location.is_not(None)).scalar() or 0
    )

    spatial_metrics = _spatial_metric_values(rows)
    if transit_stop_count == 0:
        spatial_metrics["nearest_transit_stop_distance_m"] = {
            tract_id: None for tract_id in tract_ids
        }
        spatial_metrics["transit_stops_within_half_mi"] = {tract_id: None for tract_id in tract_ids}
    vulnerability_metrics = _vulnerability_metric_values(tracts)
    metric_values = {**spatial_metrics, **vulnerability_metrics}
    metric_percentiles = _statewide_percentiles(metric_values)

    metrics_written = 0
    metrics_skipped = 0
    for tract_id in tract_ids:
        for metric_name, values_by_tract in metric_values.items():
            value = values_by_tract.get(tract_id)
            if value is None:
                metrics_skipped += 1
                continue
            definition = _metric_definition(metric_name)
            _upsert_metric(
                db,
                census_tract_id=tract_id,
                metric_name=metric_name,
                metric_value=float(value),
                metric_unit=definition["unit"],
                percentile_statewide=metric_percentiles[metric_name].get(tract_id),
            )
            metrics_written += 1

    db.commit()
    result = MetricComputationResult(
        tracts_seen=len(tracts),
        metrics_written=metrics_written,
        metrics_skipped=metrics_skipped,
        transit_available=transit_stop_count > 0,
        metadata={
            "state_fips": MASSACHUSETTS_STATE_FIPS,
            "distance_method": "ST_PointOnSurface tract representative point with geography meters",
            "cms_provider_spatial_use": "excluded because CMS providers may have null geometry",
            "osm_healthcare_spatial_use": "OSM healthcare amenities drive healthcare proximity",
            "thresholds_meters": {
                "one_mile": ONE_MILE_METERS,
                "two_miles": TWO_MILES_METERS,
                "half_mile": HALF_MILE_METERS,
            },
            "metric_names": sorted(metric_values),
            "mapped_transit_stop_count": transit_stop_count,
        },
    )
    LOGGER.info(
        "tract_metric_recompute_completed",
        state_fips=MASSACHUSETTS_STATE_FIPS,
        tracts_seen=result.tracts_seen,
        metrics_written=result.metrics_written,
        metrics_skipped=result.metrics_skipped,
    )
    score_result = recompute_access_scores(db)
    result.metadata["score_result"] = score_result
    return result


def compute_vulnerability_component_percentiles(
    rows: list[dict[str, float | str | None]],
) -> dict[str, dict[str, float | None]]:
    metric_values: dict[str, dict[str, float | None]] = {
        metric_name: {
            str(row["id"]): _numeric_or_none(row.get(definition["source_column"]))
            for row in rows
        }
        for metric_name, definition in VULNERABILITY_METRIC_DEFINITIONS.items()
    }
    return _statewide_percentiles(metric_values)


def _spatial_metric_values(rows: list[RowMapping]) -> dict[str, dict[str, float | None]]:
    return {
        metric_name: {
            str(row["census_tract_id"]): _numeric_or_none(row[metric_name]) for row in rows
        }
        for metric_name in ACCESS_METRIC_DEFINITIONS
    }


def _vulnerability_metric_values(tracts: list[CensusTract]) -> dict[str, dict[str, float | None]]:
    return {
        metric_name: {
            tract.id: _numeric_or_none(getattr(tract, definition["source_column"]))
            for tract in tracts
        }
        for metric_name, definition in VULNERABILITY_METRIC_DEFINITIONS.items()
    }


def _statewide_percentiles(
    metric_values: dict[str, dict[str, float | None]],
) -> dict[str, dict[str, float | None]]:
    return {
        metric_name: percentile_map(
            values_by_tract,
            higher_is_higher=_metric_definition(metric_name)["higher_percentile_is_more_gap"],
        )
        for metric_name, values_by_tract in metric_values.items()
    }


def _upsert_metric(
    db: Session,
    *,
    census_tract_id: str,
    metric_name: str,
    metric_value: float,
    metric_unit: str,
    percentile_statewide: float | None,
) -> AccessMetric:
    metric = (
        db.query(AccessMetric)
        .filter(
            AccessMetric.census_tract_id == census_tract_id,
            AccessMetric.metric_name == metric_name,
        )
        .one_or_none()
    )
    if metric is None:
        metric = AccessMetric(census_tract_id=census_tract_id, metric_name=metric_name)
    metric.metric_value = metric_value
    metric.metric_unit = metric_unit
    metric.percentile_statewide = percentile_statewide
    metric.computed_at = datetime.now(UTC)
    db.add(metric)
    return metric


def _metric_definition(metric_name: str) -> dict[str, Any]:
    return ACCESS_METRIC_DEFINITIONS.get(metric_name) or VULNERABILITY_METRIC_DEFINITIONS[
        metric_name
    ]


def _numeric_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
