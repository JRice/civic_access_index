from typing import Literal

from fastapi import APIRouter

router = APIRouter()


@router.get("/search")
def search(q: str, type: Literal["tract", "amenity", "provider", "all"] = "all") -> dict[str, object]:
    return {"q": q, "type": type, "results": []}

