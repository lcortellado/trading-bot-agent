"""GET /health — liveness and readiness check."""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import SettingsDep, get_market_data_service
from app.schemas.health import HealthResponse
from app.services.market_data import MarketDataService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health_check(
    settings: SettingsDep,
    market_data: Annotated[MarketDataService, Depends(get_market_data_service)],
) -> HealthResponse:
    exchange_ok = await market_data.is_exchange_reachable()

    return HealthResponse(
        status="ok" if exchange_ok else "degraded",
        version=settings.app_version,
        trading_mode=settings.trading_mode,
        exchange_connected=exchange_ok,
        details={
            "exchange": "binance_testnet",
            "base_url": settings.binance_testnet_base_url,
        },
    )
