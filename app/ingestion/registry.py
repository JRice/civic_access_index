from app.ingestion.base import SourceAdapter
from app.ingestion.sources.census_acs import CensusACSAdapter
from app.ingestion.sources.census_tiger import CensusTigerAdapter
from app.ingestion.sources.cms_providers import CMSProvidersAdapter
from app.ingestion.sources.osm_overpass import OSMOverpassAdapter
from app.ingestion.sources.usda_food_access import USDAFoodAccessAdapter


def get_source_registry() -> dict[str, type[SourceAdapter]]:
    adapters: list[type[SourceAdapter]] = [
        CensusACSAdapter,
        CensusTigerAdapter,
        USDAFoodAccessAdapter,
        CMSProvidersAdapter,
        OSMOverpassAdapter,
    ]
    return {adapter.name: adapter for adapter in adapters}

