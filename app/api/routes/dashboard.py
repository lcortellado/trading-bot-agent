"""
JSON API for the React dashboard (signals, AI, risk, exits).

The web UI lives in `frontend/` (Vite + React). In production, FastAPI serves
the built assets under /dashboard — see app/main.py.
"""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import SettingsDep, get_event_store, get_signal_service
from app.core.config import Settings
from app.dashboard.event_store import DashboardEventStore
from app.schemas.dashboard import DashboardPublicConfig, DashboardSnapshot, PositionSnapshot
from app.services.signal_service import SignalService

router = APIRouter(tags=["dashboard"])


def _public_config_from_settings(settings: Settings) -> DashboardPublicConfig:
    return DashboardPublicConfig(
        app_name=settings.app_name,
        app_version=settings.app_version,
        debug=settings.debug,
        trading_mode=settings.trading_mode.value,
        paper_initial_capital=settings.paper_initial_capital,
        max_position_size_pct=settings.max_position_size_pct,
        max_open_positions=settings.max_open_positions,
        max_daily_drawdown_pct=settings.max_daily_drawdown_pct,
        default_stop_loss_pct=settings.default_stop_loss_pct,
        default_take_profit_pct=settings.default_take_profit_pct,
        default_symbol=settings.default_symbol,
        default_timeframe=settings.default_timeframe,
        sma_short_period=settings.sma_short_period,
        sma_long_period=settings.sma_long_period,
        position_monitor_interval=settings.position_monitor_interval,
        dashboard_max_events=settings.dashboard_max_events,
        ai_enabled=settings.ai_enabled,
        ai_provider=settings.ai_provider,
        ai_model=settings.ai_model,
        openai_model=settings.openai_model,
        ai_timeout=settings.ai_timeout,
        ai_anthropic_key_configured=bool(settings.ai_api_key.strip()),
        ai_openai_key_configured=bool(settings.openai_api_key.strip()),
        auto_trading_enabled=settings.auto_trading_enabled,
        auto_trading_interval_seconds=settings.auto_trading_interval_seconds,
        auto_trading_symbols=settings.auto_trading_symbols,
        auto_trading_timeframe=settings.auto_trading_timeframe,
        auto_trading_strategy_names=settings.auto_trading_strategy_names,
        auto_trading_use_ai=settings.auto_trading_use_ai,
        auto_trading_skip_if_open=settings.auto_trading_skip_if_open,
        auto_trading_cooldown_seconds=settings.auto_trading_cooldown_seconds,
        auto_trading_candle_limit=settings.auto_trading_candle_limit,
    )


@router.get("/api/dashboard/config", response_model=DashboardPublicConfig)
async def dashboard_config(settings: SettingsDep) -> DashboardPublicConfig:
    """Exposes current non-secret configuration (read-only; values fixed at process start)."""
    return _public_config_from_settings(settings)


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
