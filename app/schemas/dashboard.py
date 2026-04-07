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
    AUTO = "auto"


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


class DashboardPublicConfig(BaseModel):
    """
    Non-secret settings snapshot for the web UI (read-only).
    Secrets (API keys) are never included — only booleans that a key is set.
    """

    app_name: str
    app_version: str
    debug: bool
    trading_mode: str
    paper_initial_capital: float

    max_position_size_pct: float
    max_open_positions: int
    max_daily_drawdown_pct: float
    default_stop_loss_pct: float
    default_take_profit_pct: float

    default_symbol: str
    default_timeframe: str
    sma_short_period: int
    sma_long_period: int

    position_monitor_interval: int
    dashboard_max_events: int

    ai_enabled: bool
    ai_provider: str
    ai_model: str
    openai_model: str
    ai_timeout: int
    ai_anthropic_key_configured: bool
    ai_openai_key_configured: bool

    auto_trading_enabled: bool
    auto_trading_interval_seconds: int
    auto_trading_symbols: str
    auto_trading_timeframe: str
    auto_trading_strategy_names: str
    auto_trading_use_ai: bool
    auto_trading_skip_if_open: bool
    auto_trading_cooldown_seconds: int
    auto_trading_candle_limit: int
