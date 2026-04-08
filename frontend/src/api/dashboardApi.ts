import { apiGet } from './client'
import type {
  DashboardEvent,
  DashboardPublicConfig,
  DashboardSnapshot,
  StrategyLabChartData,
  StrategyLabSnapshot,
} from '../types/api'

export function fetchSnapshot(): Promise<DashboardSnapshot> {
  return apiGet<DashboardSnapshot>('/api/dashboard/snapshot')
}

export function fetchPublicConfig(): Promise<DashboardPublicConfig> {
  return apiGet<DashboardPublicConfig>('/api/dashboard/config')
}

export function fetchStrategyLab(): Promise<StrategyLabSnapshot> {
  return apiGet<StrategyLabSnapshot>('/api/dashboard/strategy-lab')
}

export function fetchStrategyLabChart(params: {
  symbol: string
  strategy_name: string
  timeframe?: string
  limit?: number
}): Promise<StrategyLabChartData> {
  const q = new URLSearchParams()
  q.set('symbol', params.symbol)
  q.set('strategy_name', params.strategy_name)
  if (params.timeframe) q.set('timeframe', params.timeframe)
  if (params.limit) q.set('limit', String(params.limit))
  return apiGet<StrategyLabChartData>(`/api/dashboard/strategy-lab/chart?${q.toString()}`)
}

export function fetchEvents(limit = 200): Promise<{ events: DashboardEvent[] }> {
  return apiGet<{ events: DashboardEvent[] }>(`/api/dashboard/events?limit=${limit}`)
}
