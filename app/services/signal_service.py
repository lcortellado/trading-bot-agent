"""
Signal service — orchestrates the full signal → risk check → order flow.

This is the only service that touches both strategies and risk management.
FastAPI routes call this service; they never call strategies or risk manager directly.
"""
from __future__ import annotations

from decimal import Decimal

from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.models import Order, Position, Signal
from app.dashboard.event_store import DashboardEventStore
from app.domain.enums import OrderSide, OrderType, SignalAction
from app.exchange.base import ExchangeClient
from app.risk_management.risk_manager import RiskManager, RiskCheckResult
from app.schemas.dashboard import DashboardEventKind
from app.schemas.signal import SignalRequest, SignalResponse
from app.strategies.base import Strategy

log = get_logger(__name__)


class SignalService:
    """
    Processes inbound signals (from external webhooks or internal strategies).

    Flow:
      1. Convert schema → domain Signal
      2. Run risk checks
      3. If approved → place order via exchange client
      4. Return structured response
    """

    def __init__(
        self,
        exchange: ExchangeClient,
        risk_manager: RiskManager,
        settings: Settings,
        event_store: DashboardEventStore | None = None,
    ) -> None:
        self._exchange = exchange
        self._risk = risk_manager
        self._settings = settings
        self._event_store = event_store
        # In-memory state for paper trading (replace with DB repository later)
        self._open_positions: list[Position] = []
        self._daily_pnl: Decimal = Decimal("0")
        self._capital: Decimal = Decimal(str(settings.paper_initial_capital))

    # ── Read-only accessors (used by AgentService and PositionMonitor) ─────────

    @property
    def open_positions(self) -> list[Position]:
        return self._open_positions

    @property
    def capital(self) -> Decimal:
        return self._capital

    @property
    def daily_pnl(self) -> Decimal:
        return self._daily_pnl

    async def process_signal(self, request: SignalRequest) -> SignalResponse:
        """Main entry point for signal processing."""
        signal = self._to_domain_signal(request)
        risk_result = self._risk.evaluate(
            signal=signal,
            available_capital=self._capital,
            open_positions=self._open_positions,
            daily_pnl=self._daily_pnl,
        )

        if not risk_result.approved:
            resp = SignalResponse(
                accepted=False,
                signal_action=signal.action,
                symbol=signal.symbol,
                reason=risk_result.reason,
                risk_check_passed=False,
            )
            await self._emit_signal_dashboard(request, resp)
            return resp

        order = await self._place_order(signal, risk_result)

        resp = SignalResponse(
            accepted=True,
            signal_action=signal.action,
            symbol=signal.symbol,
            reason=risk_result.reason,
            risk_check_passed=True,
            order_id=order.order_id,
        )
        await self._emit_signal_dashboard(request, resp)
        return resp

    async def close_position(self, position: Position, realized_pnl: Decimal) -> None:
        """
        Remove a position from open tracking, update daily PnL, and restore locked notional.
        Called by PositionMonitor when SL/TP is hit.
        Future: swap list mutation for a repository call.
        """
        self._open_positions = [p for p in self._open_positions if p is not position]
        self._daily_pnl += realized_pnl
        # Return margin/notional locked at entry plus realized PnL (≈ exit proceeds in USDT terms)
        self._capital += position.entry_price * position.quantity + realized_pnl
        log.info(
            "Position closed | symbol=%s | realized_pnl=%s | daily_pnl=%s",
            position.symbol,
            realized_pnl,
            self._daily_pnl,
        )

    async def run_strategy_signal(
        self,
        strategy: Strategy,
        symbol: str,
        timeframe_str: str,
        candles: list,
    ) -> Signal:
        """Generate a signal from a strategy (used by /strategy endpoint)."""
        return strategy.generate_signal(candles)

    def _to_domain_signal(self, req: SignalRequest) -> Signal:
        from app.domain.models import Signal as DomainSignal

        return DomainSignal(
            symbol=req.symbol,
            timeframe=req.timeframe,
            action=req.action,
            strategy_name=req.strategy_name,
            confidence=req.confidence,
            reason=req.reason,
            price=req.price,
            size_multiplier=req.size_multiplier,
            metadata=req.metadata,
        )

    async def _place_order(self, signal: Signal, risk: RiskCheckResult) -> Order:
        side = OrderSide.BUY if signal.action == SignalAction.BUY else OrderSide.SELL
        order = await self._exchange.place_order(
            symbol=signal.symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=risk.suggested_quantity,  # type: ignore[arg-type]
            price=signal.price,
        )
        log.info(
            "Order placed | id=%s | %s %s qty=%s",
            order.order_id,
            side.value,
            signal.symbol,
            risk.suggested_quantity,
        )
        # Track the opened position (in-memory; future: persist via repository)
        position = Position(
            symbol=signal.symbol,
            side=side,
            entry_price=signal.price,
            quantity=risk.suggested_quantity,  # type: ignore[arg-type]
            stop_loss=risk.stop_loss,
            take_profit=risk.take_profit,
        )
        self._open_positions.append(position)
        locked = signal.price * risk.suggested_quantity  # type: ignore[operator]
        self._capital -= locked
        return order

    async def _emit_signal_dashboard(
        self, request: SignalRequest, response: SignalResponse
    ) -> None:
        if self._event_store is None:
            return
        src = "agent" if request.metadata.get("agent_decision") else "direct"
        title = (
            f"Risk OK · order {response.order_id}"
            if response.accepted
            else f"Risk rejected · {response.reason[:100]}"
        )
        await self._event_store.append_new(
            kind=DashboardEventKind.SIGNAL,
            symbol=response.symbol,
            title=title,
            detail={
                "source": src,
                "action": response.signal_action.value,
                "strategy": request.strategy_name,
                "confidence": request.confidence,
                "size_multiplier": request.size_multiplier,
                "risk_check_passed": response.risk_check_passed,
                "reason": response.reason,
                "order_id": response.order_id,
            },
        )
