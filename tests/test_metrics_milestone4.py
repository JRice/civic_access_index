from uuid import uuid4

from fastapi.testclient import TestClient

from app.analysis.metrics import (
    SPATIAL_ACCESS_SQL,
    _upsert_metric,
    compute_vulnerability_component_percentiles,
)
from app.analysis.percentiles import midpoint_percentile, percentile_map
from app.api.dependencies import get_db
from app.db.models.access_metric import AccessMetric
from app.db.models.census_tract import CensusTract
from app.main import create_app


def test_spatial_metric_sql_uses_representative_points_and_geography_meters() -> None:
    sql = str(SPATIAL_ACCESS_SQL)

    assert "ST_PointOnSurface" in sql
    assert "::geography" in sql
    assert "ST_DWithin" in sql
    assert "providers" not in sql


def test_midpoint_percentiles_handle_nulls_and_ties() -> None:
    values = {"a": 1.0, "b": 2.0, "c": 2.0, "d": 4.0, "e": None}

    percentiles = percentile_map(values)

    assert midpoint_percentile([1.0, 2.0, 2.0, 4.0, None], 2.0, higher_is_higher=True) == 50
    assert percentiles["a"] == 12.5
    assert percentiles["b"] == 50
    assert percentiles["c"] == 50
    assert percentiles["d"] == 87.5
    assert percentiles["e"] is None


def test_vulnerability_percentiles_invert_income_direction() -> None:
    rows = [
        {"id": "low_income", "median_income": 30000, "poverty_rate": 0.10},
        {"id": "mid_income", "median_income": 60000, "poverty_rate": 0.20},
        {"id": "high_income", "median_income": 90000, "poverty_rate": 0.30},
    ]

    percentiles = compute_vulnerability_component_percentiles(rows)

    assert percentiles["vulnerability_median_household_income"]["low_income"] > percentiles[
        "vulnerability_median_household_income"
    ]["high_income"]
    assert percentiles["vulnerability_poverty_rate"]["high_income"] > percentiles[
        "vulnerability_poverty_rate"
    ]["low_income"]


def test_metric_upsert_is_idempotent() -> None:
    db = _FakeMetricSession()
    tract_id = str(uuid4())

    _upsert_metric(
        db,
        census_tract_id=tract_id,
        metric_name="nearest_food_access_distance_m",
        metric_value=1000.0,
        metric_unit="meters",
        percentile_statewide=50.0,
    )
    _upsert_metric(
        db,
        census_tract_id=tract_id,
        metric_name="nearest_food_access_distance_m",
        metric_value=900.0,
        metric_unit="meters",
        percentile_statewide=40.0,
    )

    assert len(db.metrics) == 1
    metric = next(iter(db.metrics.values()))
    assert metric.metric_value == 900.0
    assert metric.percentile_statewide == 40.0


def test_tract_metrics_endpoint_returns_available_and_not_available_metrics() -> None:
    tract = CensusTract(
        id=str(uuid4()),
        geoid="25001010100",
        state_fips="25",
        county_fips="001",
        tract_code="010100",
        name="Census Tract 101",
    )
    metric = AccessMetric(
        id=str(uuid4()),
        census_tract_id=tract.id,
        metric_name="vulnerability_poverty_rate",
        metric_value=0.25,
        metric_unit="rate",
        percentile_statewide=80.0,
    )
    db = _FakeApiSession(tracts=[tract], metrics=[metric])
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.get("/api/tracts/25001010100/metrics")

    assert response.status_code == 200
    payload = response.json()
    available = {
        item["metric_name"]: item
        for item in payload["metrics"]
        if item["status"] == "available"
    }
    missing = {
        item["metric_name"]: item
        for item in payload["metrics"]
        if item["status"] == "not_available"
    }
    assert available["vulnerability_poverty_rate"]["percentile_statewide"] == 80.0
    assert missing["nearest_transit_stop_distance_m"]["caveat"].startswith("Transit stop data")


def test_scores_top_and_distribution_endpoints() -> None:
    tract_one = CensusTract(
        id="tract-one",
        geoid="25001010100",
        state_fips="25",
        county_fips="001",
        tract_code="010100",
        name="One",
    )
    tract_two = CensusTract(
        id="tract-two",
        geoid="25001010200",
        state_fips="25",
        county_fips="001",
        tract_code="010200",
        name="Two",
    )
    metric_one = AccessMetric(
        census_tract_id=tract_one.id,
        metric_name="vulnerability_poverty_rate",
        metric_value=0.1,
        metric_unit="rate",
        percentile_statewide=30,
    )
    metric_two = AccessMetric(
        census_tract_id=tract_two.id,
        metric_name="vulnerability_poverty_rate",
        metric_value=0.3,
        metric_unit="rate",
        percentile_statewide=90,
    )
    db = _FakeApiSession(
        tracts=[tract_one, tract_two],
        metrics=[metric_one, metric_two],
    )
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    top_response = client.get("/api/scores/top?score_type=vulnerability_poverty_rate&limit=2")
    distribution_response = client.get(
        "/api/scores/distribution?score_type=vulnerability_poverty_rate"
    )

    assert top_response.status_code == 200
    assert top_response.json()["results"][0]["geoid"] == "25001010200"
    assert distribution_response.status_code == 200
    assert distribution_response.json()["count"] == 2
    assert sum(bucket["count"] for bucket in distribution_response.json()["buckets"]) == 2


class _FakeMetricSession:
    def __init__(self) -> None:
        self.metrics = {}

    def query(self, model):
        assert model is AccessMetric
        return _FakeMetricQuery(self)

    def add(self, metric: AccessMetric) -> None:
        self.metrics[(metric.census_tract_id, metric.metric_name)] = metric


class _FakeMetricQuery:
    def __init__(self, session: _FakeMetricSession) -> None:
        self.session = session

    def filter(self, *_args):
        return self

    def one_or_none(self):
        return next(iter(self.session.metrics.values()), None)


class _FakeApiSession:
    def __init__(self, *, tracts: list[CensusTract], metrics: list[AccessMetric]) -> None:
        self.tracts = tracts
        self.metrics = metrics

    def query(self, *models):
        return _FakeApiQuery(self, models)


class _FakeApiQuery:
    def __init__(self, session: _FakeApiSession, models: tuple) -> None:
        self.session = session
        self.models = models
        self.limit_count = None
        self.metric_name = None

    def filter(self, *args):
        for arg in args:
            text = str(arg)
            if "access_metrics.metric_name" in text:
                for metric in self.session.metrics:
                    if metric.metric_name in text:
                        self.metric_name = metric.metric_name
        return self

    def join(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def limit(self, limit: int):
        self.limit_count = limit
        return self

    def all(self):
        if len(self.models) == 1 and self.models[0] is CensusTract:
            return self.session.tracts[: self.limit_count]
        if len(self.models) == 1 and self.models[0] is AccessMetric:
            return self.session.metrics
        if (
            len(self.models) == 2
            and self.models[0] is AccessMetric
            and self.models[1] is CensusTract
        ):
            pairs = [
                (metric, self._tract_for_metric(metric))
                for metric in self.session.metrics
                if self.metric_name is None or metric.metric_name == self.metric_name
            ]
            pairs.sort(key=lambda pair: pair[0].percentile_statewide or -1, reverse=True)
            return pairs[: self.limit_count]
        if len(self.models) == 1 and "percentile_statewide" in str(self.models[0]):
            return [
                (metric.percentile_statewide,)
                for metric in self.session.metrics
                if metric.percentile_statewide is not None
            ]
        return []

    def one_or_none(self):
        if len(self.models) == 1 and self.models[0] is CensusTract:
            return self.session.tracts[0] if self.session.tracts else None
        return None

    def _tract_for_metric(self, metric: AccessMetric) -> CensusTract:
        return next(tract for tract in self.session.tracts if tract.id == metric.census_tract_id)
