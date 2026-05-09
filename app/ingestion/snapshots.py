from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson

from app.config import get_settings


def write_local_snapshot(source_name: str, records: list[dict[str, Any]]) -> str:
    settings = get_settings()
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir = Path(settings.raw_snapshot_root) / source_name
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{timestamp}.json"
    snapshot_path.write_bytes(orjson.dumps(records, option=orjson.OPT_INDENT_2))
    return str(snapshot_path)

