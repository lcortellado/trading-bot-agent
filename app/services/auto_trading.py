"""
Automated trading loop — periodic multi-strategy scan, optional AI gate, then risk + order.

Similar in spirit to scheduler-style bots (e.g. 3Commas): runs in the background,
fetches candles, runs each configured strategy, aggregates non-HOLD signals, then
either calls the AI agent (multi-signal bundle) or the strongest signal directly.

Safety:
- Skips symbols with an open position when AUTO_TRADING_SKIP_IF_OPEN=true
- Per-symbol cooldown after a successful order (AUTO_TRADING_COOLDOWN_SECONDS)
- Paper/testnet only — same as the rest of the app
"""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from app.agents.schemas import MarketContext
from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.enums import SignalAction, Timeframe
from app.domain.models import Signal
from app.schemas.agent import AgentSignalRequest
from app.schemas.dashboard import DashboardEventKind
from app.schemas.signal import SignalRequest
from app.services.market_data import MarketDataService
from app.strategies.base import Strategy

if TYPE_CHECKING:
    from app.agents.agent_service import AgentService
    from app.dashboard.event_store import DashboardEventStore
    from app.services.signal_service import SignalService

log = get_logger(__name__)


def _parse_timeframe(raw: str) -> Timeframe:
    s = raw.strip().lower()
    for tf in Timeframe:
        if tf.value == s:
            return tf
    raise ValueError(f"Unsupported timeframe: {raw!r}")


def _signal_to_request(s: Signal) -> SignalRequest:
    return SignalRequest(
        symbol=s.symbol,
        timeframe=s.timeframe,
        action=s.action,
        strategy_name=s.strategy_name,
        confidence=s.confidence,
        reason=s.reason,
        price=s.price,
        metadata={**s.metadata, "auto_trading": True},
    )


def _pick_primary(signals: list[Signal]) -> Signal:
    """Highest-confidence BUY/SELL; tie-breaker: first in list."""
    actionable = [s for s in signals if s.action in (SignalAction.BUY, SignalAction.SELL)]
    if not actionable:
        raise ValueError("No actionable signals")
    return max(actionable, key=lambda s: s.confidence)


class AutoTradingLoop:
    """
    Background asyncio task: sleep → for each symbol run strategies → AI or direct → order.
    """

    def __init__(
        self,
        settings: Settings,
        market_data: MarketDataService,
        strategies: dict[str, Strategy],
        agent_service: AgentService,
        signal_service: SignalService,
        event_store: DashboardEventStore | None = None,
    ) -> None:
        self._settings = settings
        self._market_data = market_data
        self._strategies = strategies
        self._agent = agent_service
        self._signals = signal_service
        self._event_store = event_store
        self._timeframe = _parse_timeframe(settings.auto_trading_timeframe)
        self._strategy_names = [
            n.strip() for n in settings.auto_trading_strategy_names.split(",") if n.strip()
        ]
        self._symbols = [
            s.strip().upper() for s in settings.auto_trading_symbols.split(",") if s.strip()
        ]
        # Per symbol: monotonic timestamp after last *filled* auto order
        self._last_order_mono: dict[str, float] = {}

    async def run(self) -> None:
        interval = self._settings.auto_trading_interval_seconds
        log.info(
            "AutoTradingLoop started | interval=%ds | symbols=%s | strategies=%s | use_ai=%s",
            interval,
            self._symbols,
            self._strategy_names,
            self._settings.auto_trading_use_ai,
        )
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                log.info("AutoTradingLoop shutting down")
                raise
            except Exception as exc:  # noqa: BLE001
                log.error("AutoTradingLoop tick error: %s", exc, exc_info=True)
            await asyncio.sleep(interval)

    async def _tick(self) -> None:
        for symbol in self._symbols:
            await self._process_symbol(symbol)

    async def _process_symbol(self, symbol: str) -> None:
        if self._settings.auto_trading_skip_if_open and self._has_open_position(symbol):
            log.debug("Auto-trading skip %s — open position exists", symbol)
            return

        cd = self._settings.auto_trading_cooldown_seconds
        if cd > 0 and symbol in self._last_order_mono:
            elapsed = time.monotonic() - self._last_order_mono[symbol]
            if elapsed < cd:
                log.debug(
                    "Auto-trading skip %s — cooldown %.0fs remaining",
                    symbol,
                    cd - elapsed,
                )
                return

        collected: list[Signal] = []
        limit = self._settings.auto_trading_candle_limit

        try:
            candles = await self._market_data.get_candles(
                symbol, self._timeframe, limit=limit
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Auto-trading: no candles for %s: %s", symbol, exc)
            return

        for name in self._strategy_names:
            strat = self._strategies.get(name)
            if strat is None:
                log.warning("Auto-trading: unknown strategy %r — skipped", name)
                continue
            try:
                sig = strat.generate_signal(candles)
            except Exception as exc:  # noqa: BLE001
                log.warning("Auto-trading: strategy %s failed for %s: %s", name, symbol, exc)
                continue
            if sig.action == SignalAction.HOLD:
                continue
            collected.append(sig)

        if not collected:
            log.debug("Auto-trading: %s — no actionable signals this cycle", symbol)
            return

        primary = _pick_primary(collected)
        primary_req = _signal_to_request(primary)
        all_req = [_signal_to_request(s) for s in collected]

        if self._settings.auto_trading_use_ai:
            req = AgentSignalRequest(
                primary_signal=primary_req,
                signals=all_req,
                market_context=MarketContext(trend=None, volume_ratio=None),
            )
            resp = await self._agent.process(req)
            if resp.order_executed:
                self._last_order_mono[symbol] = time.monotonic()
            await self._emit_auto_event(
                symbol,
                "AI cycle",
                {
                    "agent_decision": resp.agent_decision.value,
                    "order_executed": resp.order_executed,
                    "strategies": [s.strategy_name for s in collected],
                },
            )
            return

        # Direct: strongest signal only — still passes through RiskManager
        out = await self._signals.process_signal(primary_req)
        if out.accepted:
            self._last_order_mono[symbol] = time.monotonic()
        await self._emit_auto_event(
            symbol,
            "Direct signal",
            {
                "accepted": out.accepted,
                "strategy": primary.strategy_name,
                "reason": out.reason[:200],
            },
        )

    def _has_open_position(self, symbol: str) -> bool:
        return any(p.symbol == symbol for p in self._signals.open_positions)

    async def _emit_auto_event(self, symbol: str, title: str, detail: dict) -> None:
        if self._event_store is None:
            return
        await self._event_store.append_new(
            kind=DashboardEventKind.AUTO,
            symbol=symbol,
            title=f"Auto · {title}",
            detail=detail,
        )

