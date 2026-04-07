"""
Simple Moving Average (SMA) Crossover Strategy.

Signal logic:
  - BUY  when short SMA crosses ABOVE long SMA (golden cross)
  - SELL when short SMA crosses BELOW long SMA (death cross)
  - HOLD otherwise

Decision note: TA-Lib was avoided because it requires compiled C libraries
that complicate Docker builds. SMA is calculated with pandas rolling mean,
which is a pure-Python dependency already needed for backtesting.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd

from app.core.logging import get_logger
from app.domain.enums import SignalAction, Timeframe
from app.domain.models import Candle, Signal
from app.strategies.base import Strategy, StrategyConfig

log = get_logger(__name__)


@dataclass
class SmaCrossoverConfig(StrategyConfig):
    short_period: int = 9
    long_period: int = 21

    def __post_init__(self) -> None:
        if self.short_period >= self.long_period:
            raise ValueError("short_period must be less than long_period")


class SmaCrossoverStrategy(Strategy):
    """
    SMA crossover using pandas rolling mean.
    Compares the last two bars to detect a cross event.
    """

    def __init__(self, config: SmaCrossoverConfig | None = None) -> None:
        cfg = config or SmaCrossoverConfig(
            name="sma_crossover",
            description="Golden/death cross on SMA short vs long",
        )
        super().__init__(cfg)
        self._cfg: SmaCrossoverConfig = cfg  # typed alias

    def min_candles_required(self) -> int:
        # Need long_period + 1 to detect a cross (current vs previous bar)
        return self._cfg.long_period + 1

    def generate_signal(self, candles: list[Candle]) -> Signal:
        self.validate_candles(candles)

        closes = pd.Series([float(c.close) for c in candles])
        short_sma = closes.rolling(self._cfg.short_period).mean()
        long_sma = closes.rolling(self._cfg.long_period).mean()

        prev_short = short_sma.iloc[-2]
        prev_long = long_sma.iloc[-2]
        curr_short = short_sma.iloc[-1]
        curr_long = long_sma.iloc[-1]

        latest_candle = candles[-1]
        symbol = latest_candle.symbol
        timeframe = latest_candle.timeframe
        price = latest_candle.close

        action, confidence, reason = self._evaluate_cross(
            prev_short, prev_long, curr_short, curr_long
        )

        log.debug(
            "SMA crossover | %s | short=%.4f long=%.4f | action=%s",
            symbol, curr_short, curr_long, action.value,
        )

        return Signal(
            symbol=symbol,
            timeframe=timeframe,
            action=action,
            strategy_name=self.name,
            confidence=confidence,
            reason=reason,
            price=price,
            timestamp=datetime.now(tz=timezone.utc),
            metadata={
                "sma_short": round(curr_short, 6),
                "sma_long": round(curr_long, 6),
                "short_period": self._cfg.short_period,
                "long_period": self._cfg.long_period,
                "candles_used": len(candles),
            },
        )

    def _evaluate_cross(
        self,
        prev_short: float,
        prev_long: float,
        curr_short: float,
        curr_long: float,
    ) -> tuple[SignalAction, float, str]:
        golden_cross = prev_short <= prev_long and curr_short > curr_long
        death_cross = prev_short >= prev_long and curr_short < curr_long

        if golden_cross:
            gap_pct = abs(curr_short - curr_long) / curr_long
            confidence = min(0.5 + gap_pct * 10, 0.9)
            reason = (
                f"Golden cross: SMA{self._cfg.short_period} ({curr_short:.4f}) "
                f"crossed above SMA{self._cfg.long_period} ({curr_long:.4f}). "
                f"Gap: {gap_pct:.4%}"
            )
            return SignalAction.BUY, round(confidence, 4), reason

        if death_cross:
            gap_pct = abs(curr_short - curr_long) / curr_long
            confidence = min(0.5 + gap_pct * 10, 0.9)
            reason = (
                f"Death cross: SMA{self._cfg.short_period} ({curr_short:.4f}) "
                f"crossed below SMA{self._cfg.long_period} ({curr_long:.4f}). "
                f"Gap: {gap_pct:.4%}"
            )
            return SignalAction.SELL, round(confidence, 4), reason

        spread = curr_short - curr_long
        reason = (
            f"No crossover detected. SMA{self._cfg.short_period}={curr_short:.4f}, "
            f"SMA{self._cfg.long_period}={curr_long:.4f}, spread={spread:.4f}"
        )
        return SignalAction.HOLD, 0.0, reason


def get_available_strategies() -> dict[str, Strategy]:
    """Registry of all available strategies. Add new strategies here."""
    return {
        "sma_crossover": SmaCrossoverStrategy(),
    }
