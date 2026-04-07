"""
Risk Manager — validates signals before any order is placed.

Responsibility: enforce capital protection rules.
This module knows nothing about strategies or exchange internals.
It answers one question: "Is it safe to act on this signal?"

Rules enforced:
  1. Minimum confidence threshold
  2. Maximum open positions
  3. Maximum position size (% of capital)
  4. Daily drawdown limit
  5. Stop-loss / take-profit attachment
"""
from dataclasses import dataclass
from decimal import Decimal

from app.core.config import Settings
from app.core.logging import DecisionLogger, get_logger
from app.domain.enums import OrderSide, SignalAction
from app.domain.models import Position, Signal

log = get_logger(__name__)
decision_log = DecisionLogger(log)


@dataclass
class RiskCheckResult:
    approved: bool
    reason: str
    suggested_quantity: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None


class RiskManager:
    """
    Stateless risk evaluator.
    Caller provides current state (capital, positions, drawdown).
    """

    MIN_CONFIDENCE = 0.4  # Signals below this are always skipped

    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def evaluate(
        self,
        signal: Signal,
        available_capital: Decimal,
        open_positions: list[Position],
        daily_pnl: Decimal,
    ) -> RiskCheckResult:
        """
        Run all risk checks against a candidate signal.

        Args:
            signal:            The strategy signal to evaluate.
            available_capital: Liquid capital available for new positions.
            open_positions:    Currently open positions.
            daily_pnl:         Realized + unrealized PnL for today (negative = loss).

        Returns:
            RiskCheckResult with approved flag and explanation.
        """
        # 1. HOLD signals are never acted on
        if signal.action == SignalAction.HOLD:
            decision_log.skip(signal.symbol, "signal action is HOLD — no trade needed")
            return RiskCheckResult(approved=False, reason="Signal action is HOLD")

        # 2. Minimum confidence
        if signal.confidence < self.MIN_CONFIDENCE:
            reason = (
                f"Confidence {signal.confidence:.2%} is below minimum "
                f"{self.MIN_CONFIDENCE:.2%}"
            )
            decision_log.skip(signal.symbol, reason, confidence=signal.confidence)
            return RiskCheckResult(approved=False, reason=reason)

        # 3. Max open positions
        if len(open_positions) >= self._s.max_open_positions:
            reason = (
                f"Max open positions reached: {len(open_positions)}/{self._s.max_open_positions}"
            )
            decision_log.skip(signal.symbol, reason)
            return RiskCheckResult(approved=False, reason=reason)

        # 4. Daily drawdown limit
        if available_capital > 0:
            total_capital = available_capital  # simplified: no tracking of locked capital here
            drawdown_pct = float(-daily_pnl / total_capital) if daily_pnl < 0 else 0.0
            if drawdown_pct >= self._s.max_daily_drawdown_pct:
                reason = (
                    f"Daily drawdown {drawdown_pct:.2%} exceeds limit "
                    f"{self._s.max_daily_drawdown_pct:.2%}"
                )
                decision_log.skip(signal.symbol, reason, drawdown_pct=f"{drawdown_pct:.2%}")
                return RiskCheckResult(approved=False, reason=reason)

        # 5. Position sizing
        quantity, stop_loss, take_profit = self._calculate_position(
            signal.price, available_capital
        )

        if quantity <= 0:
            reason = f"Calculated quantity {quantity} is too small to trade"
            decision_log.skip(signal.symbol, reason, capital=str(available_capital))
            return RiskCheckResult(approved=False, reason=reason)

        decision_log.enter(
            signal.symbol,
            signal.reason,
            action=signal.action.value,
            confidence=f"{signal.confidence:.2%}",
            quantity=str(quantity),
            stop_loss=str(stop_loss),
            take_profit=str(take_profit),
        )

        return RiskCheckResult(
            approved=True,
            reason=f"All risk checks passed. {signal.reason}",
            suggested_quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def _calculate_position(
        self,
        price: Decimal,
        available_capital: Decimal,
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Fixed fractional position sizing."""
        max_notional = available_capital * Decimal(str(self._s.max_position_size_pct))
        quantity = (max_notional / price).quantize(Decimal("0.00001"))

        sl_distance = price * Decimal(str(self._s.default_stop_loss_pct))
        tp_distance = price * Decimal(str(self._s.default_take_profit_pct))
        stop_loss = (price - sl_distance).quantize(Decimal("0.01"))
        take_profit = (price + tp_distance).quantize(Decimal("0.01"))

        return quantity, stop_loss, take_profit
