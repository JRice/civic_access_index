from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, amenities, health, ingestion_runs, scores, search, tracts
from app.config import get_settings
from app.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Geospatial APIs for civic access metrics and ingestion operations.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(tracts.router, prefix="/api", tags=["tracts"])
    app.include_router(amenities.router, prefix="/api", tags=["amenities"])
    app.include_router(scores.router, prefix="/api", tags=["scores"])
    app.include_router(search.router, prefix="/api", tags=["search"])
    app.include_router(ingestion_runs.router, prefix="/api", tags=["ingestion"])
    app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
    return app


app = create_app()

