from typing import Any

from app.ingestion.base import IngestionResult, SourceAdapter


class CensusTigerAdapter(SourceAdapter):
    name = "census_tiger"
    source_type = "census-geography"

    async def fetch(self) -> list[dict[str, Any]]:
        return []

    async def normalize(self, records: list[dict[str, Any]]) -> IngestionResult:
        return IngestionResult(records_seen=len(records))

