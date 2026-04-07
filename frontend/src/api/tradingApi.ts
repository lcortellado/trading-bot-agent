import { apiPost } from './client'
import type {
  AgentDecisionResponse,
  AgentSignalRequest,
  RunStrategyResponse,
  SignalRequest,
  SignalResponse,
} from '../types/api'

export function postSignal(body: SignalRequest): Promise<SignalResponse> {
  return apiPost<SignalResponse>('/signal', body)
}

export function postAgentDecide(body: AgentSignalRequest): Promise<AgentDecisionResponse> {
  return apiPost<AgentDecisionResponse>('/agent/decide', body)
}

export function postStrategyRun(body: {
  strategy_name: string
  symbol: string
  timeframe: string
  limit: number
}): Promise<RunStrategyResponse> {
  return apiPost<RunStrategyResponse>('/strategy/run', body)
}
