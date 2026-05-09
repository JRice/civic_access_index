from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_db
from app.db.models.amenity import Amenity
from app.db.models.data_source import DataSource
from app.db.models.provider import Provider
from app.ingestion.sources import cms_providers, osm_overpass
from app.ingestion.sources.cms_providers import (
    _upsert_provider,
    normalize_cms_provider,
)
from app.ingestion.sources.osm_overpass import (
    _upsert_amenity,
    normalize_osm_element,
)
from app.main import create_app


def test_osm_normalization_handles_nodes_and_centered_members() -> None:
    node = normalize_osm_element(
        {
            "type": "node",
            "id": 1,
            "lat": 42.36,
            "lon": -71.06,
            "tags": {
                "amenity": "pharmacy",
                "name": "Beacon Pharmacy",
                "addr:housenumber": "10",
                "addr:street": "Main St",
                "addr:city": "Boston",
                "addr:postcode": "02108",
            },
        }
    )
    way = normalize_osm_element(
        {
            "type": "way",
            "id": 2,
            "center": {"lat": 42.37, "lon": -71.07},
            "tags": {"shop": "supermarket", "name": "Market"},
        }
    )
    relation = normalize_osm_element(
        {
            "type": "relation",
            "id": 3,
            "center": {"lat": 42.38, "lon": -71.08},
            "tags": {"amenity": "library", "name": "Branch Library"},
        }
    )

    assert node["source_record_id"] == "osm:node/1"
    assert node["normalized_category"] == "healthcare"
    assert node["address"] == "10 Main St"
    assert way["normalized_category"] == "food_access"
    assert relation["normalized_category"] == "civic_service"


def test_cms_provider_normalization_preserves_address_and_phone_without_geometry() -> None:
    provider = normalize_cms_provider(
        {
            "facility_id": "220001",
            "facility_name": "MASSACHUSETTS GENERAL HOSPITAL",
            "address": "55 FRUIT STREET",
            "citytown": "BOSTON",
            "state": "MA",
            "zip_code": "02114",
            "countyparish": "SUFFOLK",
            "telephone_number": "(617) 726-2000",
            "hospital_type": "Acute Care Hospitals",
            "hospital_overall_rating": "5",
        }
    )

    assert provider["source_record_id"] == "cms:hospital:220001"
    assert provider["name"] == "MASSACHUSETTS GENERAL HOSPITAL"
    assert provider["state"] == "MA"
    assert provider["cms_rating"] == 5.0
    assert provider["raw_payload_json"]["phone"] == "(617) 726-2000"


def test_osm_and_cms_upserts_are_idempotent() -> None:
    amenity_source = DataSource(id=str(uuid4()), name="osm_overpass", source_type="amenity")
    provider_source = DataSource(
        id=str(uuid4()),
        name="cms_providers",
        source_type="healthcare-provider",
    )
    amenity_db = _FakeUpsertSession(Amenity)
    provider_db = _FakeUpsertSession(Provider)
    parsed_amenity = normalize_osm_element(
        {
            "type": "node",
            "id": 10,
            "lat": 42.0,
            "lon": -71.0,
            "tags": {"amenity": "clinic", "name": "Clinic"},
        }
    )
    parsed_provider = normalize_cms_provider(
        {
            "facility_id": "220010",
            "facility_name": "CLINIC HOSPITAL",
            "state": "MA",
            "hospital_type": "Acute Care Hospitals",
        }
    )

    assert _upsert_amenity(amenity_db, amenity_source, parsed_amenity) is True
    assert _upsert_amenity(amenity_db, amenity_source, parsed_amenity) is False
    assert len(amenity_db.rows) == 1
    assert _upsert_provider(provider_db, provider_source, parsed_provider) is True
    assert _upsert_provider(provider_db, provider_source, parsed_provider) is False
    assert len(provider_db.rows) == 1


async def test_rejection_counting_for_malformed_records(monkeypatch) -> None:
    osm_source = DataSource(id=str(uuid4()), name="osm_overpass", source_type="amenity")
    cms_source = DataSource(
        id=str(uuid4()),
        name="cms_providers",
        source_type="healthcare-provider",
    )
    monkeypatch.setattr(
        osm_overpass,
        "SessionLocal",
        lambda: _FakeNormalizeSession(Amenity, osm_source),
    )
    monkeypatch.setattr(
        cms_providers,
        "SessionLocal",
        lambda: _FakeNormalizeSession(Provider, cms_source),
    )

    osm_result = await osm_overpass.OSMOverpassAdapter().normalize(
        [
            {"type": "node", "id": 1, "lat": 42.0, "lon": -71.0, "tags": {"amenity": "clinic"}},
            {"type": "node", "id": 2, "tags": {"amenity": "clinic"}},
        ]
    )
    cms_result = await cms_providers.CMSProvidersAdapter().normalize(
        [
            {"facility_id": "220001", "facility_name": "Hospital", "state": "MA"},
            {"facility_id": "220002", "facility_name": "Out-of-state", "state": "RI"},
        ]
    )

    assert osm_result.records_seen == 2
    assert osm_result.records_created == 1
    assert osm_result.records_rejected == 1
    assert cms_result.records_seen == 2
    assert cms_result.records_created == 1
    assert cms_result.records_rejected == 1


def test_amenity_and_provider_api_filtering(monkeypatch) -> None:
    amenity = Amenity(
        id=str(uuid4()),
        source_record_id="osm:node/1",
        name="Beacon Pharmacy",
        category="pharmacy",
        normalized_category="healthcare",
        city="Boston",
        state="MA",
    )
    provider = Provider(
        id=str(uuid4()),
        source_record_id="cms:hospital:220001",
        name="Mass General",
        provider_type="Acute Care Hospitals",
        city="Boston",
        state="MA",
        raw_payload_json={"phone": "(617) 726-2000", "county": "SUFFOLK"},
    )
    db = _FakeApiSession(
        amenity_rows=[(amenity, -71.06, 42.36)],
        provider_rows=[(provider, None, None)],
    )

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    amenities_response = client.get("/api/amenities?category=healthcare&city=Boston&limit=5")
    providers_response = client.get("/api/providers?provider_type=Acute&state=MA&limit=5")

    assert amenities_response.status_code == 200
    assert amenities_response.json()["results"][0]["name"] == "Beacon Pharmacy"
    assert amenities_response.json()["results"][0]["longitude"] == -71.06
    assert providers_response.status_code == 200
    assert providers_response.json()["results"][0]["phone"] == "(617) 726-2000"
    assert db.queries[0].filter_count >= 2
    assert db.queries[1].filter_count >= 2


class _FakeUpsertSession:
    def __init__(self, model) -> None:
        self.model = model
        self.rows = {}

    def query(self, _model):
        return _FakeUpsertQuery(self)

    def add(self, row) -> None:
        self.rows[row.source_record_id] = row


class _FakeUpsertQuery:
    def __init__(self, session: _FakeUpsertSession) -> None:
        self.session = session

    def filter(self, *_args):
        return self

    def one_or_none(self):
        if len(self.session.rows) == 1:
            return next(iter(self.session.rows.values()))
        return None


class _FakeNormalizeSession(_FakeUpsertSession):
    def __init__(self, row_model, source: DataSource) -> None:
        super().__init__(row_model)
        self.source = source

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def query(self, model):
        if model is DataSource:
            return _FakeSourceQuery(self.source)
        return _FakeUpsertQuery(self)

    def commit(self) -> None:
        pass


class _FakeSourceQuery:
    def __init__(self, source: DataSource) -> None:
        self.source = source

    def filter(self, *_args):
        return self

    def one(self):
        return self.source


class _FakeApiSession:
    def __init__(self, *, amenity_rows: list, provider_rows: list) -> None:
        self.amenity_rows = amenity_rows
        self.provider_rows = provider_rows
        self.queries = []

    def query(self, model, *_columns):
        if model is Amenity:
            query = _FakeApiQuery(self.amenity_rows)
        elif model is Provider:
            query = _FakeApiQuery(self.provider_rows)
        else:
            raise AssertionError(f"Unexpected model: {model}")
        self.queries.append(query)
        return query


class _FakeApiQuery:
    def __init__(self, rows: list) -> None:
        self.rows = rows
        self.filter_count = 0

    def filter(self, *_args):
        self.filter_count += 1
        return self

    def order_by(self, *_args):
        return self

    def offset(self, _offset: int):
        return self

    def limit(self, _limit: int):
        return self

    def all(self):
        return self.rows
