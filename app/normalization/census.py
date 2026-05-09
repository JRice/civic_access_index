def split_tract_geoid(geoid: str) -> tuple[str, str, str]:
    return geoid[:2], geoid[2:5], geoid[5:]

