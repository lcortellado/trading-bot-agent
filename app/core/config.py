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
        populate_by_name=True,  # allow kwargs by Python field name even when alias is set
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

    # AI agent — Anthropic Claude and/or OpenAI (ChatGPT API)
    # Set AI_PROVIDER=openai with OPENAI_API_KEY, or anthropic (default) with AI_API_KEY
    ai_provider: str = Field(default="anthropic", alias="AI_PROVIDER")
    ai_api_key: str = Field(default="", alias="AI_API_KEY")
    ai_model: str = "claude-haiku-4-5-20251001"   # Anthropic model id
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    ai_timeout: int = 15                            # seconds; keep short to avoid blocking orders
    ai_enabled: bool = True                         # set False to bypass AI and use risk-only mode

    # Position monitor
    position_monitor_interval: int = 30            # seconds between SL/TP checks

    # Dashboard (in-memory event feed)
    dashboard_max_events: int = Field(default=500, alias="DASHBOARD_MAX_EVENTS")


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — one load per process lifetime."""
    return Settings()
