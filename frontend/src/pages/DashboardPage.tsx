import { useCallback, useEffect, useState } from 'react'
import { fetchSnapshot } from '../api/dashboardApi'
import type { DashboardSnapshot } from '../types/api'
import { AppHeader } from '../components/AppHeader'
import { StatsBar } from '../components/StatsBar'
import { EventFeed } from '../components/EventFeed'
import { SignalForm } from '../components/SignalForm'
import { AgentForm } from '../components/AgentForm'
import { StrategyForm } from '../components/StrategyForm'

export function DashboardPage() {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null)
  const [feedRefreshToken, setFeedRefreshToken] = useState(0)
  const refreshSnapshot = useCallback(() => {
    fetchSnapshot()
      .then(setSnapshot)
      .catch(() => setSnapshot(null))
  }, [])

  useEffect(() => {
    refreshSnapshot()
    const id = setInterval(refreshSnapshot, 3000)
    return () => clearInterval(id)
  }, [refreshSnapshot])

  const onAction = useCallback(() => {
    refreshSnapshot()
    setFeedRefreshToken((n) => n + 1)
  }, [refreshSnapshot])

  return (
    <>
      <AppHeader />

      <StatsBar snapshot={snapshot} />

      <main className="layout">
        <section className="block">
          <h2>Acciones</h2>
          <div className="forms-grid">
            <SignalForm onDone={onAction} />
            <AgentForm onDone={onAction} />
            <StrategyForm onDone={onAction} />
          </div>
        </section>

        <section className="block">
          <h2>Actividad reciente</h2>
          <EventFeed refreshToken={feedRefreshToken} />
        </section>
      </main>

      <footer className="app-footer">
        Desarrollo: Vite :5173 → proxy al API :8000 · Producción: mismo origen bajo /dashboard/
      </footer>
    </>
  )
}
