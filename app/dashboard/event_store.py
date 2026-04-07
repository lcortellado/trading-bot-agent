"""
Thread-safe async event ring buffer for dashboard feeds.

New events are prepended (newest first). Size is capped via maxlen on deque.
"""
import asyncio
import uuid
from collections import deque
from datetime import datetime, timezone

from app.schemas.dashboard import DashboardEvent, DashboardEventKind


class DashboardEventStore:
    def __init__(self, max_events: int = 500) -> None:
        self._max = max_events
        self._items: deque[DashboardEvent] = deque(maxlen=max_events)
        self._lock = asyncio.Lock()

    async def append(self, event: DashboardEvent) -> None:
        async with self._lock:
            self._items.appendleft(event)

    async def append_new(
        self,
        *,
        kind: DashboardEventKind,
        symbol: str,
        title: str,
        detail: dict | None = None,
    ) -> DashboardEvent:
        ev = DashboardEvent(
            id=str(uuid.uuid4())[:8],
            ts=datetime.now(tz=timezone.utc),
            kind=kind,
            symbol=symbol.upper(),
            title=title,
            detail=detail or {},
        )
        await self.append(ev)
        return ev

    async def list_events(self, limit: int = 200) -> list[DashboardEvent]:
        async with self._lock:
            return list(self._items)[:limit]
