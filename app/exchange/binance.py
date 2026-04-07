"""
Binance Testnet exchange client.
Base URL: https://testnet.binance.vision/api/v3

Authentication: HMAC-SHA256 signature on every signed endpoint.
Paper mode: place_order is fully simulated without hitting Binance.
"""
import hashlib
import hmac
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.enums import OrderSide, OrderStatus, OrderType, TradingMode, Timeframe
from app.domain.models import Candle, Order
from app.exchange.base import ExchangeClient

log = get_logger(__name__)

# Binance klines column positions
_OPEN_TIME = 0
_OPEN = 1
_HIGH = 2
_LOW = 3
_CLOSE = 4
_VOLUME = 5
_CLOSE_TIME = 6


class BinanceClient(ExchangeClient):
    """
    Connects to Binance Testnet (https://testnet.binance.vision).
    When trading_mode=PAPER, no orders are sent to the exchange.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.binance_testnet_base_url
        self._api_key = settings.binance_api_key
        self._secret = settings.binance_secret_key
        self._timeout = settings.binance_request_timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"X-MBX-APIKEY": self._api_key},
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _sign(self, params: dict) -> dict:
        """Add timestamp and HMAC-SHA256 signature to signed requests."""
        params["timestamp"] = int(time.time() * 1000)
        query = "&".join(f"{k}={v}" for k, v in params.items())
        signature = hmac.new(
            self._secret.encode(),
            query.encode(),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    async def ping(self) -> bool:
        try:
            client = await self._get_client()
            response = await client.get("/ping")
            response.raise_for_status()
            log.debug("Binance testnet ping OK")
            return True
        except Exception as exc:
            log.warning("Binance testnet ping failed: %s", exc)
            return False

    async def get_ticker_price(self, symbol: str) -> Decimal:
        client = await self._get_client()
        response = await client.get("/ticker/price", params={"symbol": symbol})
        response.raise_for_status()
        data = response.json()
        return Decimal(data["price"])

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 100,
    ) -> list[Candle]:
        client = await self._get_client()
        response = await client.get(
            "/klines",
            params={"symbol": symbol, "interval": timeframe.value, "limit": limit},
        )
        response.raise_for_status()
        raw = response.json()

        candles: list[Candle] = []
        for row in raw:
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=datetime.fromtimestamp(row[_OPEN_TIME] / 1000, tz=timezone.utc),
                    open=Decimal(row[_OPEN]),
                    high=Decimal(row[_HIGH]),
                    low=Decimal(row[_LOW]),
                    close=Decimal(row[_CLOSE]),
                    volume=Decimal(row[_VOLUME]),
                    close_time=datetime.fromtimestamp(row[_CLOSE_TIME] / 1000, tz=timezone.utc),
                )
            )

        log.debug("Fetched %d candles for %s/%s", len(candles), symbol, timeframe.value)
        return candles

    async def get_account_balance(self) -> dict[str, Decimal]:
        if not self._api_key or not self._secret:
            log.warning("No API credentials — returning empty balance")
            return {}

        client = await self._get_client()
        params = self._sign({})
        response = await client.get("/account", params=params)
        response.raise_for_status()
        data = response.json()

        return {
            asset["asset"]: Decimal(asset["free"])
            for asset in data["balances"]
            if Decimal(asset["free"]) > 0
        }

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> Order:
        order = Order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            trading_mode=self._settings.trading_mode,
        )

        if self._settings.trading_mode == TradingMode.PAPER:
            return self._simulate_order(order)

        # Testnet execution
        if not self._api_key or not self._secret:
            raise RuntimeError("API credentials required for testnet order execution")

        params: dict = {
            "symbol": symbol,
            "side": side.value,
            "type": order_type.value,
            "quantity": str(quantity),
        }
        if order_type == OrderType.LIMIT and price is not None:
            params["price"] = str(price)
            params["timeInForce"] = "GTC"

        signed = self._sign(params)
        client = await self._get_client()
        response = await client.post("/order", params=signed)
        response.raise_for_status()
        data = response.json()

        order.order_id = str(data["orderId"])
        order.status = OrderStatus.NEW
        log.info("Testnet order placed: %s %s %s qty=%s", side, symbol, order_type, quantity)
        return order

    def _simulate_order(self, order: Order) -> Order:
        """Simulate order fill for paper trading — no network call."""
        order.order_id = f"PAPER-{uuid.uuid4().hex[:8].upper()}"
        order.status = OrderStatus.FILLED
        order.filled_qty = order.quantity
        order.filled_price = order.price
        log.info(
            "Paper order simulated: %s %s qty=%s id=%s",
            order.side,
            order.symbol,
            order.quantity,
            order.order_id,
        )
        return order
