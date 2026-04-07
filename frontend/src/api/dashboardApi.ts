import { apiGet } from './client'
import type { DashboardEvent, DashboardPublicConfig, DashboardSnapshot } from '../types/api'

export function fetchSnapshot(): Promise<DashboardSnapshot> {
  return apiGet<DashboardSnapshot>('/api/dashboard/snapshot')
}

export function fetchPublicConfig(): Promise<DashboardPublicConfig> {
  return apiGet<DashboardPublicConfig>('/api/dashboard/config')
}

export function fetchEvents(limit = 200): Promise<{ events: DashboardEvent[] }> {
  return apiGet<{ events: DashboardEvent[] }>(`/api/dashboard/events?limit=${limit}`)
}
