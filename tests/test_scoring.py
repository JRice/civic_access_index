from app.analysis.scoring import compute_civic_access_index


def test_compute_civic_access_index_uses_declared_weights() -> None:
    score = compute_civic_access_index(
        healthcare_gap_score=80,
        food_gap_score=60,
        transit_gap_score=50,
        socioeconomic_vulnerability_score=90,
    )

    assert score == 71.0

