from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.db.models.access_metric import AccessMetric
from app.db.models.census_tract import CensusTract
from app.db.session import SessionLocal
from app.ingestion.base import IngestionResult, SourceAdapter
from app.logging import get_logger

LOGGER = get_logger(__name__)

MASSACHUSETTS_STATE_FIPS = "25"
ACS_YEAR = "2024"
ACS_PROFILE_URL = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5/profile"
REQUEST_TIMEOUT_SECONDS = 30.0

# Census ACS 5-year profile variables used for socioeconomic vulnerability.
# Counts use estimate fields (E); rates use Census profile percent fields (PE), normalized to 0-1.
ACS_VARIABLES = {
    "total_population": "DP05_0001E",
    "poverty_count": "DP03_0128E",
    "poverty_rate": "DP03_0128PE",
    "median_household_income": "DP03_0062E",
    "no_vehicle_access_count": "DP04_0058E",
    "no_vehicle_access_rate": "DP04_0058PE",
    "disability_count": "DP02_0072E",
    "disability_rate": "DP02_0072PE",
    "age_65_plus_count": "DP05_0024E",
    "age_65_plus_rate": "DP05_0024PE",
}

METRIC_DEFINITIONS = {
    "poverty_count": ("count", ACS_VARIABLES["poverty_count"]),
    "poverty_rate": ("rate", ACS_VARIABLES["poverty_rate"]),
    "median_household_income": ("dollars", ACS_VARIABLES["median_household_income"]),
    "no_vehicle_access_count": ("count", ACS_VARIABLES["no_vehicle_access_count"]),
    "no_vehicle_access_rate": ("rate", ACS_VARIABLES["no_vehicle_access_rate"]),
    "disability_count": ("count", ACS_VARIABLES["disability_count"]),
    "disability_rate": ("rate", ACS_VARIABLES["disability_rate"]),
    "age_65_plus_count": ("count", ACS_VARIABLES["age_65_plus_count"]),
    "age_65_plus_rate": ("rate", ACS_VARIABLES["age_65_plus_rate"]),
}


def normalize_acs_record(record: dict[str, Any]) -> dict[str, Any]:
    state = str(record.get("state") or "").zfill(2)
    county = str(record.get("county") or "").zfill(3)
    tract = str(record.get("tract") or "").zfill(6)
    geoid = f"{state}{county}{tract}"
    if len(geoid) != 11 or state != MASSACHUSETTS_STATE_FIPS:
        raise ValueError(f"Invalid Massachusetts ACS tract GEOID: {geoid!r}")

    return {
        "geoid": geoid,
        "total_population": _parse_int(record.get(ACS_VARIABLES["total_population"])),
        "poverty_count": _parse_int(record.get(ACS_VARIABLES["poverty_count"])),
        "poverty_rate": _parse_percent(record.get(ACS_VARIABLES["poverty_rate"])),
        "median_household_income": _parse_int(
            record.get(ACS_VARIABLES["median_household_income"])
        ),
        "no_vehicle_access_count": _parse_int(record.get(ACS_VARIABLES["no_vehicle_access_count"])),
        "no_vehicle_access_rate": _parse_percent(
            record.get(ACS_VARIABLES["no_vehicle_access_rate"])
        ),
        "disability_count": _parse_int(record.get(ACS_VARIABLES["disability_count"])),
        "disability_rate": _parse_percent(record.get(ACS_VARIABLES["disability_rate"])),
        "age_65_plus_count": _parse_int(record.get(ACS_VARIABLES["age_65_plus_count"])),
        "age_65_plus_rate": _parse_percent(record.get(ACS_VARIABLES["age_65_plus_rate"])),
    }


def _parse_int(value: Any) -> int | None:
    if value in (None, "", "null", "-666666666", "-999999999"):
        return None
    return int(float(value))


def _parse_percent(value: Any) -> float | None:
    if value in (None, "", "null", "-666666666", "-999999999"):
        return None
    return float(value) / 100.0


def _upsert_metric(
    db: Session,
    *,
    tract: CensusTract,
    metric_name: str,
    metric_value: float | int | None,
    metric_unit: str,
    run_id: str | None,
) -> bool:
    if metric_value is None:
        return False

    metric = (
        db.query(AccessMetric)
        .filter(
            AccessMetric.census_tract_id == tract.id,
            AccessMetric.metric_name == metric_name,
        )
        .one_or_none()
    )
    if metric is None:
        metric = AccessMetric(census_tract_id=tract.id, metric_name=metric_name)
    metric.metric_value = float(metric_value)
    metric.metric_unit = metric_unit
    metric.computed_at = datetime.now(UTC)
    metric.source_run_ids = [run_id] if run_id else None
    db.add(metric)
    return True


def _apply_acs_record(
    db: Session,
    parsed: dict[str, Any],
    *,
    run_id: str | None = None,
) -> tuple[int, int]:
    tract = db.query(CensusTract).filter(CensusTract.geoid == parsed["geoid"]).one_or_none()
    if tract is None:
        raise ValueError(f"ACS record references unknown census tract {parsed['geoid']}")

    tract.population = parsed["total_population"]
    tract.median_income = parsed["median_household_income"]
    tract.poverty_rate = parsed["poverty_rate"]
    tract.no_vehicle_household_rate = parsed["no_vehicle_access_rate"]
    tract.elderly_rate = parsed["age_65_plus_rate"]
    tract.disability_rate = parsed["disability_rate"]
    tract.properties_json = {
        **(tract.properties_json or {}),
        "acs_year": ACS_YEAR,
        "acs_variables": ACS_VARIABLES,
        "poverty_count": parsed["poverty_count"],
        "no_vehicle_access_count": parsed["no_vehicle_access_count"],
        "disability_count": parsed["disability_count"],
        "age_65_plus_count": parsed["age_65_plus_count"],
    }
    db.add(tract)

    metrics_written = 0
    for metric_name, (unit, _variable) in METRIC_DEFINITIONS.items():
        if _upsert_metric(
            db,
            tract=tract,
            metric_name=metric_name,
            metric_value=parsed[metric_name],
            metric_unit=unit,
            run_id=run_id,
        ):
            metrics_written += 1
    return 1, metrics_written


class CensusACSAdapter(SourceAdapter):
    name = "census_acs"
    source_type = "census-demographics"
    homepage_url = "https://www.census.gov/programs-surveys/acs"
    api_url = ACS_PROFILE_URL
    license = "U.S. Census Bureau public data"
    refresh_strategy = "annual"

    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id

    async def fetch(self) -> list[dict[str, Any]]:
        variables = ",".join(ACS_VARIABLES.values())
        params = {
            "get": variables,
            "for": "tract:*",
            "in": f"state:{MASSACHUSETTS_STATE_FIPS} county:*",
        }
        LOGGER.info("census_acs_fetch_started", url=ACS_PROFILE_URL, acs_year=ACS_YEAR)
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(ACS_PROFILE_URL, params=params)
            response.raise_for_status()
            payload = response.json()
        if not payload or len(payload) < 2:
            return []
        headers = payload[0]
        records = [dict(zip(headers, row, strict=True)) for row in payload[1:]]
        LOGGER.info("census_acs_fetch_completed", records=len(records), acs_year=ACS_YEAR)
        return records

    async def normalize(self, records: list[dict[str, Any]]) -> IngestionResult:
        updated_tracts = 0
        metrics_written = 0
        rejected = 0

        with SessionLocal() as db:
            for record in records:
                try:
                    tract_count, metric_count = _apply_acs_record(
                        db,
                        normalize_acs_record(record),
                        run_id=self.run_id,
                    )
                    updated_tracts += tract_count
                    metrics_written += metric_count
                except Exception as exc:
                    rejected += 1
                    LOGGER.warning(
                        "census_acs_record_rejected",
                        error=str(exc),
                        state=record.get("state"),
                        county=record.get("county"),
                        tract=record.get("tract"),
                    )
            db.commit()

        return IngestionResult(
            records_seen=len(records),
            records_created=0,
            records_updated=updated_tracts,
            records_rejected=rejected,
            metadata={
                "state_fips": MASSACHUSETTS_STATE_FIPS,
                "acs_year": ACS_YEAR,
                "metrics_written": metrics_written,
                "variables": ACS_VARIABLES,
            },
        )
