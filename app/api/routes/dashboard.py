"""
JSON API for the React dashboard (signals, AI, risk, exits).

The web UI lives in `frontend/` (Vite + React). In production, FastAPI serves
the built assets under /dashboard — see app/main.py.
"""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_event_store, get_signal_service
from app.dashboard.event_store import DashboardEventStore
from app.schemas.dashboard import DashboardSnapshot, PositionSnapshot
from app.services.signal_service import SignalService

router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard/events")
async def list_dashboard_events(
    store: Annotated[DashboardEventStore, Depends(get_event_store)],
    limit: int = 200,
) -> dict:
    events = await store.list_events(limit=min(limit, 500))
    return {"events": [e.model_dump(mode="json") for e in events]}


@router.get("/api/dashboard/snapshot", response_model=DashboardSnapshot)
async def dashboard_snapshot(
    signal_service: Annotated[SignalService, Depends(get_signal_service)],
) -> DashboardSnapshot:
    positions: list[PositionSnapshot] = []
    for p in signal_service.open_positions:
        positions.append(
            PositionSnapshot(
                symbol=p.symbol,
                side=p.side.value,
                entry_price=str(p.entry_price),
                quantity=str(p.quantity),
                stop_loss=str(p.stop_loss) if p.stop_loss is not None else None,
                take_profit=str(p.take_profit) if p.take_profit is not None else None,
            )
        )
    return DashboardSnapshot(
        capital=str(signal_service.capital),
        daily_pnl=str(signal_service.daily_pnl),
        open_positions=len(signal_service.open_positions),
        positions=positions,
    )
