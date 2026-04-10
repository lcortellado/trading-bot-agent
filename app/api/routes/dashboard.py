"""
JSON API for the React dashboard (signals, AI, risk, exits).

The web UI lives in `frontend/` (Vite + React). In production, FastAPI serves
the built assets under /dashboard — see app/main.py.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import (
    SettingsDep,
    get_event_store,
    get_market_data_service,
    get_signal_service,
    get_strategies,
)
from app.core.config import Settings
from app.dashboard.event_store import DashboardEventStore
from app.domain.enums import Timeframe
from app.schemas.dashboard import (
    ChartCandlePoint,
    ChartCrossPoint,
    ChartLinePoint,
    DashboardPublicConfig,
    DashboardSnapshot,
    PositionSnapshot,
    StrategyLabChartData,
    StrategyLabLaneRow,
    StrategyLabLeaderboardRow,
    StrategyLabSnapshot,
)
from app.services.market_data import MarketDataService
from app.services.signal_service import SignalService
from app.services.strategy_lab import StrategyLabRuntime, build_leaderboard
from app.strategies.base import Strategy

router = APIRouter(tags=["dashboard"])


def _parse_timeframe(raw: str) -> Timeframe:
    s = raw.strip().lower()
    for tf in Timeframe:
        if tf.value == s:
            return tf
    raise HTTPException(status_code=422, detail=f"Unsupported timeframe: {raw!r}")


def _rolling_sma(values: list[float], period: int) -> list[float | None]:
    out: list[float | None] = []
    if period <= 0:
        return [None for _ in values]
    acc = 0.0
    for i, v in enumerate(values):
        acc += v
        if i >= period:
            acc -= values[i - period]
        if i >= period - 1:
            out.append(acc / period)
        else:
            out.append(None)
    return out


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
        news_context_enabled=settings.news_context_enabled,
        news_cryptopanic_configured=bool(settings.cryptopanic_api_token.strip()),
        auto_trading_enabled=settings.auto_trading_enabled,
        auto_trading_interval_seconds=settings.auto_trading_interval_seconds,
        auto_trading_symbols=settings.auto_trading_symbols,
        auto_trading_timeframe=settings.auto_trading_timeframe,
        auto_trading_strategy_names=settings.auto_trading_strategy_names,
        auto_trading_use_ai=settings.auto_trading_use_ai,
        auto_trading_skip_if_open=settings.auto_trading_skip_if_open,
        auto_trading_cooldown_seconds=settings.auto_trading_cooldown_seconds,
        auto_trading_candle_limit=settings.auto_trading_candle_limit,
        strategy_lab_enabled=settings.strategy_lab_enabled,
        strategy_lab_interval_seconds=settings.strategy_lab_interval_seconds,
        strategy_lab_symbols=settings.strategy_lab_symbols,
        strategy_lab_timeframe=settings.strategy_lab_timeframe,
        strategy_lab_strategy_names=settings.strategy_lab_strategy_names,
        strategy_lab_candle_limit=settings.strategy_lab_candle_limit,
        strategy_lab_notional_usd=settings.strategy_lab_notional_usd,
        strategy_lab_tp_multiplier=settings.strategy_lab_tp_multiplier,
        strategy_lab_sl_min_pct=settings.strategy_lab_sl_min_pct,
        strategy_lab_sl_max_pct=settings.strategy_lab_sl_max_pct,
        strategy_lab_use_combined_signals=settings.strategy_lab_use_combined_signals,
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


@router.get("/api/dashboard/strategy-lab/chart", response_model=StrategyLabChartData)
async def strategy_lab_chart(
    settings: SettingsDep,
    strategies: Annotated[dict[str, Strategy], Depends(get_strategies)],
    market_data: Annotated[MarketDataService, Depends(get_market_data_service)],
    symbol: str = Query(default="BTCUSDT"),
    strategy_name: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    limit: int = Query(default=240, ge=60, le=1000),
) -> StrategyLabChartData:
    if not settings.strategy_lab_enabled:
        raise HTTPException(
            status_code=409,
            detail="Strategy lab is disabled (set STRATEGY_LAB_ENABLED=true and restart).",
        )
    chosen_name = strategy_name or settings.strategy_lab_strategy_names.split(",")[0].strip()
    strategy = strategies.get(chosen_name)
    if strategy is None:
        raise HTTPException(status_code=404, detail=f"Unknown strategy: {chosen_name!r}")
    # This chart endpoint currently supports SMA presets.
    cfg = getattr(strategy, "_cfg", None)
    short = getattr(cfg, "short_period", None)
    long = getattr(cfg, "long_period", None)
    if not isinstance(short, int) or not isinstance(long, int):
        raise HTTPException(
            status_code=422,
            detail=f"Strategy {chosen_name!r} does not expose SMA periods for chart overlay.",
        )
    tf = _parse_timeframe(timeframe or settings.strategy_lab_timeframe)
    try:
        candles = await market_data.get_candles(symbol.upper(), tf, limit=max(limit, long + 2))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Unable to load candles: {exc}")

    closes = [float(c.close) for c in candles]
    sma_short = _rolling_sma(closes, short)
    sma_long = _rolling_sma(closes, long)

    cross_points: list[ChartCrossPoint] = []
    for i in range(1, len(candles)):
        ps, pl = sma_short[i - 1], sma_long[i - 1]
        cs, cl = sma_short[i], sma_long[i]
        if ps is None or pl is None or cs is None or cl is None:
            continue
        ts = int(candles[i].open_time.timestamp())
        price = float(candles[i].close)
        if ps <= pl and cs > cl:
            cross_points.append(ChartCrossPoint(time=ts, side="buy", price=price))
        elif ps >= pl and cs < cl:
            cross_points.append(ChartCrossPoint(time=ts, side="sell", price=price))

    candle_points = [
        ChartCandlePoint(
            time=int(c.open_time.timestamp()),
            open=float(c.open),
            high=float(c.high),
            low=float(c.low),
            close=float(c.close),
        )
        for c in candles
    ]
    short_points = [
        ChartLinePoint(time=int(c.open_time.timestamp()), value=v)
        for c, v in zip(candles, sma_short)
        if v is not None
    ]
    long_points = [
        ChartLinePoint(time=int(c.open_time.timestamp()), value=v)
        for c, v in zip(candles, sma_long)
        if v is not None
    ]
    return StrategyLabChartData(
        symbol=symbol.upper(),
        timeframe=tf.value,
        strategy_name=chosen_name,
        sma_short_period=short,
        sma_long_period=long,
        candles=candle_points,
        sma_short=short_points,
        sma_long=long_points,
        crosses=cross_points,
    )


@router.get("/api/dashboard/strategy-lab", response_model=StrategyLabSnapshot)
async def strategy_lab_dashboard(
    settings: SettingsDep,
    request: Request,
    strategies: Annotated[dict[str, Strategy], Depends(get_strategies)],
) -> StrategyLabSnapshot:
    """
    Paper-only multi-strategy leaderboard: same candles, independent virtual positions per lane.
    Disabled unless STRATEGY_LAB_ENABLED=true at startup.
    """
    runtime: StrategyLabRuntime | None = getattr(request.app.state, "strategy_lab", None)
    if not settings.strategy_lab_enabled or runtime is None:
        return StrategyLabSnapshot(
            enabled=False,
            notional_usd=settings.strategy_lab_notional_usd,
            last_tick_at=None,
            tick_count=0,
            rows=[],
            leaderboard=[],
        )
    rows: list[StrategyLabLaneRow] = []
    for lane in sorted(runtime.all_lanes(), key=lambda l: (l.strategy_name, l.symbol)):
        desc = strategies.get(lane.strategy_name)
        mark_price = runtime.get_last_price(lane.symbol)
        entry_price = lane.entry_price
        position_notional = settings.strategy_lab_notional_usd if lane.in_position else None
        unrealized_pnl: str | None = None
        if lane.in_position and entry_price is not None and mark_price is not None and entry_price != 0:
            qty = settings.strategy_lab_notional_usd / float(entry_price)
            pnl = (float(mark_price) - float(entry_price)) * qty
            unrealized_pnl = f"{pnl:.6f}"
        rows.append(
            StrategyLabLaneRow(
                strategy_name=lane.strategy_name,
                description=desc.description if desc else (
                    "Combinada: mayoria BUY/SELL entre estrategias"
                    if lane.strategy_name == "combo_majority"
                    else ""
                ),
                symbol=lane.symbol,
                entry_price=str(entry_price) if entry_price is not None else None,
                mark_price=str(mark_price) if mark_price is not None else None,
                position_notional_usd=(
                    f"{position_notional:.2f}" if position_notional is not None else None
                ),
                unrealized_pnl=unrealized_pnl,
                realized_pnl=str(lane.realized_pnl),
                trades=lane.trades,
                wins=lane.wins,
                losses=lane.losses,
                in_position=lane.in_position,
                stop_loss=str(lane.stop_loss) if lane.stop_loss is not None else None,
                take_profit=str(lane.take_profit) if lane.take_profit is not None else None,
                last_action=lane.last_action,
                last_exit_reason=lane.last_exit_reason,
                last_confidence=lane.last_confidence,
            )
        )
    lb_raw = build_leaderboard(runtime, strategies)
    leaderboard = [StrategyLabLeaderboardRow(**x) for x in lb_raw]
    last_ts = runtime.last_tick_at.isoformat() if runtime.last_tick_at else None
    return StrategyLabSnapshot(
        enabled=True,
        notional_usd=settings.strategy_lab_notional_usd,
        last_tick_at=last_ts,
        tick_count=runtime.tick_count,
        rows=rows,
        leaderboard=leaderboard,
    )


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
