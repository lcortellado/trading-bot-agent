"""
FastAPI dependency injection.
All services are instantiated here and injected via Depends().
This keeps routes free of construction logic.
"""
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.exchange.binance import BinanceClient
from app.exchange.base import ExchangeClient
from app.risk_management.risk_manager import RiskManager
from app.services.market_data import MarketDataService
from app.services.signal_service import SignalService
from app.strategies.sma_crossover import get_available_strategies
from app.strategies.base import Strategy


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_exchange(settings: SettingsDep) -> ExchangeClient:
    return BinanceClient(settings)


def get_risk_manager(settings: SettingsDep) -> RiskManager:
    return RiskManager(settings)


def get_market_data_service(
    exchange: Annotated[ExchangeClient, Depends(get_exchange)],
) -> MarketDataService:
    return MarketDataService(exchange)


def get_signal_service(
    settings: SettingsDep,
    exchange: Annotated[ExchangeClient, Depends(get_exchange)],
    risk_manager: Annotated[RiskManager, Depends(get_risk_manager)],
) -> SignalService:
    return SignalService(exchange, risk_manager, settings)


def get_strategies() -> dict[str, Strategy]:
    return get_available_strategies()
