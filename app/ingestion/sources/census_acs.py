from typing import Any

from app.ingestion.base import IngestionResult, SourceAdapter


class CensusACSAdapter(SourceAdapter):
    name = "census_acs"
    source_type = "census-demographics"

    async def fetch(self) -> list[dict[str, Any]]:
        return []

    async def normalize(self, records: list[dict[str, Any]]) -> IngestionResult:
        return IngestionResult(records_seen=len(records))

