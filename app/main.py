"""
Application entry point.
Wires up FastAPI, routers, and startup/shutdown lifecycle.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.api.routes import health, strategy, signal

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging(debug=settings.debug)
    log.info(
        "Starting %s v%s | mode=%s",
        settings.app_name,
        settings.app_version,
        settings.trading_mode.value,
    )
    yield
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

    return app


app = create_app()
