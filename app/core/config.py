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

    # Automated trading loop (3Commas-style: periodic scan → signals → AI (optional) → risk → order)
    auto_trading_enabled: bool = Field(default=False, alias="AUTO_TRADING_ENABLED")
    auto_trading_interval_seconds: int = Field(default=300, ge=30, alias="AUTO_TRADING_INTERVAL_SECONDS")
    auto_trading_symbols: str = Field(default="BTCUSDT", alias="AUTO_TRADING_SYMBOLS")
    auto_trading_timeframe: str = Field(default="1h", alias="AUTO_TRADING_TIMEFRAME")
    auto_trading_strategy_names: str = Field(
        default="sma_crossover",
        alias="AUTO_TRADING_STRATEGIES",
    )
    auto_trading_use_ai: bool = Field(default=True, alias="AUTO_TRADING_USE_AI")
    auto_trading_skip_if_open: bool = Field(default=True, alias="AUTO_TRADING_SKIP_IF_OPEN")
    auto_trading_cooldown_seconds: int = Field(
        default=3600,
        ge=0,
        alias="AUTO_TRADING_COOLDOWN_SECONDS",
    )
    auto_trading_candle_limit: int = Field(default=120, ge=30, alias="AUTO_TRADING_CANDLE_LIMIT")

    # Strategy lab — paper-only: run several strategies on the same candles; rank by simulated PnL
    strategy_lab_enabled: bool = Field(default=False, alias="STRATEGY_LAB_ENABLED")
    strategy_lab_interval_seconds: int = Field(default=300, ge=30, alias="STRATEGY_LAB_INTERVAL_SECONDS")
    strategy_lab_symbols: str = Field(default="BTCUSDT", alias="STRATEGY_LAB_SYMBOLS")
    strategy_lab_timeframe: str = Field(default="5m", alias="STRATEGY_LAB_TIMEFRAME")
    strategy_lab_strategy_names: str = Field(
        default="sma_crossover,sma_5_15,sma_13_34",
        alias="STRATEGY_LAB_STRATEGIES",
    )
    strategy_lab_candle_limit: int = Field(default=120, ge=30, alias="STRATEGY_LAB_CANDLE_LIMIT")
    strategy_lab_notional_usd: float = Field(default=1000.0, gt=0, alias="STRATEGY_LAB_NOTIONAL_USD")
    # Exit model for lab lanes: TP distance = SL distance * multiplier.
    # SL% is estimated from recent volatility and clamped to [min, max].
    strategy_lab_tp_multiplier: float = Field(default=1.2, gt=0, alias="STRATEGY_LAB_TP_MULTIPLIER")
    strategy_lab_sl_min_pct: float = Field(default=0.005, gt=0, alias="STRATEGY_LAB_SL_MIN_PCT")
    strategy_lab_sl_max_pct: float = Field(default=0.02, gt=0, alias="STRATEGY_LAB_SL_MAX_PCT")
    strategy_lab_use_combined_signals: bool = Field(
        default=True,
        alias="STRATEGY_LAB_USE_COMBINED_SIGNALS",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — one load per process lifetime."""
    return Settings()
