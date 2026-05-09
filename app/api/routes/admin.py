from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import require_admin_token
from app.ingestion.registry import get_source_registry
from app.workers.tasks.index import reindex_search
from app.workers.tasks.ingest import run_source_ingestion
from app.workers.tasks.score import recompute_scores

router = APIRouter(dependencies=[Depends(require_admin_token)])


@router.post("/ingest/{source_name}")
def trigger_ingestion(source_name: str) -> dict[str, str]:
    if source_name not in get_source_registry():
        raise HTTPException(status_code=404, detail=f"Unknown source: {source_name}")
    task = run_source_ingestion.delay(source_name)
    return {"task_id": task.id, "source_name": source_name}


@router.post("/recompute-scores")
def trigger_score_recompute() -> dict[str, str]:
    task = recompute_scores.delay()
    return {"task_id": task.id}


@router.post("/reindex-search")
def trigger_search_reindex() -> dict[str, str]:
    task = reindex_search.delay()
    return {"task_id": task.id}
