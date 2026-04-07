"""
FastAPI dependency injection.

Singleton services (SignalService, AgentService) are stored on app.state and
initialized once in the lifespan (see app/main.py).  Reading them via
Request.app.state ensures all requests share the same in-memory position state.

Stateless helpers (RiskManager, MarketDataService, strategies) are still
constructed per-request because they hold no mutable state.
"""
from typing import Annotated

from fastapi import Depends, Request

from app.agents.agent_service import AgentService
from app.core.config import Settings, get_settings
from app.exchange.base import ExchangeClient
from app.exchange.binance import BinanceClient
from app.risk_management.risk_manager import RiskManager
from app.services.market_data import MarketDataService
from app.services.signal_service import SignalService
from app.strategies.base import Strategy
from app.strategies.sma_crossover import get_available_strategies


SettingsDep = Annotated[Settings, Depends(get_settings)]


# ── Stateless per-request deps ─────────────────────────────────────────────────


def get_exchange(settings: SettingsDep) -> ExchangeClient:
    return BinanceClient(settings)


def get_risk_manager(settings: SettingsDep) -> RiskManager:
    return RiskManager(settings)


def get_market_data_service(
    exchange: Annotated[ExchangeClient, Depends(get_exchange)],
) -> MarketDataService:
    return MarketDataService(exchange)


def get_strategies() -> dict[str, Strategy]:
    return get_available_strategies()


# ── Singleton deps from app.state ──────────────────────────────────────────────


def get_signal_service(request: Request) -> SignalService:
    """
    Returns the singleton SignalService that holds in-memory position state.
    Initialised once in app/main.py lifespan; shared across all requests.
    """
    return request.app.state.signal_service


def get_agent_service(request: Request) -> AgentService:
    """Returns the singleton AgentService (wraps AIDecisionClient + SignalService)."""
    return request.app.state.agent_service
