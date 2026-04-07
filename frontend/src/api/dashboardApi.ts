import { apiGet } from './client'
import type { DashboardEvent, DashboardSnapshot } from '../types/api'

export function fetchSnapshot(): Promise<DashboardSnapshot> {
  return apiGet<DashboardSnapshot>('/api/dashboard/snapshot')
}

export function fetchEvents(limit = 200): Promise<{ events: DashboardEvent[] }> {
  return apiGet<{ events: DashboardEvent[] }>(`/api/dashboard/events?limit=${limit}`)
}
