"""Unit tests for AgentAnalystService (deterministic analyst_summaries)."""

import pytest

from app.agents.schemas import MarketContext, NewsHeadline, SignalFeature
from app.services.agent_analyst_service import AgentAnalystService


@pytest.fixture
def svc() -> AgentAnalystService:
    return AgentAnalystService()


def test_signal_consensus_aligned_buy(svc: AgentAnalystService) -> None:
    signals = [
        SignalFeature(name="a", action="buy", confidence=0.9, reason="x"),
        SignalFeature(name="b", action="buy", confidence=0.85, reason="y"),
    ]
    summaries = svc.build_summaries(
        signals=signals,
        market_context=MarketContext(),
        news_headlines=[],
    )
    sc = next(s for s in summaries if s.analyst_id == "signal_consensus")
    assert sc.stance == "bullish"
    assert sc.score > 0.5
    assert sc.confidence >= 0.5


def test_signal_consensus_mixed_buy_sell(svc: AgentAnalystService) -> None:
    signals = [
        SignalFeature(name="a", action="buy", confidence=0.8, reason="x"),
        SignalFeature(name="b", action="sell", confidence=0.75, reason="y"),
    ]
    summaries = svc.build_summaries(
        signals=signals,
        market_context=MarketContext(),
        news_headlines=[],
    )
    sc = next(s for s in summaries if s.analyst_id == "signal_consensus")
    assert sc.stance == "mixed"


def test_market_context_bullish_trend(svc: AgentAnalystService) -> None:
    ctx = MarketContext(trend="bullish", volatility_24h=0.07, volume_ratio=1.8)
    summaries = svc.build_summaries(
        signals=[
            SignalFeature(name="s", action="hold", confidence=0.5, reason="z"),
        ],
        market_context=ctx,
        news_headlines=[],
    )
    mc = next(s for s in summaries if s.analyst_id == "market_context")
    assert mc.stance == "bullish"
    assert any("volatility" in d.lower() for d in mc.drivers)
    assert any("volume" in d.lower() for d in mc.drivers)


def test_news_digest_bullish_hits(svc: AgentAnalystService) -> None:
    headlines = [
        NewsHeadline(title="Bitcoin ETF inflows surge after rally", source="t"),
    ]
    summaries = svc.build_summaries(
        signals=[
            SignalFeature(name="s", action="buy", confidence=0.7, reason="r"),
        ],
        market_context=MarketContext(),
        news_headlines=headlines,
    )
    nd = next(s for s in summaries if s.analyst_id == "news_digest")
    assert nd.stance == "bullish"
    assert nd.score > 0
    assert "lexicon" in " ".join(nd.drivers).lower()


def test_news_digest_empty(svc: AgentAnalystService) -> None:
    summaries = svc.build_summaries(
        signals=[
            SignalFeature(name="s", action="buy", confidence=0.7, reason="r"),
        ],
        market_context=MarketContext(),
        news_headlines=[],
    )
    nd = next(s for s in summaries if s.analyst_id == "news_digest")
    assert nd.stance == "neutral"
    assert any("no headlines" in d.lower() for d in nd.drivers)


def test_returns_three_analysts(svc: AgentAnalystService) -> None:
    summaries = svc.build_summaries(
        signals=[SignalFeature(name="x", action="hold", confidence=0.5, reason="h")],
        market_context=MarketContext(),
        news_headlines=[],
    )
    ids = {s.analyst_id for s in summaries}
    assert ids == {"signal_consensus", "market_context", "news_digest"}
