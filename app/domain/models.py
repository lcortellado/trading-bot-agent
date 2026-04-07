"""
Core domain models. Pure Python dataclasses — zero framework dependencies.
These represent the business concepts, independent of FastAPI, SQLAlchemy, or Binance.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.domain.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    SignalAction,
    Timeframe,
    TradingMode,
)


@dataclass
class Candle:
    """OHLCV candlestick data."""
    symbol: str
    timeframe: Timeframe
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time: datetime


@dataclass
class Signal:
    """
    Trading signal produced by a strategy.
    Includes reasoning so decisions can be audited (required by CLAUDE.md).
    """
    symbol: str
    timeframe: Timeframe
    action: SignalAction
    strategy_name: str
    confidence: float          # 0.0 – 1.0
    reason: str                # Why enter or skip — mandatory
    price: Decimal
    size_multiplier: float = 1.0  # scales max notional in RiskManager (e.g. AI REDUCE_SIZE)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be between 0 and 1, got {self.confidence}")
        if not self.reason:
            raise ValueError("Signal must include a reason explaining the decision")
        if not (0.0 < self.size_multiplier <= 1.0):
            raise ValueError(
                f"size_multiplier must be in (0, 1], got {self.size_multiplier}"
            )


@dataclass
class Order:
    """Represents an order sent to an exchange (or simulated in paper mode)."""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None      # None for MARKET orders
    status: OrderStatus = OrderStatus.NEW
    order_id: str | None = None
    filled_qty: Decimal = Decimal("0")
    filled_price: Decimal | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trading_mode: TradingMode = TradingMode.PAPER


@dataclass
class Position:
    """Open position tracking."""
    symbol: str
    side: OrderSide
    entry_price: Decimal
    quantity: Decimal
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    opened_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def notional(self) -> Decimal:
        return self.entry_price * self.quantity

    def unrealized_pnl(self, current_price: Decimal) -> Decimal:
        if self.side == OrderSide.BUY:
            return (current_price - self.entry_price) * self.quantity
        return (self.entry_price - current_price) * self.quantity
