def build_entity_search_query(q: str, entity_type: str = "all") -> dict:
    filters = [] if entity_type == "all" else [{"term": {"entity_type": entity_type}}]
    return {"query": {"bool": {"must": [{"multi_match": {"query": q, "fields": ["name^2", "geoid"]}}], "filter": filters}}}

