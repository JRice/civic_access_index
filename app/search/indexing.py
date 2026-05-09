def tract_document(tract: dict) -> dict:
    return {
        "entity_type": "tract",
        "geoid": tract.get("geoid"),
        "name": tract.get("name"),
        "state_fips": tract.get("state_fips"),
        "county_fips": tract.get("county_fips"),
        "civic_access_index": tract.get("civic_access_index"),
    }

