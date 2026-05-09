from typing import Any


def require_fields(record: dict[str, Any], fields: list[str]) -> list[str]:
    return [field for field in fields if record.get(field) in (None, "")]

