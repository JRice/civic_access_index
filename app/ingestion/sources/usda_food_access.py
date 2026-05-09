from typing import Any

from app.ingestion.base import IngestionResult, SourceAdapter


class USDAFoodAccessAdapter(SourceAdapter):
    name = "usda_food_access"
    source_type = "food-access"

    async def fetch(self) -> list[dict[str, Any]]:
        return []

    async def normalize(self, records: list[dict[str, Any]]) -> IngestionResult:
        return IngestionResult(records_seen=len(records))

