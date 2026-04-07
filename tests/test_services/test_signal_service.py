"""Tests for SignalService using a mock exchange."""
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.domain.enums import OrderSide, OrderStatus, OrderType, SignalAction, Timeframe, TradingMode
from app.domain.models import Order
from app.risk_management.risk_manager import RiskManager
from app.schemas.signal import SignalRequest
from app.services.signal_service import SignalService
from tests.conftest import make_settings


def make_mock_exchange(order_id: str = "PAPER-ABC123") -> MagicMock:
    exchange = AsyncMock()
    exchange.place_order.return_value = Order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.004"),
        price=Decimal("50000"),
        status=OrderStatus.FILLED,
        order_id=order_id,
        filled_qty=Decimal("0.004"),
        filled_price=Decimal("50000"),
        trading_mode=TradingMode.PAPER,
    )
    return exchange


@pytest.fixture
def service() -> SignalService:
    settings = make_settings()
    exchange = make_mock_exchange()
    risk = RiskManager(settings)
    return SignalService(exchange, risk, settings)


@pytest.mark.asyncio
async def test_valid_buy_signal_is_accepted(service: SignalService) -> None:
    req = SignalRequest(
        symbol="BTCUSDT",
        timeframe=Timeframe.H1,
        action=SignalAction.BUY,
        strategy_name="test",
        confidence=0.8,
        reason="Golden cross detected",
        price=Decimal("50000"),
    )
    response = await service.process_signal(req)
    assert response.accepted
    assert response.risk_check_passed
    assert response.order_id is not None


@pytest.mark.asyncio
async def test_hold_signal_is_not_accepted(service: SignalService) -> None:
    req = SignalRequest(
        symbol="BTCUSDT",
        timeframe=Timeframe.H1,
        action=SignalAction.HOLD,
        strategy_name="test",
        confidence=0.0,
        reason="No crossover detected",
        price=Decimal("50000"),
    )
    response = await service.process_signal(req)
    assert not response.accepted
    assert not response.risk_check_passed
    assert response.order_id is None


@pytest.mark.asyncio
async def test_low_confidence_signal_rejected(service: SignalService) -> None:
    req = SignalRequest(
        symbol="BTCUSDT",
        timeframe=Timeframe.H1,
        action=SignalAction.BUY,
        strategy_name="test",
        confidence=0.1,
        reason="Weak signal",
        price=Decimal("50000"),
    )
    response = await service.process_signal(req)
    assert not response.accepted


@pytest.mark.asyncio
async def test_symbol_is_uppercased(service: SignalService) -> None:
    req = SignalRequest(
        symbol="btcusdt",
        timeframe=Timeframe.H1,
        action=SignalAction.BUY,
        strategy_name="test",
        confidence=0.8,
        reason="Test",
        price=Decimal("50000"),
    )
    response = await service.process_signal(req)
    assert response.symbol == "BTCUSDT"


@pytest.mark.asyncio
async def test_capital_reserved_on_fill_and_restored_on_close(service: SignalService) -> None:
    """Opening locks notional; closing returns locked amount plus realized PnL."""
    assert service.capital == Decimal("10000")
    req = SignalRequest(
        symbol="BTCUSDT",
        timeframe=Timeframe.H1,
        action=SignalAction.BUY,
        strategy_name="test",
        confidence=0.8,
        reason="Golden cross detected",
        price=Decimal("50000"),
    )
    await service.process_signal(req)
    locked = Decimal("50000") * Decimal("0.004")
    assert service.capital == Decimal("10000") - locked
    assert len(service.open_positions) == 1
    pos = service.open_positions[0]
    pnl = Decimal("25.5")
    await service.close_position(pos, pnl)
    assert service.capital == Decimal("10000") - locked + pos.entry_price * pos.quantity + pnl
    assert service.daily_pnl == pnl
    assert len(service.open_positions) == 0
