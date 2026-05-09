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


class AmenityRead(BaseModel):
    id: UUID
    source_record_id: str | None = None
    name: str | None = None
    category: str
    normalized_category: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    longitude: float | None = None
    latitude: float | None = None


class ProviderRead(BaseModel):
    id: UUID
    source_record_id: str | None = None
    name: str | None = None
    provider_type: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    cms_rating: float | None = None
    accepts_medicare: bool | None = None
    longitude: float | None = None
    latitude: float | None = None
    is_mappable: bool = False
    mapping_status: str = "not_mappable"


class TractSummary(BaseModel):
    geoid: str
    name: str | None = None
    state_fips: str
    county_fips: str
    population: int | None = None
    civic_access_index: float | None = None
    vulnerability_score: float | None = None


class TractMetricRead(BaseModel):
    metric_name: str
    metric_value: float | None = None
    metric_unit: str | None = None
    percentile_statewide: float | None = None
    percentile_county: float | None = None
    status: str = "available"
    caveat: str | None = None


class ScoreTopResult(BaseModel):
    geoid: str
    tract_name: str | None = None
    county_fips: str
    metric_name: str
    metric_value: float | None = None
    metric_unit: str | None = None
    percentile_statewide: float | None = None
    healthcare_access_score: float | None = None
    food_access_score: float | None = None
    transit_access_score: float | None = None
    vulnerability_score: float | None = None


class ScoreDistributionBucket(BaseModel):
    bucket_min: float
    bucket_max: float
    count: int


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
