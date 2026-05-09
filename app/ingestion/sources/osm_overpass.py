from typing import Any

from app.ingestion.base import IngestionResult, SourceAdapter


class OSMOverpassAdapter(SourceAdapter):
    name = "osm_overpass"
    source_type = "amenity"

    async def fetch(self) -> list[dict[str, Any]]:
        return []

    async def normalize(self, records: list[dict[str, Any]]) -> IngestionResult:
        return IngestionResult(records_seen=len(records))

