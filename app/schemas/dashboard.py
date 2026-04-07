"""
Pydantic models for dashboard API and in-memory event log.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DashboardEventKind(str, Enum):
    AGENT = "agent"
    SIGNAL = "signal"
    POSITION = "position"
    STRATEGY = "strategy"


class DashboardEvent(BaseModel):
    """Single row in the activity feed (newest-first in API)."""
    id: str
    ts: datetime = Field(description="UTC timestamp")
    kind: DashboardEventKind
    symbol: str
    title: str
    detail: dict[str, Any] = Field(default_factory=dict)


class PositionSnapshot(BaseModel):
    symbol: str
    side: str
    entry_price: str
    quantity: str
    stop_loss: str | None
    take_profit: str | None


class DashboardSnapshot(BaseModel):
    """Current bot state for the dashboard header."""
    capital: str
    daily_pnl: str
    open_positions: int
    positions: list[PositionSnapshot]
