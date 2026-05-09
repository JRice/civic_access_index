def tract_map_key(state: str | None, county: str | None, score_type: str) -> str:
    return f"tract-map:{state or 'all'}:{county or 'all'}:{score_type}"

