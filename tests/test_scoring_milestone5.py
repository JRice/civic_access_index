from uuid import uuid4

from fastapi.testclient import TestClient

from app.analysis.scoring import mean_available_percentile, recompute_access_scores
from app.api.dependencies import get_db
from app.db.models.access_metric import AccessMetric
from app.db.models.access_score import AccessScore
from app.db.models.census_tract import CensusTract
from app.main import create_app


def test_mean_available_percentile_ignores_missing_values() -> None:
    metrics = [
        AccessMetric(metric_name="a", percentile_statewide=20),
        AccessMetric(metric_name="b", percentile_statewide=None),
        AccessMetric(metric_name="c", percentile_statewide=80),
    ]

    assert mean_available_percentile(metrics) == 50


def test_recompute_access_scores_persists_components_and_explanations_idempotently() -> None:
    tract = CensusTract(
        id="tract-one",
        geoid="25001010100",
        state_fips="25",
        county_fips="001",
        tract_code="010100",
        name="One",
    )
    metrics = [
        _metric(tract.id, "nearest_healthcare_amenity_distance_m", 75),
        _metric(tract.id, "healthcare_amenities_within_1mi", 25),
        _metric(tract.id, "nearest_food_access_distance_m", 80),
        _metric(tract.id, "food_access_amenities_within_1mi", 60),
        _metric(tract.id, "vulnerability_poverty_rate", 90),
        _metric(tract.id, "vulnerability_median_household_income", 70),
    ]
    db = _FakeScoringSession(tracts=[tract], metrics=metrics)

    first = recompute_access_scores(db)
    second = recompute_access_scores(db)

    assert first["scores_written"] == 1
    assert second["scores_written"] == 1
    assert len(db.scores) == 1
    score = next(iter(db.scores.values()))
    assert score.healthcare_access_score == 50
    assert score.food_access_score == 70
    assert score.transit_access_score is None
    assert score.vulnerability_score == 80
    assert score.civic_access_index == 63.75
    assert score.explanation_json["main_drivers"][0]["metric"] == "vulnerability_poverty_rate"
    assert any(
        "Transit score is unavailable" in item
        for item in score.explanation_json["limitations"]
    )


def test_explanation_endpoint_uses_persisted_score_payload() -> None:
    tract = CensusTract(
        id="tract-one",
        geoid="25001010100",
        state_fips="25",
        county_fips="001",
        tract_code="010100",
        name="One",
    )
    score = AccessScore(
        id=str(uuid4()),
        census_tract_id=tract.id,
        composite_score=72,
        civic_access_index=72,
        vulnerability_score=88,
        explanation_json={
            "main_drivers": [
                {
                    "metric": "vulnerability_poverty_rate",
                    "value": 0.3,
                    "percentile": 90,
                    "interpretation": "Higher percentile indicates higher relative vulnerability.",
                }
            ],
            "limitations": ["OSM coverage varies."],
        },
    )
    db = _FakeScoringApiSession(tracts=[tract], scores=[score])
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.get("/api/tracts/25001010100/explanation")

    assert response.status_code == 200
    assert response.json()["composite_score"] == 72
    assert response.json()["main_drivers"][0]["metric"] == "vulnerability_poverty_rate"
    assert response.json()["limitations"] == ["OSM coverage varies."]


def test_scores_top_defaults_to_persisted_civic_access_index() -> None:
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
    scores = [
        AccessScore(census_tract_id=tract_one.id, civic_access_index=40, composite_score=40),
        AccessScore(census_tract_id=tract_two.id, civic_access_index=85, composite_score=85),
    ]
    db = _FakeScoringApiSession(tracts=[tract_one, tract_two], scores=scores)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.get("/api/scores/top?limit=2")

    assert response.status_code == 200
    assert response.json()["score_type"] == "civic_access_index"
    assert response.json()["results"][0]["geoid"] == "25001010200"
    assert response.json()["results"][0]["metric_value"] == 85


def _metric(tract_id: str, name: str, percentile: float) -> AccessMetric:
    return AccessMetric(
        census_tract_id=tract_id,
        metric_name=name,
        metric_value=1.0,
        metric_unit="unit",
        percentile_statewide=percentile,
    )


class _FakeScoringSession:
    def __init__(self, *, tracts: list[CensusTract], metrics: list[AccessMetric]) -> None:
        self.tracts = tracts
        self.metrics = metrics
        self.scores = {}

    def query(self, model):
        return _FakeScoringQuery(self, model)

    def add(self, score: AccessScore) -> None:
        self.scores[score.census_tract_id] = score

    def commit(self) -> None:
        pass


class _FakeScoringQuery:
    def __init__(self, session: _FakeScoringSession, model) -> None:
        self.session = session
        self.model = model
        self.tract_id = None

    def filter(self, *args):
        for arg in args:
            text = str(arg)
            for tract in self.session.tracts:
                if tract.id in text:
                    self.tract_id = tract.id
        return self

    def all(self):
        if self.model is CensusTract:
            return self.session.tracts
        if self.model is AccessMetric:
            return self.session.metrics
        return []

    def one_or_none(self):
        if self.model is AccessScore:
            if self.tract_id:
                return self.session.scores.get(self.tract_id)
            return next(iter(self.session.scores.values()), None)
        return None


class _FakeScoringApiSession:
    def __init__(
        self,
        *,
        tracts: list[CensusTract],
        scores: list[AccessScore],
    ) -> None:
        self.tracts = tracts
        self.scores = scores

    def query(self, *models):
        return _FakeScoringApiQuery(self, models)


class _FakeScoringApiQuery:
    def __init__(self, session: _FakeScoringApiSession, models: tuple) -> None:
        self.session = session
        self.models = models
        self.limit_count = None

    def filter(self, *_args):
        return self

    def join(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def limit(self, limit: int):
        self.limit_count = limit
        return self

    def all(self):
        if len(self.models) == 2 and self.models[0] is AccessScore:
            pairs = [
                (score, self._tract_for_score(score))
                for score in self.session.scores
            ]
            pairs.sort(key=lambda pair: pair[0].civic_access_index or -1, reverse=True)
            return pairs[: self.limit_count]
        return []

    def one_or_none(self):
        if len(self.models) == 1 and self.models[0] is CensusTract:
            return self.session.tracts[0] if self.session.tracts else None
        if len(self.models) == 1 and self.models[0] is AccessScore:
            return self.session.scores[0] if self.session.scores else None
        return None

    def _tract_for_score(self, score: AccessScore) -> CensusTract:
        return next(tract for tract in self.session.tracts if tract.id == score.census_tract_id)
