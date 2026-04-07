"""Shared pytest fixtures."""
import pytest
from decimal import Decimal
from datetime import datetime, timezone

from app.core.config import Settings
from app.domain.enums import Timeframe, TradingMode
from app.domain.models import Candle


def make_settings(**overrides) -> Settings:
    defaults = dict(
        trading_mode=TradingMode.PAPER,
        binance_api_key="test_key",
        binance_secret_key="test_secret",
        paper_initial_capital=10_000.0,
        max_position_size_pct=0.02,
        max_open_positions=5,
        max_daily_drawdown_pct=0.05,
        default_stop_loss_pct=0.02,
        default_take_profit_pct=0.04,
        sma_short_period=3,
        sma_long_period=5,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def make_candle(
    close: float,
    symbol: str = "BTCUSDT",
    timeframe: Timeframe = Timeframe.H1,
    open_: float | None = None,
) -> Candle:
    now = datetime.now(tz=timezone.utc)
    c = Decimal(str(close))
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        open_time=now,
        open=Decimal(str(open_)) if open_ else c,
        high=c * Decimal("1.01"),
        low=c * Decimal("0.99"),
        close=c,
        volume=Decimal("100"),
        close_time=now,
    )


def make_candle_series(closes: list[float], **kwargs) -> list[Candle]:
    return [make_candle(c, **kwargs) for c in closes]
