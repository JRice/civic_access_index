from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.schemas import DataSourceRead, IngestionRunRead
from app.db.models.data_source import DataSource
from app.db.models.ingestion_run import IngestionRun
from app.ingestion.lifecycle import ensure_data_source
from app.ingestion.registry import get_source_registry

router = APIRouter()
DB_DEPENDENCY = Depends(get_db)


@router.get("/ingestion-runs")
def list_ingestion_runs(
    db: Session = DB_DEPENDENCY,
    limit: int = 50,
) -> dict[str, list[IngestionRunRead]]:
    runs = (
        db.query(IngestionRun)
        .order_by(IngestionRun.started_at.desc().nullslast(), IngestionRun.id.desc())
        .limit(min(limit, 200))
        .all()
    )
    return {"results": [IngestionRunRead.model_validate(run) for run in runs]}


@router.get("/ingestion-runs/{run_id}")
def get_ingestion_run(run_id: UUID, db: Session = DB_DEPENDENCY) -> IngestionRunRead:
    run = db.get(IngestionRun, str(run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Ingestion run not found.")
    return IngestionRunRead.model_validate(run)


@router.get("/data-sources")
def list_data_sources(db: Session = DB_DEPENDENCY) -> dict[str, list[DataSourceRead]]:
    for adapter_class in get_source_registry().values():
        ensure_data_source(db, adapter_class())
    sources = db.query(DataSource).order_by(DataSource.name.asc()).all()
    return {"results": [DataSourceRead.model_validate(source) for source in sources]}
