"""
API-layer Pydantic schemas for the AI agent endpoint.

Decoupled from internal agent schemas (app/agents/schemas.py) so the API
contract can evolve independently of the AI integration.
"""
from pydantic import BaseModel, Field

from app.agents.schemas import AgentDecision, MarketContext
from app.schemas.signal import SignalRequest, SignalResponse


class AgentSignalRequest(BaseModel):
    """
    Multi-signal bundle submitted to POST /agent/decide.

    Fields:
        primary_signal: The signal that will be executed (paper/testnet order)
                        if the agent decides ENTER or REDUCE_SIZE AND RiskManager approves.
        signals:        All signals for the AI to synthesize (must include or
                        describe the primary signal; can contain additional
                        indicators from other strategies).
        market_context: Optional enrichment — volume ratio, volatility, trend.
    """

    primary_signal: SignalRequest = Field(
        ..., description="Signal to execute on ENTER/REDUCE_SIZE decision"
    )
    signals: list[SignalRequest] = Field(
        ...,
        min_length=1,
        description="All signals the AI agent should consider for synthesis",
    )
    market_context: MarketContext | None = Field(
        default=None,
        description="Optional market context (volume, volatility, trend)",
    )


class AgentDecisionResponse(BaseModel):
    """
    Full response from POST /agent/decide.

    agent_decision:  ENTER | SKIP | REDUCE_SIZE
    agent_confidence: AI's confidence in its decision (0–1)
    agent_reason:    Mandatory explanation (why enter or why skip)
    order_executed:  True if an order was placed after ENTER/REDUCE_SIZE + risk approval
    signal_response: Populated when order_executed is True; contains order_id and risk details
    """

    agent_decision: AgentDecision
    agent_confidence: float
    agent_reason: str
    order_executed: bool
    signal_response: SignalResponse | None = None
