"""Pydantic schemas for Strategy API endpoints."""
from pydantic import BaseModel, Field

from app.domain.enums import Timeframe


class StrategyInfo(BaseModel):
    name: str
    description: str
    parameters: dict


class StrategyListResponse(BaseModel):
    strategies: list[StrategyInfo]
    total: int


class RunStrategyRequest(BaseModel):
    strategy_name: str = Field(..., examples=["sma_crossover"])
    symbol: str = Field(..., examples=["BTCUSDT"])
    timeframe: Timeframe = Field(default=Timeframe.H1)
    limit: int = Field(default=100, ge=10, le=1000, description="Number of candles to analyze")


class RunStrategyResponse(BaseModel):
    strategy_name: str
    symbol: str
    timeframe: Timeframe
    action: str
    confidence: float
    reason: str
    candles_analyzed: int
