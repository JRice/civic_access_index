def keys_for_source_refresh(source_name: str) -> list[str]:
    return [f"source:{source_name}:*", "tract-map:*", "scores:*"]

