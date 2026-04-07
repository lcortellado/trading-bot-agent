"""
PositionMonitor — async background task that watches open positions for SL/TP exits.

Design:
- Runs as an asyncio.Task started in the FastAPI lifespan.
- Shares the singleton SignalService instance to read/mutate in-memory position state.
- On SL/TP breach: places a MARKET close order (simulated in paper mode) and
  calls SignalService.close_position() to update state + daily PnL.
- Interface is ready for a future repository: replace direct signal_service calls
  with repository.get_open_positions() / repository.close_position().

Logging: every exit decision uses DecisionLogger with a mandatory reason.
"""
import asyncio
from decimal import Decimal

from app.core.logging import DecisionLogger, get_logger
from app.domain.enums import OrderSide, OrderType
from app.domain.models import Position
from app.dashboard.event_store import DashboardEventStore
from app.exchange.base import ExchangeClient
from app.schemas.dashboard import DashboardEventKind
from app.services.signal_service import SignalService

log = get_logger(__name__)
decision_log = DecisionLogger(log)


class PositionMonitor:
    """
    Polls open positions at a fixed interval and closes them when SL or TP is hit.

    Usage (in FastAPI lifespan):
        task = asyncio.create_task(monitor.run())
        ...
        task.cancel(); await task
    """

    def __init__(
        self,
        signal_service: SignalService,
        exchange: ExchangeClient,
        interval_seconds: int = 30,
        event_store: DashboardEventStore | None = None,
    ) -> None:
        self._signal_service = signal_service
        self._exchange = exchange
        self._interval = interval_seconds
        self._event_store = event_store

    async def run(self) -> None:
        log.info("PositionMonitor started | check_interval=%ds", self._interval)
        while True:
            try:
                await self._check_all_positions()
            except asyncio.CancelledError:
                log.info("PositionMonitor shutting down gracefully")
                return
            except Exception as exc:  # noqa: BLE001
                log.error("PositionMonitor uncaught error (will retry): %s", exc)
            await asyncio.sleep(self._interval)

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _check_all_positions(self) -> None:
        positions = list(self._signal_service.open_positions)  # snapshot to avoid mutation during iteration
        if not positions:
            return

        log.debug("PositionMonitor checking %d open position(s)", len(positions))
        for position in positions:
            await self._evaluate_position(position)

    async def _evaluate_position(self, position: Position) -> None:
        try:
            current_price = await self._exchange.get_ticker_price(position.symbol)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "PositionMonitor: cannot fetch price for %s — skipping this cycle: %s",
                position.symbol,
                exc,
            )
            return

        should_exit, reason = _check_exit_conditions(position, current_price)
        if should_exit:
            await self._close_position(position, current_price, reason)

    async def _close_position(
        self, position: Position, current_price: Decimal, reason: str
    ) -> None:
        close_side = OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY
        try:
            order = await self._exchange.place_order(
                symbol=position.symbol,
                side=close_side,
                order_type=OrderType.MARKET,
                quantity=position.quantity,
                price=current_price,
            )
            pnl = position.unrealized_pnl(current_price)
            await self._signal_service.close_position(position, pnl)
            decision_log.skip(  # "skip" semantics = exit / no more action
                position.symbol,
                reason,
                order_id=str(order.order_id),
                realized_pnl=str(pnl),
                close_price=str(current_price),
                entry_price=str(position.entry_price),
            )
            if self._event_store is not None:
                await self._event_store.append_new(
                    kind=DashboardEventKind.POSITION,
                    symbol=position.symbol,
                    title=f"Exit · {reason[:72]}",
                    detail={
                        "order_id": str(order.order_id),
                        "side": position.side.value,
                        "realized_pnl": str(pnl),
                        "close_price": str(current_price),
                        "entry_price": str(position.entry_price),
                    },
                )
        except Exception as exc:  # noqa: BLE001
            log.error(
                "PositionMonitor: failed to close position %s: %s",
                position.symbol,
                exc,
            )


# ── Pure helpers ───────────────────────────────────────────────────────────────


def _check_exit_conditions(
    position: Position, current_price: Decimal
) -> tuple[bool, str]:
    """Return (should_exit, reason). Pure function — no side effects."""
    if position.side == OrderSide.BUY:
        if position.stop_loss and current_price <= position.stop_loss:
            return (
                True,
                f"Stop-loss triggered: price {current_price} <= SL {position.stop_loss}",
            )
        if position.take_profit and current_price >= position.take_profit:
            return (
                True,
                f"Take-profit reached: price {current_price} >= TP {position.take_profit}",
            )
    else:  # SHORT
        if position.stop_loss and current_price >= position.stop_loss:
            return (
                True,
                f"Stop-loss triggered: price {current_price} >= SL {position.stop_loss}",
            )
        if position.take_profit and current_price <= position.take_profit:
            return (
                True,
                f"Take-profit reached: price {current_price} <= TP {position.take_profit}",
            )
    return False, ""
