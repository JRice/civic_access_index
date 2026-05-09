def percentile_rank(sorted_values: list[float], value: float) -> float:
    if not sorted_values:
        return 0.0
    below_or_equal = sum(1 for item in sorted_values if item <= value)
    return round(100 * below_or_equal / len(sorted_values), 2)

