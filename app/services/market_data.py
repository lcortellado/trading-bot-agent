"""
Market data service.
Abstracts data fetching — strategies never call exchange clients directly.
"""
from decimal import Decimal

from app.core.logging import get_logger
from app.domain.enums import Timeframe
from app.domain.models import Candle
from app.exchange.base import ExchangeClient

log = get_logger(__name__)


class MarketDataService:
    def __init__(self, exchange: ExchangeClient) -> None:
        self._exchange = exchange

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 100,
    ) -> list[Candle]:
        log.debug("Fetching %d candles for %s [%s]", limit, symbol, timeframe.value)
        candles = await self._exchange.get_candles(symbol, timeframe, limit)
        if not candles:
            raise ValueError(f"No candle data returned for {symbol}/{timeframe.value}")
        return candles

    async def get_current_price(self, symbol: str) -> Decimal:
        return await self._exchange.get_ticker_price(symbol)

    async def is_exchange_reachable(self) -> bool:
        return await self._exchange.ping()
