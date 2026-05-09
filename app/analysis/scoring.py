SCORE_WEIGHTS = {
    "healthcare_gap_score": 0.35,
    "food_gap_score": 0.25,
    "transit_gap_score": 0.20,
    "socioeconomic_vulnerability_score": 0.20,
}


def compute_civic_access_index(
    healthcare_gap_score: float,
    food_gap_score: float,
    transit_gap_score: float,
    socioeconomic_vulnerability_score: float,
) -> float:
    weighted = (
        SCORE_WEIGHTS["healthcare_gap_score"] * healthcare_gap_score
        + SCORE_WEIGHTS["food_gap_score"] * food_gap_score
        + SCORE_WEIGHTS["transit_gap_score"] * transit_gap_score
        + SCORE_WEIGHTS["socioeconomic_vulnerability_score"] * socioeconomic_vulnerability_score
    )
    return round(weighted, 2)

