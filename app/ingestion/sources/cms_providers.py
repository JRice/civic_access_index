from typing import Any

from app.ingestion.base import IngestionResult, SourceAdapter


class CMSProvidersAdapter(SourceAdapter):
    name = "cms_providers"
    source_type = "healthcare-provider"

    async def fetch(self) -> list[dict[str, Any]]:
        return []

    async def normalize(self, records: list[dict[str, Any]]) -> IngestionResult:
        return IngestionResult(records_seen=len(records))

