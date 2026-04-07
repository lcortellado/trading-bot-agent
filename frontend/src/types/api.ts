/** Mirrors backend JSON contracts (app/schemas + agents). */

export type DashboardEventKind = 'agent' | 'signal' | 'position' | 'strategy' | 'auto'

export interface DashboardEvent {
  id: string
  ts: string
  kind: DashboardEventKind
  symbol: string
  title: string
  detail: Record<string, unknown>
}

export interface PositionSnapshot {
  symbol: string
  side: string
  entry_price: string
  quantity: string
  stop_loss: string | null
  take_profit: string | null
}

export interface DashboardSnapshot {
  capital: string
  daily_pnl: string
  open_positions: number
  positions: PositionSnapshot[]
}

/** Read-only server config (no secrets) — GET /api/dashboard/config */
export interface DashboardPublicConfig {
  app_name: string
  app_version: string
  debug: boolean
  trading_mode: string
  paper_initial_capital: number
  max_position_size_pct: number
  max_open_positions: number
  max_daily_drawdown_pct: number
  default_stop_loss_pct: number
  default_take_profit_pct: number
  default_symbol: string
  default_timeframe: string
  sma_short_period: number
  sma_long_period: number
  position_monitor_interval: number
  dashboard_max_events: number
  ai_enabled: boolean
  ai_provider: string
  ai_model: string
  openai_model: string
  ai_timeout: number
  ai_anthropic_key_configured: boolean
  ai_openai_key_configured: boolean
  auto_trading_enabled: boolean
  auto_trading_interval_seconds: number
  auto_trading_symbols: string
  auto_trading_timeframe: string
  auto_trading_strategy_names: string
  auto_trading_use_ai: boolean
  auto_trading_skip_if_open: boolean
  auto_trading_cooldown_seconds: number
  auto_trading_candle_limit: number
}

export type SignalAction = 'buy' | 'sell' | 'hold'
export type Timeframe =
  | '1m'
  | '5m'
  | '15m'
  | '30m'
  | '1h'
  | '4h'
  | '1d'

export interface SignalRequest {
  symbol: string
  timeframe: Timeframe
  action: SignalAction
  strategy_name: string
  confidence: number
  reason: string
  price: string
  size_multiplier?: number
  metadata?: Record<string, unknown>
}

export interface SignalResponse {
  accepted: boolean
  signal_action: SignalAction
  symbol: string
  reason: string
  risk_check_passed: boolean
  order_id: string | null
}

export interface MarketContext {
  volume_ratio?: number | null
  volatility_24h?: number | null
  trend?: string | null
}

export interface AgentSignalRequest {
  primary_signal: SignalRequest
  signals: SignalRequest[]
  market_context?: MarketContext | null
}

export type AgentDecision = 'ENTER' | 'SKIP' | 'REDUCE_SIZE'

export interface AgentDecisionResponse {
  agent_decision: AgentDecision
  agent_confidence: number
  agent_reason: string
  order_executed: boolean
  signal_response: SignalResponse | null
}

export interface RunStrategyResponse {
  strategy_name: string
  symbol: string
  timeframe: Timeframe
  action: string
  confidence: number
  reason: string
  candles_analyzed: number
}
