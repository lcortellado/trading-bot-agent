/** Mirrors backend JSON contracts (app/schemas + agents). */

export type DashboardEventKind = 'agent' | 'signal' | 'position' | 'strategy'

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
