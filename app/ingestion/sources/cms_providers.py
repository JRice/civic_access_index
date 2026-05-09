import asyncio
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.db.models.data_source import DataSource
from app.db.models.provider import Provider
from app.db.session import SessionLocal
from app.ingestion.base import IngestionResult, SourceAdapter
from app.logging import get_logger

LOGGER = get_logger(__name__)

CMS_HOSPITAL_GENERAL_INFORMATION_URL = (
    "https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0"
)
REQUEST_TIMEOUT_SECONDS = 60.0
MAX_ATTEMPTS = 3


def normalize_cms_provider(record: dict[str, Any]) -> dict[str, Any]:
    facility_id = _clean(record.get("facility_id"))
    name = _clean(record.get("facility_name"))
    state = (_clean(record.get("state")) or "").upper()
    if not facility_id or not name:
        raise ValueError("CMS provider record is missing facility_id or facility_name.")
    if state != "MA":
        raise ValueError(f"CMS provider {facility_id} is outside Massachusetts.")

    provider_type = _clean(record.get("hospital_type")) or "hospital"
    return {
        "source_record_id": f"cms:hospital:{facility_id}",
        "name": name,
        "provider_type": provider_type[:80],
        "address": _clean(record.get("address")),
        "city": _clean(record.get("citytown")),
        "state": state,
        "postal_code": _clean(record.get("zip_code")),
        "cms_rating": _parse_rating(record.get("hospital_overall_rating")),
        "accepts_medicare": True,
        "raw_payload_json": {
            "source_dataset": "Hospital General Information",
            "facility_id": facility_id,
            "phone": _clean(record.get("telephone_number")),
            "county": _clean(record.get("countyparish")),
            "hospital_type": provider_type,
            "hospital_ownership": _clean(record.get("hospital_ownership")),
            "emergency_services": _clean(record.get("emergency_services")),
            "raw": record,
        },
    }


def _clean(value: Any) -> str | None:
    if value in (None, "", "Not Available"):
        return None
    return str(value).strip()


def _parse_rating(value: Any) -> float | None:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _upsert_provider(db: Session, source: DataSource, parsed: dict[str, Any]) -> bool:
    provider = (
        db.query(Provider)
        .filter(
            Provider.source_id == source.id,
            Provider.source_record_id == parsed["source_record_id"],
        )
        .one_or_none()
    )
    created = provider is None
    if provider is None:
        provider = Provider(
            source_id=source.id,
            source_record_id=parsed["source_record_id"],
        )

    provider.name = parsed["name"]
    provider.provider_type = parsed["provider_type"]
    provider.address = parsed["address"]
    provider.city = parsed["city"]
    provider.state = parsed["state"]
    provider.postal_code = parsed["postal_code"]
    provider.location = None
    provider.cms_rating = parsed["cms_rating"]
    provider.accepts_medicare = parsed["accepts_medicare"]
    provider.raw_payload_json = parsed["raw_payload_json"]
    db.add(provider)
    return created


class CMSProvidersAdapter(SourceAdapter):
    name = "cms_providers"
    source_type = "healthcare-provider"
    homepage_url = "https://data.cms.gov/provider-data"
    api_url = CMS_HOSPITAL_GENERAL_INFORMATION_URL
    license = "CMS public provider data"
    refresh_strategy = "quarterly CMS Provider Data refresh"

    async def fetch(self) -> list[dict[str, Any]]:
        LOGGER.info("cms_providers_fetch_started", url=CMS_HOSPITAL_GENERAL_INFORMATION_URL)
        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                    response = await client.get(
                        CMS_HOSPITAL_GENERAL_INFORMATION_URL,
                        params={"size": 10000},
                    )
                    response.raise_for_status()
                    payload = response.json()
                records = [
                    record for record in payload.get("results", []) if record.get("state") == "MA"
                ]
                LOGGER.info("cms_providers_fetch_completed", records=len(records), attempt=attempt)
                return records
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code not in {429, 500, 502, 503, 504}:
                    raise
            except httpx.HTTPError as exc:
                last_error = exc
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(2**attempt)

        raise RuntimeError(
            f"CMS provider request failed after {MAX_ATTEMPTS} attempts: {last_error}"
        )

    async def normalize(self, records: list[dict[str, Any]]) -> IngestionResult:
        created = 0
        updated = 0
        rejected = 0

        with SessionLocal() as db:
            source = db.query(DataSource).filter(DataSource.name == self.name).one()
            for record in records:
                try:
                    parsed = normalize_cms_provider(record)
                    if _upsert_provider(db, source, parsed):
                        created += 1
                    else:
                        updated += 1
                except Exception as exc:
                    rejected += 1
                    LOGGER.warning(
                        "cms_provider_record_rejected",
                        error=str(exc),
                        facility_id=record.get("facility_id"),
                    )
            db.commit()

        return IngestionResult(
            records_seen=len(records),
            records_created=created,
            records_updated=updated,
            records_rejected=rejected,
            metadata={
                "state": "MA",
                "dataset": "Hospital General Information",
                "cms_dataset_id": "xubh-q36u",
                "geocoding": "skipped; CMS dataset provides address fields but no coordinates",
            },
        )
