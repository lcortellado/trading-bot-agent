/** Mirrors backend JSON contracts (app/schemas + agents). */

export type DashboardEventKind =
  | 'agent'
  | 'signal'
  | 'position'
  | 'strategy'
  | 'auto'
  | 'compare'

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
  news_context_enabled: boolean
  news_cryptopanic_configured: boolean
  auto_trading_enabled: boolean
  auto_trading_interval_seconds: number
  auto_trading_symbols: string
  auto_trading_timeframe: string
  auto_trading_strategy_names: string
  auto_trading_use_ai: boolean
  auto_trading_skip_if_open: boolean
  auto_trading_cooldown_seconds: number
  auto_trading_candle_limit: number
  strategy_lab_enabled: boolean
  strategy_lab_interval_seconds: number
  strategy_lab_symbols: string
  strategy_lab_timeframe: string
  strategy_lab_strategy_names: string
  strategy_lab_candle_limit: number
  strategy_lab_notional_usd: number
  strategy_lab_tp_multiplier: number
  strategy_lab_sl_min_pct: number
  strategy_lab_sl_max_pct: number
  strategy_lab_use_combined_signals: boolean
}

export interface StrategyLabLaneRow {
  strategy_name: string
  description: string
  symbol: string
  entry_price: string | null
  mark_price: string | null
  position_notional_usd: string | null
  unrealized_pnl: string | null
  realized_pnl: string
  trades: number
  wins: number
  losses: number
  in_position: boolean
  stop_loss: string | null
  take_profit: string | null
  last_action: string | null
  last_exit_reason: string | null
  last_confidence: number | null
}

export interface StrategyLabLeaderboardRow {
  strategy_name: string
  description: string
  total_pnl: string
  total_trades: number
  wins: number
  losses: number
}

export interface StrategyLabSnapshot {
  enabled: boolean
  notional_usd: number
  /** ISO UTC timestamp of last completed lab tick (null if never ran). */
  last_tick_at: string | null
  tick_count: number
  rows: StrategyLabLaneRow[]
  leaderboard: StrategyLabLeaderboardRow[]
}

export interface ChartCandlePoint {
  time: number
  open: number
  high: number
  low: number
  close: number
}

export interface ChartLinePoint {
  time: number
  value: number
}

export interface ChartCrossPoint {
  time: number
  side: 'buy' | 'sell'
  price: number
}

export interface StrategyLabChartData {
  symbol: string
  timeframe: string
  strategy_name: string
  sma_short_period: number
  sma_long_period: number
  candles: ChartCandlePoint[]
  sma_short: ChartLinePoint[]
  sma_long: ChartLinePoint[]
  crosses: ChartCrossPoint[]
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

export interface AgentDebugHeadline {
  title: string
  source: string | null
  url: string | null
  published_at: string | null
}

export interface AgentDebugAnalystRow {
  analyst_id: string
  stance: string
  score: number
  confidence: number
  drivers: string[]
}

export interface AgentDebugItem {
  event_id: string
  ts: string
  symbol: string
  decision: AgentDecision | null
  confidence: number | null
  reason: string | null
  effective_confidence: number | null
  size_multiplier: number | null
  order_executed: boolean | null
  news_count: number
  news_headlines: AgentDebugHeadline[]
  analyst_summaries?: AgentDebugAnalystRow[]
}

export interface AgentDebugRecentResponse {
  events: AgentDebugItem[]
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
