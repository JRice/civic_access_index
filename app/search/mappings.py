TRACT_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "geoid": {"type": "keyword"},
            "name": {"type": "text"},
            "state_fips": {"type": "keyword"},
            "county_fips": {"type": "keyword"},
            "civic_access_index": {"type": "float"},
        }
    }
}

