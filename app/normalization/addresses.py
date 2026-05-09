def normalize_state(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().upper()

