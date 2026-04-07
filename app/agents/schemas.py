"""
Internal Pydantic schemas for the AI agent layer.

These define the structured JSON contract between the bot and the AI model:
- AgentInput  → what we send to Claude (multi-signal bundle + context)
- AgentOutput → what Claude must return (decision + confidence + reason)

Using plain floats (not Decimal) because this data is for AI consumption,
not for financial calculations.
"""
from enum import Enum

from pydantic import BaseModel, Field


class AgentDecision(str, Enum):
    ENTER = "ENTER"
    SKIP = "SKIP"
    REDUCE_SIZE = "REDUCE_SIZE"


class SignalFeature(BaseModel):
    """One signal/indicator contributing to the decision bundle."""

    name: str
    action: str  # "buy", "sell", or "hold"
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str


class MarketContext(BaseModel):
    """Optional market enrichment passed to the agent."""

    volume_ratio: float | None = None     # current / average volume
    volatility_24h: float | None = None   # e.g. 0.03 = 3 %
    trend: str | None = None              # "bullish" | "bearish" | "sideways"


class RiskContext(BaseModel):
    """Snapshot of risk state — informational only, RiskManager enforces hard limits."""

    available_capital: float
    open_positions_count: int
    daily_pnl: float


class AgentInput(BaseModel):
    """Full structured bundle sent to the AI model as JSON."""

    symbol: str
    timeframe: str
    current_price: float
    signals: list[SignalFeature]
    market_context: MarketContext = Field(default_factory=MarketContext)
    risk_context: RiskContext


class AgentOutput(BaseModel):
    """Validated JSON output from the AI model."""

    decision: AgentDecision
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., min_length=1)
