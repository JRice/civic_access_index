def percentile_rank(sorted_values: list[float], value: float) -> float:
    if not sorted_values:
        return 0.0
    below_or_equal = sum(1 for item in sorted_values if item <= value)
    return round(100 * below_or_equal / len(sorted_values), 2)


def midpoint_percentile(
    values: list[float | None],
    value: float,
    *,
    higher_is_higher: bool,
) -> float:
    valid_values = [item for item in values if item is not None]
    if not valid_values:
        return 0.0

    if higher_is_higher:
        better_count = sum(1 for item in valid_values if item < value)
    else:
        better_count = sum(1 for item in valid_values if item > value)
    tied_count = sum(1 for item in valid_values if item == value)
    return round(100 * (better_count + 0.5 * tied_count) / len(valid_values), 2)


def percentile_map(
    values_by_id: dict[str, float | None],
    *,
    higher_is_higher: bool = True,
) -> dict[str, float | None]:
    values = list(values_by_id.values())
    return {
        item_id: (
            midpoint_percentile(values, value, higher_is_higher=higher_is_higher)
            if value is not None
            else None
        )
        for item_id, value in values_by_id.items()
    }
