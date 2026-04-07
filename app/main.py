"""
Application entry point.
Wires up FastAPI, singleton services, background tasks, and startup/shutdown lifecycle.
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agents.agent_service import AgentService
from app.agents.ai_client import AIDecisionClient
from app.api.routes import health, signal, strategy
from app.api.routes import agent as agent_route
from app.api.routes import dashboard as dashboard_route
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.dashboard.event_store import DashboardEventStore
from app.exchange.binance import BinanceClient
from app.risk_management.risk_manager import RiskManager
from app.services.auto_trading import AutoTradingLoop
from app.services.market_data import MarketDataService
from app.services.position_monitor import PositionMonitor
from app.services.signal_service import SignalService
from app.strategies.sma_crossover import get_available_strategies

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging(debug=settings.debug)

    # ── Build singleton services ────────────────────────────────────────────
    exchange = BinanceClient(settings)
    risk_manager = RiskManager(settings)
    event_store = DashboardEventStore(max_events=settings.dashboard_max_events)
    signal_service = SignalService(
        exchange, risk_manager, settings, event_store=event_store
    )
    ai_client = AIDecisionClient(settings)
    agent_service = AgentService(
        ai_client, signal_service, settings, event_store=event_store
    )

    app.state.signal_service = signal_service
    app.state.agent_service = agent_service
    app.state.event_store = event_store

    # ── Start position monitor background task ──────────────────────────────
    monitor = PositionMonitor(
        signal_service=signal_service,
        exchange=exchange,
        interval_seconds=settings.position_monitor_interval,
        event_store=event_store,
    )
    monitor_task = asyncio.create_task(monitor.run())

    auto_trading_task: asyncio.Task[None] | None = None
    if settings.auto_trading_enabled:
        market_data = MarketDataService(exchange)
        strategies = get_available_strategies()
        auto_loop = AutoTradingLoop(
            settings=settings,
            market_data=market_data,
            strategies=strategies,
            agent_service=agent_service,
            signal_service=signal_service,
            event_store=event_store,
        )
        auto_trading_task = asyncio.create_task(auto_loop.run())
        log.info(
            "Auto-trading loop enabled | interval=%ds | symbols=%s | strategies=%s",
            settings.auto_trading_interval_seconds,
            settings.auto_trading_symbols,
            settings.auto_trading_strategy_names,
        )

    ai_on = False
    if settings.ai_enabled:
        if settings.ai_provider.strip().lower() == "openai":
            ai_on = bool(settings.openai_api_key)
        else:
            ai_on = bool(settings.ai_api_key)
    log.info(
        "Starting %s v%s | mode=%s | ai_provider=%s | ai_ready=%s",
        settings.app_name,
        settings.app_version,
        settings.trading_mode.value,
        settings.ai_provider,
        ai_on,
    )
    log.info(
        "Web UI: React app under /dashboard (after npm run build)  ·  API docs: /docs  ·  "
        "OpenAI: AI_PROVIDER=openai + OPENAI_API_KEY  ·  "
        "Anthropic: AI_PROVIDER=anthropic + AI_API_KEY"
    )

    yield

    # ── Graceful shutdown ───────────────────────────────────────────────────
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    if auto_trading_task is not None:
        auto_trading_task.cancel()
        try:
            await auto_trading_task
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
    app.include_router(dashboard_route.router)

    # React production build (npm run build in frontend/) — dev uses Vite :5173 + proxy
    _ui_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if _ui_dist.is_dir() and (_ui_dist / "index.html").is_file():
        app.mount(
            "/dashboard",
            StaticFiles(directory=str(_ui_dist), html=True),
            name="dashboard_ui",
        )
        log.info("Serving React UI from %s at /dashboard/", _ui_dist)
    else:
        log.info("React UI not built — run: cd frontend && npm install && npm run build")

    return app


app = create_app()
