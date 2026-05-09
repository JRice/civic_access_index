from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import MultiPolygon, Polygon

from app.api.dependencies import get_db
from app.db.models.data_source import DataSource
from app.db.models.ingestion_run import IngestionRun
from app.ingestion.lifecycle import (
    create_ingestion_run,
    mark_ingestion_run_failed,
    mark_ingestion_run_succeeded,
)
from app.ingestion.sources.census_acs import ACS_VARIABLES, normalize_acs_record
from app.ingestion.sources.census_tiger import _upsert_tiger_record, parse_tiger_tract_record
from app.main import create_app


def test_acs_normalization_converts_counts_and_rates() -> None:
    record = {
        ACS_VARIABLES["total_population"]: "1000",
        ACS_VARIABLES["poverty_count"]: "123",
        ACS_VARIABLES["poverty_rate"]: "12.3",
        ACS_VARIABLES["median_household_income"]: "85000",
        ACS_VARIABLES["no_vehicle_access_count"]: "25",
        ACS_VARIABLES["no_vehicle_access_rate"]: "2.5",
        ACS_VARIABLES["disability_count"]: "99",
        ACS_VARIABLES["disability_rate"]: "9.9",
        ACS_VARIABLES["age_65_plus_count"]: "140",
        ACS_VARIABLES["age_65_plus_rate"]: "14.0",
        "state": "25",
        "county": "001",
        "tract": "010100",
    }

    normalized = normalize_acs_record(record)

    assert normalized["geoid"] == "25001010100"
    assert normalized["total_population"] == 1000
    assert normalized["poverty_count"] == 123
    assert normalized["poverty_rate"] == pytest.approx(0.123)
    assert normalized["median_household_income"] == 85000
    assert normalized["no_vehicle_access_rate"] == pytest.approx(0.025)
    assert normalized["disability_rate"] == pytest.approx(0.099)
    assert normalized["age_65_plus_rate"] == pytest.approx(0.14)


def test_tiger_geoid_parsing_and_upsert_is_idempotent() -> None:
    polygon = Polygon(
        [
            (-70.1, 42.1),
            (-70.0, 42.1),
            (-70.0, 42.2),
            (-70.1, 42.2),
            (-70.1, 42.1),
        ]
    )
    parsed = parse_tiger_tract_record(
        {
            "GEOID": "25001010100",
            "STATEFP": "25",
            "COUNTYFP": "001",
            "TRACTCE": "010100",
            "NAMELSAD": "Census Tract 101",
            "ALAND": "100",
            "AWATER": "2",
            "geometry_wkt": polygon.wkt,
        }
    )
    db = _FakeTractSession()

    assert isinstance(parsed["geometry"], MultiPolygon)
    assert _upsert_tiger_record(db, parsed) is True
    assert _upsert_tiger_record(db, parsed) is False
    assert len(db.tracts) == 1
    assert db.tracts["25001010100"].name == "Census Tract 101"
    assert db.tracts["25001010100"].properties_json["aland"] == 100


def test_ingestion_lifecycle_records_success_and_failure() -> None:
    data_source = DataSource(
        id=str(uuid4()),
        name="census_acs",
        source_type="census-demographics",
        enabled=True,
    )
    db = _FakeLifecycleSession(data_source=data_source)
    run = create_ingestion_run(db, data_source_id=data_source.id)
    run.data_source = data_source

    mark_ingestion_run_succeeded(
        db,
        run,
        records_seen=10,
        records_created=0,
        records_updated=9,
        records_rejected=1,
        raw_snapshot_uri="local-data/raw-snapshots/census_acs/test.json",
        metadata_json={"acs_year": "2024"},
    )

    assert run.status == "partial"
    assert run.records_seen == 10
    assert data_source.last_success_at is not None

    failed_run = create_ingestion_run(db, data_source_id=data_source.id)
    failed_run.data_source = data_source
    mark_ingestion_run_failed(db, failed_run, "boom")

    assert failed_run.status == "failed"
    assert failed_run.error_summary == "boom"
    assert data_source.last_failure_at is not None


def test_ingestion_routes_return_database_data(monkeypatch) -> None:
    run_id = str(uuid4())
    source_id = str(uuid4())
    started_at = datetime.now(UTC)
    source = DataSource(
        id=source_id,
        name="census_tiger",
        source_type="census-geography",
        homepage_url="https://www.census.gov/",
        enabled=True,
    )
    run = IngestionRun(
        id=run_id,
        data_source_id=source_id,
        status="succeeded",
        started_at=started_at,
        completed_at=started_at,
        records_seen=1,
        records_created=1,
        records_updated=0,
        records_rejected=0,
        retry_count=0,
    )
    db = _FakeApiSession(runs=[run], sources=[source])
    monkeypatch.setattr("app.api.routes.ingestion_runs.get_source_registry", lambda: {})

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    runs_response = client.get("/api/ingestion-runs")
    run_response = client.get(f"/api/ingestion-runs/{run_id}")
    sources_response = client.get("/api/data-sources")

    assert runs_response.status_code == 200
    assert runs_response.json()["results"][0]["id"] == run_id
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "succeeded"
    assert sources_response.status_code == 200
    assert sources_response.json()["results"][0]["name"] == "census_tiger"


class _FakeTractSession:
    def __init__(self) -> None:
        self.tracts = {}

    def query(self, _model):
        return self

    def filter(self, *_args):
        return self

    def one_or_none(self):
        return self.tracts.get("25001010100")

    def add(self, tract) -> None:
        self.tracts[tract.geoid] = tract


class _FakeLifecycleSession:
    def __init__(self, data_source: DataSource) -> None:
        self.data_source = data_source

    def add(self, obj) -> None:
        if isinstance(obj, IngestionRun) and obj.data_source_id == self.data_source.id:
            obj.data_source = self.data_source

    def commit(self) -> None:
        pass

    def refresh(self, obj) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = str(uuid4())


class _FakeApiSession:
    def __init__(self, *, runs: list[IngestionRun], sources: list[DataSource]) -> None:
        self.runs = runs
        self.sources = sources

    def query(self, model):
        if model is IngestionRun:
            return _FakeQuery(self.runs)
        if model is DataSource:
            return _FakeQuery(self.sources)
        raise AssertionError(f"Unexpected model: {model}")

    def get(self, model, obj_id: str):
        if model is IngestionRun:
            return next((run for run in self.runs if run.id == obj_id), None)
        return None


class _FakeQuery:
    def __init__(self, rows: list) -> None:
        self.rows = rows

    def order_by(self, *_args):
        return self

    def limit(self, _limit: int):
        return self

    def all(self):
        return self.rows
