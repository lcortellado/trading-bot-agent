"""
Abstract exchange client.
All exchange integrations must implement this interface.
Business logic never imports a concrete exchange class directly.
"""
from abc import ABC, abstractmethod
from decimal import Decimal

from app.domain.models import Candle, Order
from app.domain.enums import OrderSide, OrderType, Timeframe


class ExchangeClient(ABC):
    """Interface for any exchange integration."""

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 100,
    ) -> list[Candle]:
        """Fetch OHLCV candlestick data."""
        ...

    @abstractmethod
    async def get_ticker_price(self, symbol: str) -> Decimal:
        """Get the latest trade price for a symbol."""
        ...

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> Order:
        """Submit an order. In testnet/paper mode this is always simulated."""
        ...

    @abstractmethod
    async def get_account_balance(self) -> dict[str, Decimal]:
        """Return available balances keyed by asset (e.g. {'USDT': Decimal('1000')})."""
        ...

    @abstractmethod
    async def ping(self) -> bool:
        """Check exchange connectivity. Returns True if reachable."""
        ...
