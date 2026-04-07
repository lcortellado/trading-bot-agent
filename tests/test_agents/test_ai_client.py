"""
Unit tests for AIDecisionClient.

All tests use mocks — no real network calls.
Verifies: fallback on missing key, fallback on API error, successful parse.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.ai_client import AIDecisionClient, _skip
from app.agents.schemas import AgentDecision, AgentInput, AgentOutput, MarketContext, RiskContext, SignalFeature
from tests.conftest import make_settings


def make_agent_input() -> AgentInput:
    return AgentInput(
        symbol="BTCUSDT",
        timeframe="1h",
        current_price=50000.0,
        signals=[
            SignalFeature(
                name="sma_crossover",
                action="buy",
                confidence=0.75,
                reason="Golden cross detected",
            )
        ],
        market_context=MarketContext(volume_ratio=1.2, trend="bullish"),
        risk_context=RiskContext(
            available_capital=9800.0,
            open_positions_count=0,
            daily_pnl=0.0,
        ),
    )


def test_fallback_when_api_key_missing() -> None:
    settings = make_settings()  # ai_api_key defaults to ""
    client = AIDecisionClient(settings)
    assert not client._enabled


@pytest.mark.asyncio
async def test_decide_returns_skip_when_disabled() -> None:
    settings = make_settings()
    client = AIDecisionClient(settings)
    result = await client.decide(make_agent_input())
    assert result.decision == AgentDecision.SKIP
    assert result.confidence == 0.0
    assert "API key" in result.reason or "not configured" in result.reason


@pytest.mark.asyncio
async def test_decide_returns_skip_on_api_error() -> None:
    settings = make_settings(ai_api_key="sk-test-key", ai_enabled=True)
    client = AIDecisionClient(settings)

    with patch.object(client, "_call_claude", side_effect=RuntimeError("timeout")):
        result = await client.decide(make_agent_input())

    assert result.decision == AgentDecision.SKIP
    assert "RuntimeError" in result.reason


@pytest.mark.asyncio
async def test_decide_openai_path_uses_call_openai() -> None:
    settings = make_settings(
        ai_provider="openai",
        openai_api_key="sk-openai-test",
        ai_enabled=True,
    )
    client = AIDecisionClient(settings)
    expected = AgentOutput(
        decision=AgentDecision.ENTER,
        confidence=0.7,
        reason="OpenAI path",
    )
    with patch.object(client, "_call_openai", AsyncMock(return_value=expected)):
        result = await client.decide(make_agent_input())
    assert result.decision == AgentDecision.ENTER
    assert "OpenAI path" in result.reason


@pytest.mark.asyncio
async def test_decide_parses_valid_claude_response() -> None:
    """decide() propagates the parsed AgentOutput when _call_claude succeeds."""
    settings = make_settings(ai_api_key="sk-test-key", ai_enabled=True)
    client = AIDecisionClient(settings)

    expected = AgentOutput(
        decision=AgentDecision.ENTER,
        confidence=0.82,
        reason="SMA bullish + volume surge",
    )

    # Patch _call_claude directly — the anthropic SDK is lazily imported
    # inside that method so we avoid patching module-level imports.
    with patch.object(client, "_call_claude", AsyncMock(return_value=expected)):
        result = await client.decide(make_agent_input())

    assert result.decision == AgentDecision.ENTER
    assert result.confidence == pytest.approx(0.82)
    assert "SMA bullish" in result.reason


@pytest.mark.asyncio
async def test_decide_returns_skip_on_invalid_json() -> None:
    settings = make_settings(ai_api_key="sk-test-key", ai_enabled=True)
    client = AIDecisionClient(settings)

    with patch.object(client, "_call_claude", side_effect=ValueError("json decode error")):
        result = await client.decide(make_agent_input())

    assert result.decision == AgentDecision.SKIP
