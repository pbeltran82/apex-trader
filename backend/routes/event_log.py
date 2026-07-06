from fastapi import APIRouter

from backend.event_log import (
    get_events,
    build_timeline,
    clear_events,
)

router = APIRouter()


@router.get("/event-log")
def event_log(
    limit: int = 50,
    severity: str | None = None,
    category: str | None = None,
):
    return get_events(
        limit=limit,
        severity=severity,
        category=category,
    )


@router.get("/timeline")
def timeline(limit: int = 25):
    return build_timeline(limit)


@router.delete("/event-log")
def delete_event_log():
    return clear_events()