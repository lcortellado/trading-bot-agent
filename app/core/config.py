"""
Centralized configuration via environment variables.
All secrets come from the environment — never hardcoded.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.enums import TradingMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "Crypto Trading Bot"
    app_version: str = "0.1.0"
    debug: bool = False

    # Trading safety — PAPER is the only default (see CLAUDE.md)
    trading_mode: TradingMode = TradingMode.PAPER

    # Binance Testnet
    binance_testnet_base_url: str = "https://testnet.binance.vision/api/v3"
    binance_api_key: str = Field(default="", alias="BINANCE_API_KEY")
    binance_secret_key: str = Field(default="", alias="BINANCE_SECRET_KEY")
    binance_request_timeout: int = 10  # seconds

    # Risk defaults
    max_position_size_pct: float = 0.02     # 2 % of capital per trade
    max_open_positions: int = 5
    max_daily_drawdown_pct: float = 0.05    # 5 % daily drawdown limit
    default_stop_loss_pct: float = 0.02     # 2 % stop loss
    default_take_profit_pct: float = 0.04   # 4 % take profit (2:1 RR)

    # Strategy defaults
    default_symbol: str = "BTCUSDT"
    default_timeframe: str = "1h"
    sma_short_period: int = 9
    sma_long_period: int = 21

    # Paper trading virtual capital
    paper_initial_capital: float = 10_000.0


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — one load per process lifetime."""
    return Settings()
