from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DataSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source_type: str
    homepage_url: str | None = None
    enabled: bool
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None


class IngestionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    data_source_id: UUID | None = None
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    records_seen: int
    records_created: int
    records_updated: int
    records_rejected: int
    retry_count: int
    error_summary: str | None = None
    raw_snapshot_uri: str | None = None


class TractSummary(BaseModel):
    geoid: str
    name: str | None = None
    state_fips: str
    county_fips: str
    population: int | None = None
    civic_access_index: float | None = None
    vulnerability_score: float | None = None


class ScoreDriver(BaseModel):
    metric: str
    value: float | int | str | None
    percentile: float | None = None
    interpretation: str


class ScoreExplanation(BaseModel):
    tract_geoid: str
    composite_score: float
    main_drivers: list[ScoreDriver] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

