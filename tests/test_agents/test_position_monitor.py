"""
Unit tests for PositionMonitor.

Verifies:
  - SL hit on BUY → close_position called
  - TP hit on BUY → close_position called
  - No SL/TP breach → position stays open
  - SL hit on SELL (short) → close_position called
  - Price fetch failure → position not closed (logged and retried next cycle)
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.domain.enums import OrderSide, OrderStatus, OrderType, TradingMode
from app.domain.models import Order, Position
from app.services.position_monitor import PositionMonitor, _check_exit_conditions
from app.services.signal_service import SignalService


def make_buy_position(
    entry: float = 50000,
    sl: float = 49000,
    tp: float = 52000,
) -> Position:
    return Position(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        entry_price=Decimal(str(entry)),
        quantity=Decimal("0.004"),
        stop_loss=Decimal(str(sl)),
        take_profit=Decimal(str(tp)),
    )


def make_sell_position(
    entry: float = 50000,
    sl: float = 51000,
    tp: float = 48000,
) -> Position:
    return Position(
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        entry_price=Decimal(str(entry)),
        quantity=Decimal("0.004"),
        stop_loss=Decimal(str(sl)),
        take_profit=Decimal(str(tp)),
    )


def make_mock_exchange(current_price: float) -> MagicMock:
    exchange = MagicMock()
    exchange.get_ticker_price = AsyncMock(return_value=Decimal(str(current_price)))
    exchange.place_order = AsyncMock(
        return_value=Order(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.004"),
            price=Decimal(str(current_price)),
            status=OrderStatus.FILLED,
            order_id="PAPER-CLOSE001",
            trading_mode=TradingMode.PAPER,
        )
    )
    return exchange


def make_mock_signal_service(positions: list[Position]) -> MagicMock:
    svc = MagicMock(spec=SignalService)
    svc.open_positions = positions
    svc.close_position = AsyncMock()
    return svc


# ── Pure function tests ────────────────────────────────────────────────────────


def test_check_exit_buy_sl_hit() -> None:
    pos = make_buy_position(entry=50000, sl=49000, tp=52000)
    should_exit, reason = _check_exit_conditions(pos, Decimal("48999"))
    assert should_exit
    assert "Stop-loss" in reason


def test_check_exit_buy_tp_hit() -> None:
    pos = make_buy_position(entry=50000, sl=49000, tp=52000)
    should_exit, reason = _check_exit_conditions(pos, Decimal("52001"))
    assert should_exit
    assert "Take-profit" in reason


def test_check_exit_buy_no_breach() -> None:
    pos = make_buy_position(entry=50000, sl=49000, tp=52000)
    should_exit, _ = _check_exit_conditions(pos, Decimal("50500"))
    assert not should_exit


def test_check_exit_sell_sl_hit() -> None:
    pos = make_sell_position(entry=50000, sl=51000, tp=48000)
    should_exit, reason = _check_exit_conditions(pos, Decimal("51001"))
    assert should_exit
    assert "Stop-loss" in reason


def test_check_exit_sell_tp_hit() -> None:
    pos = make_sell_position(entry=50000, sl=51000, tp=48000)
    should_exit, reason = _check_exit_conditions(pos, Decimal("47999"))
    assert should_exit
    assert "Take-profit" in reason


# ── Integration-level tests (async) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_monitor_closes_position_on_sl_hit() -> None:
    position = make_buy_position(entry=50000, sl=49000, tp=52000)
    exchange = make_mock_exchange(current_price=48500)  # below SL
    signal_service = make_mock_signal_service([position])

    monitor = PositionMonitor(signal_service, exchange, interval_seconds=30)
    await monitor._check_all_positions()

    signal_service.close_position.assert_awaited_once()
    closed_pos, pnl = signal_service.close_position.call_args[0]
    assert closed_pos is position
    assert pnl < 0  # loss on SL hit


@pytest.mark.asyncio
async def test_monitor_closes_position_on_tp_hit() -> None:
    position = make_buy_position(entry=50000, sl=49000, tp=52000)
    exchange = make_mock_exchange(current_price=53000)  # above TP
    signal_service = make_mock_signal_service([position])

    monitor = PositionMonitor(signal_service, exchange, interval_seconds=30)
    await monitor._check_all_positions()

    signal_service.close_position.assert_awaited_once()
    closed_pos, pnl = signal_service.close_position.call_args[0]
    assert closed_pos is position
    assert pnl > 0  # profit on TP hit


@pytest.mark.asyncio
async def test_monitor_no_action_within_sl_tp() -> None:
    position = make_buy_position(entry=50000, sl=49000, tp=52000)
    exchange = make_mock_exchange(current_price=50500)  # within range
    signal_service = make_mock_signal_service([position])

    monitor = PositionMonitor(signal_service, exchange, interval_seconds=30)
    await monitor._check_all_positions()

    signal_service.close_position.assert_not_called()


@pytest.mark.asyncio
async def test_monitor_handles_price_fetch_failure() -> None:
    """Price fetch failure → position is NOT closed; error is logged."""
    position = make_buy_position(entry=50000, sl=49000, tp=52000)
    exchange = MagicMock()
    exchange.get_ticker_price = AsyncMock(side_effect=RuntimeError("network error"))
    signal_service = make_mock_signal_service([position])

    monitor = PositionMonitor(signal_service, exchange, interval_seconds=30)
    # Should not raise
    await monitor._check_all_positions()

    signal_service.close_position.assert_not_called()


@pytest.mark.asyncio
async def test_monitor_skips_when_no_positions() -> None:
    exchange = MagicMock()
    exchange.get_ticker_price = AsyncMock()
    signal_service = make_mock_signal_service([])

    monitor = PositionMonitor(signal_service, exchange, interval_seconds=30)
    await monitor._check_all_positions()

    exchange.get_ticker_price.assert_not_called()
