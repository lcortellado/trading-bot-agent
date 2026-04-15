"""
Unit tests for AgentService.

Key scenarios:
  - Agent SKIP → no order placed, response has order_executed=False
  - Agent ENTER + RiskManager approves → order placed, order_executed=True
  - Agent REDUCE_SIZE → confidence scaled before forwarding to signal service
  - AI fallback (unavailable) → SKIP, no order
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.agents.agent_service import (
    AgentService,
    REDUCE_CONFIDENCE_FACTOR,
    REDUCE_SIZE_MULTIPLIER,
)
from app.agents.ai_client import AIDecisionClient
from app.agents.schemas import AgentDecision, AgentOutput, NewsHeadline
from app.domain.enums import OrderSide, OrderStatus, OrderType, SignalAction, Timeframe, TradingMode
from app.domain.models import Order
from app.risk_management.risk_manager import RiskManager
from app.schemas.agent import AgentSignalRequest
from app.schemas.signal import SignalRequest, SignalResponse
from app.services.news_context import NewsContextService
from app.services.signal_service import SignalService
from tests.conftest import make_settings


def make_primary_signal(
    confidence: float = 0.8,
    action: SignalAction = SignalAction.BUY,
) -> SignalRequest:
    return SignalRequest(
        symbol="BTCUSDT",
        timeframe=Timeframe.H1,
        action=action,
        strategy_name="sma_crossover",
        confidence=confidence,
        reason="Golden cross detected",
        price=Decimal("50000"),
    )


def make_agent_request(confidence: float = 0.8) -> AgentSignalRequest:
    sig = make_primary_signal(confidence=confidence)
    return AgentSignalRequest(primary_signal=sig, signals=[sig])


def make_mock_signal_service(accepted: bool = True) -> MagicMock:
    svc = MagicMock(spec=SignalService)
    svc.capital = Decimal("10000")
    svc.open_positions = []
    svc.daily_pnl = Decimal("0")
    svc.process_signal = AsyncMock(
        return_value=SignalResponse(
            accepted=accepted,
            signal_action=SignalAction.BUY,
            symbol="BTCUSDT",
            reason="All risk checks passed",
            risk_check_passed=accepted,
            order_id="PAPER-ABC123" if accepted else None,
        )
    )
    return svc


def make_mock_ai_client(decision: AgentDecision, confidence: float = 0.8) -> MagicMock:
    client = MagicMock(spec=AIDecisionClient)
    client.decide = AsyncMock(
        return_value=AgentOutput(
            decision=decision,
            confidence=confidence,
            reason=f"Agent decided {decision.value} — test",
        )
    )
    return client


def make_mock_news_context(headline_title: str = "BTC ETF inflows rise") -> MagicMock:
    svc = MagicMock(spec=NewsContextService)
    svc.fetch_for_symbol = AsyncMock(
        return_value=[
            NewsHeadline(
                title=headline_title,
                source="test-feed",
                url="https://example.com/news",
                published_at="2026-04-09T10:00:00Z",
            )
        ]
    )
    return svc


@pytest.mark.asyncio
async def test_agent_skip_does_not_place_order() -> None:
    """SKIP decision: signal service must not be called."""
    settings = make_settings()
    ai_client = make_mock_ai_client(AgentDecision.SKIP)
    signal_service = make_mock_signal_service()

    service = AgentService(ai_client, signal_service, settings)
    response = await service.process(make_agent_request())

    assert response.agent_decision == AgentDecision.SKIP
    assert not response.order_executed
    assert response.signal_response is None
    signal_service.process_signal.assert_not_called()


@pytest.mark.asyncio
async def test_agent_enter_with_risk_approval_places_order() -> None:
    """ENTER + RiskManager approves → order_executed is True."""
    settings = make_settings()
    ai_client = make_mock_ai_client(AgentDecision.ENTER, confidence=0.85)
    signal_service = make_mock_signal_service(accepted=True)

    service = AgentService(ai_client, signal_service, settings)
    response = await service.process(make_agent_request())

    assert response.agent_decision == AgentDecision.ENTER
    assert response.order_executed
    assert response.signal_response is not None
    assert response.signal_response.order_id == "PAPER-ABC123"
    signal_service.process_signal.assert_awaited_once()


@pytest.mark.asyncio
async def test_agent_enter_risk_rejected_no_order() -> None:
    """ENTER but RiskManager rejects → order_executed is False."""
    settings = make_settings()
    ai_client = make_mock_ai_client(AgentDecision.ENTER, confidence=0.85)
    signal_service = make_mock_signal_service(accepted=False)

    service = AgentService(ai_client, signal_service, settings)
    response = await service.process(make_agent_request())

    assert response.agent_decision == AgentDecision.ENTER
    assert not response.order_executed
    signal_service.process_signal.assert_awaited_once()


@pytest.mark.asyncio
async def test_reduce_size_scales_confidence_and_size() -> None:
    """REDUCE_SIZE: scaled confidence and reduced size_multiplier on forwarded signal."""
    settings = make_settings()
    original_confidence = 0.8
    ai_client = make_mock_ai_client(AgentDecision.REDUCE_SIZE, confidence=original_confidence)
    signal_service = make_mock_signal_service(accepted=True)

    service = AgentService(ai_client, signal_service, settings)
    await service.process(make_agent_request(confidence=original_confidence))

    call_args = signal_service.process_signal.call_args
    forwarded_request: SignalRequest = call_args[0][0]
    expected_confidence = round(original_confidence * REDUCE_CONFIDENCE_FACTOR, 4)
    assert forwarded_request.confidence == pytest.approx(expected_confidence)
    assert forwarded_request.size_multiplier == pytest.approx(REDUCE_SIZE_MULTIPLIER)


@pytest.mark.asyncio
async def test_agent_strategy_name_prefixed() -> None:
    """Forwarded signal has 'agent:' prefix so origin is traceable."""
    settings = make_settings()
    ai_client = make_mock_ai_client(AgentDecision.ENTER)
    signal_service = make_mock_signal_service(accepted=True)

    service = AgentService(ai_client, signal_service, settings)
    await service.process(make_agent_request())

    forwarded: SignalRequest = signal_service.process_signal.call_args[0][0]
    assert forwarded.strategy_name.startswith("agent:")


@pytest.mark.asyncio
async def test_ai_fallback_returns_skip() -> None:
    """If AI client returns SKIP (e.g., unavailable), no order is placed."""
    settings = make_settings()  # no ai_api_key → client disabled → always SKIP
    ai_client = AIDecisionClient(settings)  # real client, disabled
    signal_service = make_mock_signal_service(accepted=True)

    service = AgentService(ai_client, signal_service, settings)
    response = await service.process(make_agent_request())

    assert response.agent_decision == AgentDecision.SKIP
    assert not response.order_executed
    signal_service.process_signal.assert_not_called()


@pytest.mark.asyncio
async def test_news_context_is_attached_when_enabled() -> None:
    settings = make_settings(news_context_enabled=True)
    ai_client = make_mock_ai_client(AgentDecision.SKIP)
    signal_service = make_mock_signal_service(accepted=True)
    news_service = make_mock_news_context()
    service = AgentService(
        ai_client,
        signal_service,
        settings,
        news_context=news_service,
    )

    await service.process(make_agent_request())

    news_service.fetch_for_symbol.assert_awaited_once_with("BTCUSDT")
    ai_input = ai_client.decide.call_args[0][0]
    assert len(ai_input.news_headlines) == 1
    assert ai_input.news_headlines[0].title == "BTC ETF inflows rise"
    assert len(ai_input.analyst_summaries) == 3
    assert {s.analyst_id for s in ai_input.analyst_summaries} == {
        "signal_consensus",
        "market_context",
        "news_digest",
    }


@pytest.mark.asyncio
async def test_analyst_summaries_disabled_empty() -> None:
    settings = make_settings(news_context_enabled=False, agent_analysts_enabled=False)
    ai_client = make_mock_ai_client(AgentDecision.SKIP)
    signal_service = make_mock_signal_service()
    service = AgentService(ai_client, signal_service, settings)
    await service.process(make_agent_request())
    ai_input = ai_client.decide.call_args[0][0]
    assert ai_input.analyst_summaries == []


@pytest.mark.asyncio
async def test_news_context_failure_does_not_block_decision() -> None:
    settings = make_settings(news_context_enabled=True)
    ai_client = make_mock_ai_client(AgentDecision.SKIP)
    signal_service = make_mock_signal_service(accepted=True)
    news_service = MagicMock(spec=NewsContextService)
    news_service.fetch_for_symbol = AsyncMock(side_effect=RuntimeError("news down"))
    service = AgentService(
        ai_client,
        signal_service,
        settings,
        news_context=news_service,
    )

    response = await service.process(make_agent_request())

    assert response.agent_decision == AgentDecision.SKIP
    ai_client.decide.assert_awaited_once()
