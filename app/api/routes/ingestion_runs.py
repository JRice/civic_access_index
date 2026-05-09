from uuid import UUID

from fastapi import APIRouter

router = APIRouter()


@router.get("/ingestion-runs")
def list_ingestion_runs() -> dict[str, object]:
    return {"results": []}


@router.get("/ingestion-runs/{run_id}")
def get_ingestion_run(run_id: UUID) -> dict[str, object]:
    return {"id": str(run_id)}


@router.get("/data-sources")
def list_data_sources() -> dict[str, object]:
    return {"results": []}

