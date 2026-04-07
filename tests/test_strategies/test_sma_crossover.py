"""Tests for SMA Crossover strategy."""
import pytest
from decimal import Decimal

from app.domain.enums import SignalAction
from app.strategies.sma_crossover import SmaCrossoverConfig, SmaCrossoverStrategy
from tests.conftest import make_candle_series


@pytest.fixture
def strategy() -> SmaCrossoverStrategy:
    cfg = SmaCrossoverConfig(
        name="sma_crossover",
        description="test",
        short_period=3,
        long_period=5,
    )
    return SmaCrossoverStrategy(config=cfg)


def test_min_candles_required(strategy: SmaCrossoverStrategy) -> None:
    assert strategy.min_candles_required() == 6  # long_period + 1


def test_raises_on_insufficient_candles(strategy: SmaCrossoverStrategy) -> None:
    candles = make_candle_series([100.0, 101.0, 102.0])
    with pytest.raises(ValueError, match="requires at least"):
        strategy.generate_signal(candles)


def test_golden_cross_returns_buy(strategy: SmaCrossoverStrategy) -> None:
    # short SMA crosses above long SMA on the last bar
    # Prices trend down then sharply up so short crosses long
    closes = [100.0, 99.0, 98.0, 97.0, 98.0, 110.0]
    candles = make_candle_series(closes)
    signal = strategy.generate_signal(candles)
    assert signal.action == SignalAction.BUY
    assert signal.confidence > 0
    assert signal.reason != ""


def test_death_cross_returns_sell(strategy: SmaCrossoverStrategy) -> None:
    # Prices trend up then sharply down
    closes = [100.0, 101.0, 102.0, 103.0, 102.0, 90.0]
    candles = make_candle_series(closes)
    signal = strategy.generate_signal(candles)
    assert signal.action == SignalAction.SELL
    assert signal.confidence > 0


def test_no_cross_returns_hold(strategy: SmaCrossoverStrategy) -> None:
    # Flat prices — no crossover
    closes = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    candles = make_candle_series(closes)
    signal = strategy.generate_signal(candles)
    assert signal.action == SignalAction.HOLD
    assert signal.confidence == 0.0


def test_signal_has_mandatory_reason(strategy: SmaCrossoverStrategy) -> None:
    closes = [100.0, 99.0, 98.0, 97.0, 98.0, 110.0]
    candles = make_candle_series(closes)
    signal = strategy.generate_signal(candles)
    assert len(signal.reason) > 0


def test_signal_metadata_contains_sma_values(strategy: SmaCrossoverStrategy) -> None:
    closes = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    candles = make_candle_series(closes)
    signal = strategy.generate_signal(candles)
    assert "sma_short" in signal.metadata
    assert "sma_long" in signal.metadata


def test_invalid_config_raises() -> None:
    with pytest.raises(ValueError, match="short_period must be less than long_period"):
        SmaCrossoverConfig(name="bad", short_period=10, long_period=5)
