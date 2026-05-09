def normalize_provider_type(value: str | None) -> str | None:
    if value is None:
        return None
    return value.lower().strip().replace(" ", "_")

