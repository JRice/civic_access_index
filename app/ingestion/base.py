from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IngestionResult:
    records_seen: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_rejected: int = 0
    raw_snapshot_uri: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class SourceAdapter(ABC):
    name: str
    source_type: str

    @abstractmethod
    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch raw records from the public source."""

    @abstractmethod
    async def normalize(self, records: list[dict[str, Any]]) -> IngestionResult:
        """Validate and upsert raw records into canonical tables."""

