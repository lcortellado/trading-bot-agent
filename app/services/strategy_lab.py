"""
Strategy lab — paper simulation of multiple strategies on the same candles.

Each (strategy, symbol) lane maintains its own virtual long-only position and realized PnL.
No exchange orders; independent from SignalService positions. Used to compare which
strategy configuration would have performed best under identical market data.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from app.core.config import Settings
from app.core.logging import get_logger
from app.dashboard.event_store import DashboardEventStore
from app.domain.enums import SignalAction
from app.schemas.dashboard import DashboardEventKind
from app.services.market_data import MarketDataService
from app.strategies.base import Strategy

log = get_logger(__name__)


@dataclass
class PaperLane:
    strategy_name: str
    symbol: str
    in_position: bool = False
    entry_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    realized_pnl: Decimal = Decimal("0")
    trades: int = 0
    wins: int = 0
    losses: int = 0
    last_action: str | None = None
    last_confidence: float | None = None
    last_reason: str = ""
    last_exit_reason: str | None = None


def _lane_key(strategy_name: str, symbol: str) -> str:
    return f"{strategy_name}::{symbol.upper()}"


def apply_signal_to_lane(
    lane: PaperLane,
    action: SignalAction,
    close: Decimal,
    notional: Decimal,
    confidence: float,
    reason: str,
) -> None:
    """Long-only paper rules: BUY opens, SELL closes; HOLD no-op; ignore conflicting signals."""
    lane.last_confidence = confidence if action != SignalAction.HOLD else None
    lane.last_reason = reason[:500] if reason else ""

    if action == SignalAction.HOLD:
        lane.last_action = "hold"
        return

    if action == SignalAction.BUY:
        if lane.in_position:
            lane.last_action = "buy_ignored_long"
            return
        lane.in_position = True
        lane.entry_price = close
        lane.stop_loss = None
        lane.take_profit = None
        lane.last_exit_reason = None
        lane.last_action = "buy"
        return

    if action == SignalAction.SELL:
        if not lane.in_position or lane.entry_price is None:
            lane.last_action = "sell_ignored_flat"
            return
        qty = notional / lane.entry_price
        pnl = (close - lane.entry_price) * qty
        lane.realized_pnl += pnl
        lane.trades += 1
        if pnl > 0:
            lane.wins += 1
        elif pnl < 0:
            lane.losses += 1
        lane.in_position = False
        lane.entry_price = None
        lane.stop_loss = None
        lane.take_profit = None
        lane.last_exit_reason = "signal_sell"
        lane.last_action = "sell"
        return


def close_lane_position(
    lane: PaperLane,
    *,
    exit_price: Decimal,
    reason: str,
    notional: Decimal,
) -> None:
    if not lane.in_position or lane.entry_price is None:
        return
    qty = notional / lane.entry_price
    pnl = (exit_price - lane.entry_price) * qty
    lane.realized_pnl += pnl
    lane.trades += 1
    if pnl > 0:
        lane.wins += 1
    elif pnl < 0:
        lane.losses += 1
    lane.in_position = False
    lane.entry_price = None
    lane.stop_loss = None
    lane.take_profit = None
    lane.last_action = reason
    lane.last_exit_reason = reason


def _estimate_sl_pct(
    closes: list[Decimal],
    *,
    min_pct: Decimal,
    max_pct: Decimal,
) -> Decimal:
    if len(closes) < 3:
        return min_pct
    rets: list[Decimal] = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        if prev == 0:
            continue
        r = abs((closes[i] - prev) / prev)
        rets.append(r)
    if not rets:
        return min_pct
    avg = sum(rets) / Decimal(len(rets))
    # Slightly conservative buffer over average absolute move.
    raw = avg * Decimal("1.5")
    return max(min_pct, min(max_pct, raw))


def _combined_majority_signal(signals: list[Signal]) -> SignalAction:
    buys = sum(1 for s in signals if s.action == SignalAction.BUY)
    sells = sum(1 for s in signals if s.action == SignalAction.SELL)
    if buys >= 2 and buys > sells:
        return SignalAction.BUY
    if sells >= 2 and sells > buys:
        return SignalAction.SELL
    return SignalAction.HOLD


def _parse_timeframe(raw: str):
    from app.domain.enums import Timeframe

    s = raw.strip().lower()
    for tf in Timeframe:
        if tf.value == s:
            return tf
    raise ValueError(f"Unsupported timeframe: {raw!r}")


@dataclass
class StrategyLabRuntime:
    """Mutable in-memory state for paper lanes (singleton on app.state)."""

    notional_usd: Decimal
    _lanes: dict[str, PaperLane] = field(default_factory=dict)
    _last_price_by_symbol: dict[str, Decimal] = field(default_factory=dict)
    last_tick_at: datetime | None = None
    tick_count: int = 0

    def ensure_lane(self, strategy_name: str, symbol: str) -> PaperLane:
        k = _lane_key(strategy_name, symbol)
        if k not in self._lanes:
            self._lanes[k] = PaperLane(strategy_name=strategy_name, symbol=symbol.upper())
        return self._lanes[k]

    def all_lanes(self) -> list[PaperLane]:
        return list(self._lanes.values())

    def set_last_price(self, symbol: str, price: Decimal) -> None:
        self._last_price_by_symbol[symbol.upper()] = price

    def get_last_price(self, symbol: str) -> Decimal | None:
        return self._last_price_by_symbol.get(symbol.upper())


class StrategyLabLoop:
    """
    Background task: fetch candles once per symbol, run each configured strategy,
    update paper lanes, optionally log a summary event.
    """

    def __init__(
        self,
        settings: Settings,
        market_data: MarketDataService,
        strategies: dict[str, Strategy],
        runtime: StrategyLabRuntime,
        event_store: DashboardEventStore | None = None,
    ) -> None:
        self._settings = settings
        self._market_data = market_data
        self._strategies = strategies
        self._runtime = runtime
        self._event_store = event_store
        self._timeframe = _parse_timeframe(settings.strategy_lab_timeframe)
        self._names = [
            n.strip() for n in settings.strategy_lab_strategy_names.split(",") if n.strip()
        ]
        self._symbols = [
            s.strip().upper() for s in settings.strategy_lab_symbols.split(",") if s.strip()
        ]
        self._notional = Decimal(str(settings.strategy_lab_notional_usd))
        self._tp_mult = Decimal(str(settings.strategy_lab_tp_multiplier))
        self._sl_min = Decimal(str(settings.strategy_lab_sl_min_pct))
        self._sl_max = Decimal(str(settings.strategy_lab_sl_max_pct))

    async def run(self) -> None:
        interval = self._settings.strategy_lab_interval_seconds
        log.info(
            "StrategyLabLoop started | interval=%ds | symbols=%s | strategies=%s",
            interval,
            self._symbols,
            self._names,
        )
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                log.info("StrategyLabLoop shutting down")
                raise
            except Exception as exc:  # noqa: BLE001
                log.error("StrategyLabLoop tick error: %s", exc, exc_info=True)
            await asyncio.sleep(interval)

    async def _tick(self) -> None:
        limit = self._settings.strategy_lab_candle_limit
        summaries: list[str] = []

        for symbol in self._symbols:
            try:
                candles = await self._market_data.get_candles(symbol, self._timeframe, limit=limit)
            except Exception as exc:  # noqa: BLE001
                log.warning("Strategy lab: no candles for %s: %s", symbol, exc)
                continue

            last_close = candles[-1].close
            last_high = candles[-1].high
            last_low = candles[-1].low
            self._runtime.set_last_price(symbol, last_close)
            closes = [c.close for c in candles]
            sl_pct = _estimate_sl_pct(closes, min_pct=self._sl_min, max_pct=self._sl_max)
            symbol_signals: list[Signal] = []

            for name in self._names:
                strat = self._strategies.get(name)
                if strat is None:
                    log.warning("Strategy lab: unknown strategy %r — skipped", name)
                    continue
                lane = self._runtime.ensure_lane(name, symbol)
                try:
                    sig = strat.generate_signal(candles)
                except Exception as exc:  # noqa: BLE001
                    log.warning("Strategy lab: %s failed for %s: %s", name, symbol, exc)
                    continue

                symbol_signals.append(sig)
                # If in position, evaluate TP/SL first on latest candle range.
                if lane.in_position and lane.stop_loss is not None and lane.take_profit is not None:
                    if last_low <= lane.stop_loss:
                        close_lane_position(
                            lane,
                            exit_price=lane.stop_loss,
                            reason="stop_loss",
                            notional=self._notional,
                        )
                    elif last_high >= lane.take_profit:
                        close_lane_position(
                            lane,
                            exit_price=lane.take_profit,
                            reason="take_profit",
                            notional=self._notional,
                        )
                apply_signal_to_lane(
                    lane,
                    sig.action,
                    last_close,
                    self._notional,
                    sig.confidence,
                    sig.reason,
                )
                if lane.in_position and lane.entry_price is not None and lane.stop_loss is None:
                    lane.stop_loss = lane.entry_price * (Decimal("1") - sl_pct)
                    lane.take_profit = lane.entry_price * (Decimal("1") + (sl_pct * self._tp_mult))
                if sig.action in (SignalAction.BUY, SignalAction.SELL):
                    summaries.append(f"{name}:{symbol}:{sig.action.value}")

            if self._settings.strategy_lab_use_combined_signals and symbol_signals:
                combo_name = "combo_majority"
                lane = self._runtime.ensure_lane(combo_name, symbol)
                if lane.in_position and lane.stop_loss is not None and lane.take_profit is not None:
                    if last_low <= lane.stop_loss:
                        close_lane_position(
                            lane,
                            exit_price=lane.stop_loss,
                            reason="stop_loss",
                            notional=self._notional,
                        )
                    elif last_high >= lane.take_profit:
                        close_lane_position(
                            lane,
                            exit_price=lane.take_profit,
                            reason="take_profit",
                            notional=self._notional,
                        )
                combo_action = _combined_majority_signal(symbol_signals)
                combo_conf = (
                    round(
                        sum(s.confidence for s in symbol_signals if s.action == combo_action)
                        / max(1, sum(1 for s in symbol_signals if s.action == combo_action)),
                        4,
                    )
                    if combo_action != SignalAction.HOLD
                    else 0.0
                )
                apply_signal_to_lane(
                    lane,
                    combo_action,
                    last_close,
                    self._notional,
                    combo_conf,
                    "Combinada por mayoria de señales",
                )
                if lane.in_position and lane.entry_price is not None and lane.stop_loss is None:
                    lane.stop_loss = lane.entry_price * (Decimal("1") - sl_pct)
                    lane.take_profit = lane.entry_price * (Decimal("1") + (sl_pct * self._tp_mult))
                if combo_action in (SignalAction.BUY, SignalAction.SELL):
                    summaries.append(f"{combo_name}:{symbol}:{combo_action.value}")

        self._runtime.last_tick_at = datetime.now(tz=timezone.utc)
        self._runtime.tick_count += 1
        if summaries:
            log.debug("Strategy lab signals: %s", summaries)
        await self._emit_summary(summaries)

    async def _emit_summary(self, summaries: list[str]) -> None:
        if self._event_store is None:
            return
        # One compact row per tick (avoid spamming one event per strategy×symbol)
        leaderboard = build_leaderboard(self._runtime, self._strategies)
        top = leaderboard[0] if leaderboard else None
        title = (
            f"Lab · mejor PnL: {top['strategy_name']} ({top['total_pnl']})"
            if top
            else "Lab · ciclo (sin señales BUY/SELL)"
        )
        await self._event_store.append_new(
            kind=DashboardEventKind.COMPARE,
            symbol=self._symbols[0] if self._symbols else "—",
            title=title[:120],
            detail={
                "signals_this_tick": summaries[:50],
                "leaderboard_top3": leaderboard[:3],
            },
        )


def build_leaderboard(
    runtime: StrategyLabRuntime,
    strategies: dict[str, Strategy],
) -> list[dict[str, str | int]]:
    """Aggregate realized PnL by strategy name across symbols; sort descending by PnL."""
    by_name: dict[str, dict[str, object]] = {}
    for lane in runtime.all_lanes():
        desc = strategies.get(lane.strategy_name)
        description = desc.description if desc else (
            "Combinada: mayoria BUY/SELL entre estrategias" if lane.strategy_name == "combo_majority" else ""
        )
        agg = by_name.setdefault(
            lane.strategy_name,
            {
                "strategy_name": lane.strategy_name,
                "description": description,
                "total_pnl": Decimal("0"),
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
            },
        )
        agg["total_pnl"] = agg["total_pnl"] + lane.realized_pnl  # type: ignore[operator,assignment]
        agg["total_trades"] = int(agg["total_trades"]) + lane.trades  # type: ignore[arg-type]
        agg["wins"] = int(agg["wins"]) + lane.wins  # type: ignore[arg-type]
        agg["losses"] = int(agg["losses"]) + lane.losses  # type: ignore[arg-type]

    rows: list[dict[str, str | int]] = []
    for _name, agg in by_name.items():
        pnl: Decimal = agg["total_pnl"]  # type: ignore[assignment]
        rows.append(
            {
                "strategy_name": str(agg["strategy_name"]),
                "description": str(agg["description"]),
                "total_pnl": format(pnl, "f"),
                "total_trades": int(agg["total_trades"]),
                "wins": int(agg["wins"]),
                "losses": int(agg["losses"]),
            }
        )
    rows.sort(key=lambda r: Decimal(str(r["total_pnl"])), reverse=True)
    return rows
