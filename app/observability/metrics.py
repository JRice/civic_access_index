def ingestion_run_counter(status: str) -> dict[str, str]:
    return {"metric": "ingestion_runs_total", "status": status}

