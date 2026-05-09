from typing import Any

from app.ingestion.base import IngestionResult, SourceAdapter


class GTFSAdapter(SourceAdapter):
    name = "gtfs"
    source_type = "transit"

    async def fetch(self) -> list[dict[str, Any]]:
        return []

    async def normalize(self, records: list[dict[str, Any]]) -> IngestionResult:
        return IngestionResult(records_seen=len(records))

