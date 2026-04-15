"""
Deterministic market analysts — enrich AgentInput before a single LLM call.

Each analyst returns a compact AnalystSummary (stance, score, confidence, drivers).
No network I/O; safe to run on every /agent/decide request when enabled.
"""
from __future__ import annotations

from collections.abc import Sequence

from app.agents.schemas import AnalystSummary, MarketContext, NewsHeadline, SignalFeature

_BULLISH_TERMS = frozenset(
    {
        "rally",
        "surge",
        "breakout",
        "inflow",
        "inflows",
        "etf",
        "adoption",
        "bullish",
        "gains",
        "gain",
        "soar",
        "record high",
        "upgrade",
        "accumulation",
    }
)
_BEARISH_TERMS = frozenset(
    {
        "crash",
        "plunge",
        "selloff",
        "sell-off",
        "outflow",
        "outflows",
        "bearish",
        "hack",
        "exploit",
        "ban",
        "lawsuit",
        "sec charges",
        "liquidation",
        "fear",
    }
)
_RISK_TERMS = frozenset(
    {
        "regulator",
        "regulatory",
        "investigation",
        "uncertainty",
        "volatile",
        "warning",
        "concern",
        "scrutiny",
    }
)


class AgentAnalystService:
    """Builds analyst_summaries for AgentInput (signal consensus, market, news digest)."""

    def build_summaries(
        self,
        *,
        signals: Sequence[SignalFeature],
        market_context: MarketContext,
        news_headlines: Sequence[NewsHeadline],
    ) -> list[AnalystSummary]:
        out: list[AnalystSummary] = [
            self._signal_consensus(signals),
            self._market_context_view(market_context),
            self._news_digest(news_headlines),
        ]
        return out

    def _signal_consensus(self, signals: Sequence[SignalFeature]) -> AnalystSummary:
        analyst_id = "signal_consensus"
        if not signals:
            return AnalystSummary(
                analyst_id=analyst_id,
                stance="neutral",
                score=0.0,
                confidence=0.15,
                drivers=["No strategy signals in bundle"],
            )

        weighted = 0.0
        weight_sum = 0.0
        buy_n = sell_n = hold_n = 0
        for s in signals:
            w = max(0.0, min(1.0, s.confidence))
            weight_sum += w
            a = s.action.strip().lower()
            if a == "buy":
                weighted += w
                buy_n += 1
            elif a == "sell":
                weighted -= w
                sell_n += 1
            else:
                hold_n += 1

        denom = weight_sum if weight_sum > 1e-9 else 1.0
        score = max(-1.0, min(1.0, weighted / denom))
        strong_both = buy_n >= 1 and sell_n >= 1 and abs(score) < 0.25
        stance = "mixed" if strong_both else _stance_from_score(score)
        spread = abs(score)
        agreement = max(buy_n, sell_n, hold_n) / len(signals)
        confidence = round(min(1.0, 0.35 + 0.45 * agreement + 0.25 * spread), 4)

        drivers: list[str] = []
        drivers.append(f"{buy_n} buy / {sell_n} sell / {hold_n} hold among {len(signals)} signals")
        top = sorted(signals, key=lambda x: x.confidence, reverse=True)[:3]
        for s in top:
            drivers.append(f"{s.name}: {s.action} ({s.confidence:.0%})")

        return AnalystSummary(
            analyst_id=analyst_id,
            stance=stance,
            score=round(score, 4),
            confidence=confidence,
            drivers=drivers[:12],
        )

    def _market_context_view(self, ctx: MarketContext) -> AnalystSummary:
        analyst_id = "market_context"
        drivers: list[str] = []
        score = 0.0

        trend = (ctx.trend or "").strip().lower()
        if trend == "bullish":
            score += 0.35
            drivers.append("trend labeled bullish")
        elif trend == "bearish":
            score -= 0.35
            drivers.append("trend labeled bearish")
        elif trend == "sideways":
            drivers.append("trend labeled sideways")

        vol = ctx.volatility_24h
        if vol is not None:
            if vol >= 0.06:
                drivers.append(f"elevated 24h volatility (~{vol:.1%})")
            elif vol <= 0.015:
                drivers.append(f"compressed 24h volatility (~{vol:.1%})")

        vr = ctx.volume_ratio
        if vr is not None:
            if vr >= 1.5:
                drivers.append(f"volume_ratio {vr:.2f} (above average)")
            elif vr <= 0.6:
                drivers.append(f"volume_ratio {vr:.2f} (below average)")

        if not drivers:
            drivers.append("No market_context fields set")

        stance = _stance_from_score(score)
        confidence = 0.55 if trend else 0.35
        if vol is not None or vr is not None:
            confidence = min(1.0, confidence + 0.15)

        return AnalystSummary(
            analyst_id=analyst_id,
            stance=stance,
            score=round(max(-1.0, min(1.0, score)), 4),
            confidence=round(confidence, 4),
            drivers=drivers[:12],
        )

    def _news_digest(self, headlines: Sequence[NewsHeadline]) -> AnalystSummary:
        analyst_id = "news_digest"
        if not headlines:
            return AnalystSummary(
                analyst_id=analyst_id,
                stance="neutral",
                score=0.0,
                confidence=0.2,
                drivers=["No headlines ingested for this symbol"],
            )

        bull = bear = risk = 0
        lowered = [h.title.lower() for h in headlines]
        for text in lowered:
            bull += sum(1 for term in _BULLISH_TERMS if term in text)
            bear += sum(1 for term in _BEARISH_TERMS if term in text)
            risk += sum(1 for term in _RISK_TERMS if term in text)

        raw = bull - bear
        total = bull + bear
        if total == 0:
            score = 0.0
            stance = "neutral"
            confidence = 0.35 if headlines else 0.2
            drivers = [
                f"{len(headlines)} headline(s); no lexicon hits (titles are weak/macro)",
            ]
        else:
            score = max(-1.0, min(1.0, raw / total))
            stance = "mixed" if bull >= 1 and bear >= 1 and abs(score) < 0.35 else _stance_from_score(score)
            confidence = min(1.0, 0.4 + 0.15 * min(total, 6))
            drivers = [
                f"lexicon hits: bullish={bull}, bearish={bear} across {len(headlines)} headlines",
            ]
        if risk:
            drivers.append(f"risk-tone hits: {risk}")
        if headlines:
            drivers.append(f"sample: {headlines[0].title[:80]!r}")

        return AnalystSummary(
            analyst_id=analyst_id,
            stance=stance,
            score=round(score, 4),
            confidence=round(confidence, 4),
            drivers=drivers[:12],
        )


def _stance_from_score(score: float) -> str:
    if score > 0.2:
        return "bullish"
    if score < -0.2:
        return "bearish"
    return "neutral"
