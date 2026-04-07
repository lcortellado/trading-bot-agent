"""Tests for AutoTradingLoop — no real exchange calls."""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.schemas import AgentDecision
from app.domain.enums import OrderSide, SignalAction, Timeframe
from app.domain.models import Position, Signal
from app.schemas.agent import AgentDecisionResponse
from app.schemas.signal import SignalResponse
from app.services.auto_trading import (
    AutoTradingLoop,
    _parse_timeframe,
    _pick_primary,
    _signal_to_request,
)
from app.strategies.sma_crossover import SmaCrossoverConfig, SmaCrossoverStrategy
from tests.conftest import make_candle_series, make_settings


def test_parse_timeframe() -> None:
    assert _parse_timeframe("1h") == Timeframe.H1


def test_parse_timeframe_invalid() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        _parse_timeframe("bogus")


def test_pick_primary_highest_confidence() -> None:
    low = Signal(
        symbol="BTCUSDT",
        timeframe=Timeframe.H1,
        action=SignalAction.BUY,
        strategy_name="a",
        confidence=0.5,
        reason="x",
        price=Decimal("1"),
    )
    high = Signal(
        symbol="BTCUSDT",
        timeframe=Timeframe.H1,
        action=SignalAction.BUY,
        strategy_name="b",
        confidence=0.9,
        reason="y",
        price=Decimal("1"),
    )
    assert _pick_primary([low, high]).strategy_name == "b"


def test_signal_to_request_marks_auto() -> None:
    s = Signal(
        symbol="BTCUSDT",
        timeframe=Timeframe.H1,
        action=SignalAction.BUY,
        strategy_name="sma",
        confidence=0.7,
        reason="r",
        price=Decimal("50000"),
        metadata={"k": "v"},
    )
    req = _signal_to_request(s)
    assert req.metadata is not None
    assert req.metadata.get("auto_trading") is True


@pytest.fixture
def sma_strategy() -> SmaCrossoverStrategy:
    cfg = SmaCrossoverConfig(
        name="sma_crossover",
        description="test",
        short_period=3,
        long_period=5,
    )
    return SmaCrossoverStrategy(config=cfg)


@pytest.mark.asyncio
async def test_process_symbol_skips_when_open_position(sma_strategy: SmaCrossoverStrategy) -> None:
    settings = make_settings(
        auto_trading_symbols="BTCUSDT",
        auto_trading_strategy_names="sma_crossover",
        auto_trading_skip_if_open=True,
    )
    pos = Position(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        entry_price=Decimal("50000"),
        quantity=Decimal("0.01"),
    )
    signal_svc = MagicMock()
    signal_svc.open_positions = [pos]
    agent = MagicMock()
    loop = AutoTradingLoop(
        settings=settings,
        market_data=MagicMock(),
        strategies={"sma_crossover": sma_strategy},
        agent_service=agent,
        signal_service=signal_svc,
        event_store=None,
    )
    await loop._process_symbol("BTCUSDT")
    signal_svc.process_signal.assert_not_called()
    agent.process.assert_not_called()


@pytest.mark.asyncio
async def test_process_symbol_ai_path_calls_agent(
    sma_strategy: SmaCrossoverStrategy,
) -> None:
    settings = make_settings(
        auto_trading_symbols="BTCUSDT",
        auto_trading_strategy_names="sma_crossover",
        auto_trading_use_ai=True,
        auto_trading_candle_limit=60,
    )
    closes = [100.0, 99.0, 98.0, 97.0, 98.0, 110.0]
    candles = make_candle_series(closes)

    market_data = MagicMock()
    market_data.get_candles = AsyncMock(return_value=candles)

    agent = MagicMock()
    agent.process = AsyncMock(
        return_value=AgentDecisionResponse(
            agent_decision=AgentDecision.SKIP,
            agent_confidence=0.0,
            agent_reason="test skip",
            order_executed=False,
            signal_response=None,
        )
    )
    signal_svc = MagicMock()
    signal_svc.open_positions = []

    loop = AutoTradingLoop(
        settings=settings,
        market_data=market_data,
        strategies={"sma_crossover": sma_strategy},
        agent_service=agent,
        signal_service=signal_svc,
        event_store=None,
    )
    await loop._process_symbol("BTCUSDT")
    agent.process.assert_awaited_once()
    signal_svc.process_signal.assert_not_called()


@pytest.mark.asyncio
async def test_process_symbol_direct_path_calls_signal_service(
    sma_strategy: SmaCrossoverStrategy,
) -> None:
    settings = make_settings(
        auto_trading_symbols="BTCUSDT",
        auto_trading_strategy_names="sma_crossover",
        auto_trading_use_ai=False,
    )
    closes = [100.0, 99.0, 98.0, 97.0, 98.0, 110.0]
    candles = make_candle_series(closes)

    market_data = MagicMock()
    market_data.get_candles = AsyncMock(return_value=candles)

    signal_svc = MagicMock()
    signal_svc.open_positions = []
    signal_svc.process_signal = AsyncMock(
        return_value=SignalResponse(
            accepted=False,
            signal_action=SignalAction.BUY,
            symbol="BTCUSDT",
            reason="risk",
            risk_check_passed=False,
        )
    )

    loop = AutoTradingLoop(
        settings=settings,
        market_data=market_data,
        strategies={"sma_crossover": sma_strategy},
        agent_service=MagicMock(),
        signal_service=signal_svc,
        event_store=None,
    )
    await loop._process_symbol("BTCUSDT")
    signal_svc.process_signal.assert_awaited_once()


@pytest.mark.asyncio
async def test_emit_auto_event_when_store_present(
    sma_strategy: SmaCrossoverStrategy,
) -> None:
    settings = make_settings(
        auto_trading_strategy_names="sma_crossover",
        auto_trading_use_ai=True,
    )
    closes = [100.0, 99.0, 98.0, 97.0, 98.0, 110.0]
    candles = make_candle_series(closes)

    market_data = MagicMock()
    market_data.get_candles = AsyncMock(return_value=candles)

    agent = MagicMock()
    agent.process = AsyncMock(
        return_value=AgentDecisionResponse(
            agent_decision=AgentDecision.SKIP,
            agent_confidence=0.0,
            agent_reason="skip",
            order_executed=False,
            signal_response=None,
        )
    )
    store = MagicMock()
    store.append_new = AsyncMock()

    loop = AutoTradingLoop(
        settings=settings,
        market_data=market_data,
        strategies={"sma_crossover": sma_strategy},
        agent_service=agent,
        signal_service=MagicMock(open_positions=[]),
        event_store=store,
    )
    await loop._process_symbol("BTCUSDT")
    store.append_new.assert_awaited()


@pytest.mark.asyncio
async def test_no_candles_skips_quietly(sma_strategy: SmaCrossoverStrategy) -> None:
    settings = make_settings(auto_trading_strategy_names="sma_crossover")
    market_data = MagicMock()
    market_data.get_candles = AsyncMock(side_effect=ValueError("no data"))

    agent = MagicMock()
    agent.process = AsyncMock()

    loop = AutoTradingLoop(
        settings=settings,
        market_data=market_data,
        strategies={"sma_crossover": sma_strategy},
        agent_service=agent,
        signal_service=MagicMock(open_positions=[]),
        event_store=None,
    )
    await loop._process_symbol("BTCUSDT")
    agent.process.assert_not_called()
