"""
AgentService — AI decision layer between signal input and order execution.

Position in the flow:
  API route → AgentService → (optional NewsContextService) → AIDecisionClient → SignalService → RiskManager → Exchange

Responsibilities:
  1. Build a structured AgentInput from the incoming signal bundle.
  2. Optionally attach RSS/CryptoPanic headlines when NEWS_CONTEXT_ENABLED.
  3. Ask AIDecisionClient for a synthesized decision (ENTER / SKIP / REDUCE_SIZE).
  4. SKIP  → return immediately; exchange is never called.
  5. ENTER / REDUCE_SIZE → forward to SignalService (which calls RiskManager as final gate).

The AI agent is an ADDITIONAL reasoning layer. RiskManager remains the last
hard barrier for capital protection and is always run on ENTER/REDUCE_SIZE.

REDUCE_SIZE: confidence is scaled by REDUCE_CONFIDENCE_FACTOR (MIN_CONFIDENCE gate)
and position notional is scaled by REDUCE_SIZE_MULTIPLIER on the forwarded signal.
"""
from decimal import Decimal

from app.agents.ai_client import AIDecisionClient
from app.agents.schemas import (
    AgentDecision,
    AgentInput,
    NewsHeadline,
    AgentOutput,
    MarketContext,
    RiskContext,
    SignalFeature,
)
from app.core.config import Settings
from app.core.logging import DecisionLogger, get_logger
from app.dashboard.event_store import DashboardEventStore
from app.schemas.agent import AgentDecisionResponse, AgentSignalRequest
from app.schemas.dashboard import DashboardEventKind
from app.schemas.signal import SignalRequest
from app.services.news_context import NewsContextService
from app.services.signal_service import SignalService

log = get_logger(__name__)
decision_log = DecisionLogger(log)

# On REDUCE_SIZE the confidence is multiplied by this factor before the
# risk check — still keeps the trade alive if above MIN_CONFIDENCE (0.4).
REDUCE_CONFIDENCE_FACTOR = 0.6
# Fraction of max position notional when the agent chooses REDUCE_SIZE.
REDUCE_SIZE_MULTIPLIER = 0.5


class AgentService:
    def __init__(
        self,
        ai_client: AIDecisionClient,
        signal_service: SignalService,
        settings: Settings,
        event_store: DashboardEventStore | None = None,
        news_context: NewsContextService | None = None,
    ) -> None:
        self._ai = ai_client
        self._signal_service = signal_service
        self._settings = settings
        self._event_store = event_store
        self._news_context = news_context

    async def process(self, request: AgentSignalRequest) -> AgentDecisionResponse:
        """
        Full agent pipeline:
          build input → optional news fetch → AI decide → log → (if not SKIP) forward to SignalService.
        """
        agent_input = self._build_agent_input(request)
        headlines: list[NewsHeadline] = []
        if self._news_context is not None and self._settings.news_context_enabled:
            try:
                headlines = await self._news_context.fetch_for_symbol(
                    request.primary_signal.symbol
                )
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "News context unavailable for %s: %s",
                    request.primary_signal.symbol,
                    exc,
                )
                headlines = []
            agent_input = agent_input.model_copy(update={"news_headlines": headlines})
        agent_output: AgentOutput = await self._ai.decide(agent_input)

        # ── SKIP: return immediately, no order ────────────────────────────────
        if agent_output.decision == AgentDecision.SKIP:
            decision_log.skip(
                request.primary_signal.symbol,
                agent_output.reason,
                source="ai_agent",
                confidence=f"{agent_output.confidence:.2%}",
            )
            await self._emit_agent_dashboard(
                request.primary_signal.symbol,
                agent_output,
                order_executed=False,
                news_headlines=headlines,
            )
            return AgentDecisionResponse(
                agent_decision=AgentDecision.SKIP,
                agent_confidence=agent_output.confidence,
                agent_reason=agent_output.reason,
                order_executed=False,
                signal_response=None,
            )

        # ── ENTER / REDUCE_SIZE: forward through RiskManager → exchange ───────
        effective_confidence = agent_output.confidence
        size_mult = 1.0
        if agent_output.decision == AgentDecision.REDUCE_SIZE:
            effective_confidence = round(
                agent_output.confidence * REDUCE_CONFIDENCE_FACTOR, 4
            )
            size_mult = REDUCE_SIZE_MULTIPLIER
            log.info(
                "REDUCE_SIZE applied | symbol=%s | confidence %.2f → %.2f | size_mult=%s",
                request.primary_signal.symbol,
                agent_output.confidence,
                effective_confidence,
                size_mult,
            )

        decision_log.enter(
            request.primary_signal.symbol,
            agent_output.reason,
            source="ai_agent",
            decision=agent_output.decision.value,
            effective_confidence=f"{effective_confidence:.2%}",
        )

        await self._emit_agent_dashboard(
            request.primary_signal.symbol,
            agent_output,
            order_executed=None,
            effective_confidence=effective_confidence,
            size_multiplier=size_mult,
            news_headlines=headlines,
        )

        signal_req = self._build_signal_request(
            request, effective_confidence, agent_output.reason, size_multiplier=size_mult
        )
        signal_resp = await self._signal_service.process_signal(signal_req)

        return AgentDecisionResponse(
            agent_decision=agent_output.decision,
            agent_confidence=agent_output.confidence,
            agent_reason=agent_output.reason,
            order_executed=signal_resp.accepted,
            signal_response=signal_resp,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_agent_input(self, request: AgentSignalRequest) -> AgentInput:
        signal_features = [
            SignalFeature(
                name=s.strategy_name,
                action=s.action.value,
                confidence=s.confidence,
                reason=s.reason,
            )
            for s in request.signals
        ]
        risk_ctx = RiskContext(
            available_capital=float(self._signal_service.capital),
            open_positions_count=len(self._signal_service.open_positions),
            daily_pnl=float(self._signal_service.daily_pnl),
        )
        return AgentInput(
            symbol=request.primary_signal.symbol,
            timeframe=request.primary_signal.timeframe.value,
            current_price=float(request.primary_signal.price),
            signals=signal_features,
            market_context=request.market_context or MarketContext(),
            risk_context=risk_ctx,
        )

    def _build_signal_request(
        self,
        request: AgentSignalRequest,
        confidence: float,
        reason: str,
        size_multiplier: float = 1.0,
    ) -> SignalRequest:
        ps = request.primary_signal
        base_mult = min(ps.size_multiplier, 1.0)
        effective_mult = round(base_mult * size_multiplier, 4)
        effective_mult = max(0.01, min(1.0, effective_mult))
        return SignalRequest(
            symbol=ps.symbol,
            timeframe=ps.timeframe,
            action=ps.action,
            strategy_name=f"agent:{ps.strategy_name}",
            confidence=confidence,
            reason=reason,
            price=ps.price,
            size_multiplier=effective_mult,
            metadata={**ps.metadata, "agent_decision": True},
        )

    async def _emit_agent_dashboard(
        self,
        symbol: str,
        agent_output: AgentOutput,
        order_executed: bool | None,
        effective_confidence: float | None = None,
        size_multiplier: float | None = None,
        news_headlines: list[NewsHeadline] | None = None,
    ) -> None:
        if self._event_store is None:
            return
        detail: dict = {
            "decision": agent_output.decision.value,
            "confidence": agent_output.confidence,
            "reason": agent_output.reason,
        }
        if effective_confidence is not None:
            detail["effective_confidence"] = effective_confidence
        if size_multiplier is not None:
            detail["size_multiplier"] = size_multiplier
        if order_executed is not None:
            detail["order_executed"] = order_executed
        if news_headlines:
            detail["news_headlines"] = [
                {
                    "title": h.title,
                    "source": h.source,
                    "url": h.url,
                    "published_at": h.published_at,
                }
                for h in news_headlines[:10]
            ]
            detail["news_count"] = len(news_headlines)
        title = f"AI {agent_output.decision.value}: {agent_output.reason[:72]}"
        assert self._event_store is not None
        await self._event_store.append_new(
            kind=DashboardEventKind.AGENT,
            symbol=symbol,
            title=title,
            detail=detail,
        )
