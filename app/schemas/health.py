"""Health check schemas."""
from pydantic import BaseModel

from app.domain.enums import TradingMode


class HealthResponse(BaseModel):
    status: str
    version: str
    trading_mode: TradingMode
    exchange_connected: bool
    details: dict = {}
