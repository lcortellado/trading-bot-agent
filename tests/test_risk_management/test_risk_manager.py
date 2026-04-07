"""Tests for RiskManager."""
import pytest
from decimal import Decimal
from datetime import datetime, timezone

from app.domain.enums import SignalAction, Timeframe
from app.domain.models import Signal
from app.risk_management.risk_manager import RiskManager
from tests.conftest import make_settings


def make_signal(
    action: SignalAction = SignalAction.BUY,
    confidence: float = 0.75,
    reason: str = "test signal",
    price: float = 50_000.0,
    size_multiplier: float = 1.0,
) -> Signal:
    return Signal(
        symbol="BTCUSDT",
        timeframe=Timeframe.H1,
        action=action,
        strategy_name="test_strategy",
        confidence=confidence,
        reason=reason,
        price=Decimal(str(price)),
        size_multiplier=size_multiplier,
        timestamp=datetime.now(tz=timezone.utc),
    )


@pytest.fixture
def risk_manager() -> RiskManager:
    return RiskManager(make_settings())


def test_hold_signal_is_rejected(risk_manager: RiskManager) -> None:
    signal = make_signal(action=SignalAction.HOLD, reason="flat market")
    result = risk_manager.evaluate(signal, Decimal("10000"), [], Decimal("0"))
    assert not result.approved
    assert "HOLD" in result.reason


def test_low_confidence_is_rejected(risk_manager: RiskManager) -> None:
    signal = make_signal(confidence=0.1)
    result = risk_manager.evaluate(signal, Decimal("10000"), [], Decimal("0"))
    assert not result.approved
    assert "Confidence" in result.reason


def test_max_positions_limit(risk_manager: RiskManager) -> None:
    from app.domain.models import Position
    from app.domain.enums import OrderSide

    positions = [
        Position(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            entry_price=Decimal("50000"),
            quantity=Decimal("0.001"),
        )
        for _ in range(5)
    ]
    signal = make_signal()
    result = risk_manager.evaluate(signal, Decimal("10000"), positions, Decimal("0"))
    assert not result.approved
    assert "Max open positions" in result.reason


def test_daily_drawdown_limit(risk_manager: RiskManager) -> None:
    signal = make_signal()
    # 6% loss on 10k capital → exceeds 5% limit
    result = risk_manager.evaluate(
        signal, Decimal("10000"), [], Decimal("-600")
    )
    assert not result.approved
    assert "drawdown" in result.reason.lower()


def test_valid_signal_is_approved(risk_manager: RiskManager) -> None:
    signal = make_signal(confidence=0.8)
    result = risk_manager.evaluate(signal, Decimal("10000"), [], Decimal("0"))
    assert result.approved
    assert result.suggested_quantity is not None
    assert result.stop_loss is not None
    assert result.take_profit is not None


def test_position_sizing(risk_manager: RiskManager) -> None:
    signal = make_signal(price=50_000.0, confidence=0.8)
    result = risk_manager.evaluate(signal, Decimal("10000"), [], Decimal("0"))
    # 2% of 10k = 200 USDT / 50_000 = 0.004 BTC
    assert result.approved
    assert result.suggested_quantity == Decimal("0.00400")


def test_stop_loss_below_entry(risk_manager: RiskManager) -> None:
    signal = make_signal(price=50_000.0, confidence=0.8)
    result = risk_manager.evaluate(signal, Decimal("10000"), [], Decimal("0"))
    assert result.stop_loss < signal.price


def test_take_profit_above_entry(risk_manager: RiskManager) -> None:
    signal = make_signal(price=50_000.0, confidence=0.8)
    result = risk_manager.evaluate(signal, Decimal("10000"), [], Decimal("0"))
    assert result.take_profit > signal.price


def test_short_stop_loss_above_entry(risk_manager: RiskManager) -> None:
    signal = make_signal(action=SignalAction.SELL, price=50_000.0, confidence=0.8)
    result = risk_manager.evaluate(signal, Decimal("10000"), [], Decimal("0"))
    assert result.approved
    assert result.stop_loss is not None and result.stop_loss > signal.price
    assert result.take_profit is not None and result.take_profit < signal.price


def test_size_multiplier_reduces_quantity(risk_manager: RiskManager) -> None:
    full = make_signal(price=50_000.0, confidence=0.8, size_multiplier=1.0)
    half = make_signal(price=50_000.0, confidence=0.8, size_multiplier=0.5)
    r_full = risk_manager.evaluate(full, Decimal("10000"), [], Decimal("0"))
    r_half = risk_manager.evaluate(half, Decimal("10000"), [], Decimal("0"))
    assert r_full.approved and r_half.approved
    assert r_half.suggested_quantity == r_full.suggested_quantity * Decimal("0.5")
