"""
Pydantic models for dashboard API and in-memory event log.
"""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DashboardEventKind(str, Enum):
    AGENT = "agent"
    SIGNAL = "signal"
    POSITION = "position"
    STRATEGY = "strategy"
    AUTO = "auto"
    COMPARE = "compare"


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

    strategy_lab_enabled: bool
    strategy_lab_interval_seconds: int
    strategy_lab_symbols: str
    strategy_lab_timeframe: str
    strategy_lab_strategy_names: str
    strategy_lab_candle_limit: int
    strategy_lab_notional_usd: float
    strategy_lab_tp_multiplier: float
    strategy_lab_sl_min_pct: float
    strategy_lab_sl_max_pct: float
    strategy_lab_use_combined_signals: bool


class StrategyLabLaneRow(BaseModel):
    """One paper-simulation lane: strategy × symbol."""

    strategy_name: str
    description: str
    symbol: str
    realized_pnl: str
    trades: int
    wins: int
    losses: int
    in_position: bool
    stop_loss: str | None = None
    take_profit: str | None = None
    last_action: str | None = None
    last_exit_reason: str | None = None
    last_confidence: float | None = None


class StrategyLabLeaderboardRow(BaseModel):
    """Aggregated paper PnL per strategy (all symbols)."""

    strategy_name: str
    description: str
    total_pnl: str
    total_trades: int
    wins: int
    losses: int


class StrategyLabSnapshot(BaseModel):
    """Paper strategy comparison snapshot for GET /api/dashboard/strategy-lab."""

    enabled: bool
    notional_usd: float
    last_tick_at: str | None = None
    tick_count: int = 0
    rows: list[StrategyLabLaneRow]
    leaderboard: list[StrategyLabLeaderboardRow]


class ChartCandlePoint(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float


class ChartLinePoint(BaseModel):
    time: int
    value: float


class ChartCrossPoint(BaseModel):
    time: int
    side: str  # "buy" | "sell"
    price: float


class StrategyLabChartData(BaseModel):
    symbol: str
    timeframe: str
    strategy_name: str
    sma_short_period: int
    sma_long_period: int
    candles: list[ChartCandlePoint]
    sma_short: list[ChartLinePoint]
    sma_long: list[ChartLinePoint]
    crosses: list[ChartCrossPoint]
