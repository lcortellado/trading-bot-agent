"""
Pydantic schemas for the Signal API layer.
Decoupled from the domain model — the API contract can evolve independently.
"""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import SignalAction, Timeframe


class SignalRequest(BaseModel):
    """Inbound signal — e.g., from an external webhook or strategy runner."""
    symbol: str = Field(..., min_length=1, max_length=20, examples=["BTCUSDT"])
    timeframe: Timeframe
    action: SignalAction
    strategy_name: str = Field(..., min_length=1, max_length=64)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., min_length=1, description="Why this signal was generated")
    price: Decimal = Field(..., gt=0)
    metadata: dict = Field(default_factory=dict)

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.upper()


class SignalResponse(BaseModel):
    """Result after processing a signal through risk management."""
    accepted: bool
    signal_action: SignalAction
    symbol: str
    reason: str
    risk_check_passed: bool
    order_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SignalListResponse(BaseModel):
    signals: list[SignalResponse]
    total: int
