from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models.data_source import DataSource
from app.db.models.ingestion_run import IngestionRun
from app.ingestion.base import SourceAdapter


def ensure_data_source(db: Session, adapter: SourceAdapter) -> DataSource:
    source = db.query(DataSource).filter(DataSource.name == adapter.name).one_or_none()
    if source is None:
        source = DataSource(name=adapter.name)
    source.source_type = adapter.source_type
    source.homepage_url = getattr(adapter, "homepage_url", None)
    source.api_url = getattr(adapter, "api_url", None)
    source.license = getattr(adapter, "license", None)
    source.refresh_strategy = getattr(adapter, "refresh_strategy", None)
    source.enabled = True
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def create_ingestion_run(db: Session, data_source_id: str | None = None) -> IngestionRun:
    run = IngestionRun(
        data_source_id=data_source_id,
        status="running",
        started_at=datetime.now(UTC),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def mark_ingestion_run_succeeded(
    db: Session,
    run: IngestionRun,
    *,
    records_seen: int,
    records_created: int,
    records_updated: int,
    records_rejected: int,
    raw_snapshot_uri: str | None,
    metadata_json: dict | None = None,
) -> IngestionRun:
    run.status = "succeeded" if records_rejected == 0 else "partial"
    run.completed_at = datetime.now(UTC)
    run.records_seen = records_seen
    run.records_created = records_created
    run.records_updated = records_updated
    run.records_rejected = records_rejected
    run.raw_snapshot_uri = raw_snapshot_uri
    run.metadata_json = metadata_json
    db.add(run)
    if run.data_source is not None:
        run.data_source.last_success_at = run.completed_at
        db.add(run.data_source)
    db.commit()
    db.refresh(run)
    return run


def mark_ingestion_run_failed(db: Session, run: IngestionRun, error_summary: str) -> IngestionRun:
    run.status = "failed"
    run.completed_at = datetime.now(UTC)
    run.error_summary = error_summary
    db.add(run)
    if run.data_source is not None:
        run.data_source.last_failure_at = run.completed_at
        db.add(run.data_source)
    db.commit()
    db.refresh(run)
    return run
