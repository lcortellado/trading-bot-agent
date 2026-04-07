"""
Application entry point.
Wires up FastAPI, singleton services, background tasks, and startup/shutdown lifecycle.
"""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.agent_service import AgentService
from app.agents.ai_client import AIDecisionClient
from app.api.routes import health, signal, strategy
from app.api.routes import agent as agent_route
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.exchange.binance import BinanceClient
from app.risk_management.risk_manager import RiskManager
from app.services.position_monitor import PositionMonitor
from app.services.signal_service import SignalService

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging(debug=settings.debug)

    # ── Build singleton services ────────────────────────────────────────────
    exchange = BinanceClient(settings)
    risk_manager = RiskManager(settings)
    signal_service = SignalService(exchange, risk_manager, settings)
    ai_client = AIDecisionClient(settings)
    agent_service = AgentService(ai_client, signal_service, settings)

    app.state.signal_service = signal_service
    app.state.agent_service = agent_service

    # ── Start position monitor background task ──────────────────────────────
    monitor = PositionMonitor(
        signal_service=signal_service,
        exchange=exchange,
        interval_seconds=settings.position_monitor_interval,
    )
    monitor_task = asyncio.create_task(monitor.run())

    log.info(
        "Starting %s v%s | mode=%s | ai_enabled=%s",
        settings.app_name,
        settings.app_version,
        settings.trading_mode.value,
        settings.ai_enabled and bool(settings.ai_api_key),
    )

    yield

    # ── Graceful shutdown ───────────────────────────────────────────────────
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    await exchange.close()
    log.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Crypto Trading Bot — paper trading & Binance testnet",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(strategy.router)
    app.include_router(signal.router)
    app.include_router(agent_route.router)

    return app


app = create_app()
