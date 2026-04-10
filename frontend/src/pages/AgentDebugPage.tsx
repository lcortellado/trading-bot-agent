import { useCallback, useEffect, useState } from 'react'
import { createAgentDebugDemoEvent, fetchAgentDebugRecent } from '../api/dashboardApi'
import type { AgentDebugItem } from '../types/api'
import { AppHeader } from '../components/AppHeader'

function formatTs(ts: string): string {
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ts
  return d.toLocaleString()
}

function decisionClass(decision: string | null): string {
  if (decision === 'ENTER') return 'pnl-pos'
  if (decision === 'SKIP') return 'pnl-neg'
  return ''
}

function formatPct(v: number | null): string {
  if (v === null || Number.isNaN(v)) return '—'
  return `${(v * 100).toFixed(2)}%`
}

export function AgentDebugPage() {
  const [rows, setRows] = useState<AgentDebugItem[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [seedMsg, setSeedMsg] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [seeding, setSeeding] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    fetchAgentDebugRecent(30)
      .then((r) => {
        setRows(r.events)
        setErr(null)
      })
      .catch((e: Error) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [])

  const createDemoEvent = useCallback(() => {
    setSeeding(true)
    setSeedMsg(null)
    createAgentDebugDemoEvent()
      .then((res) => {
        setSeedMsg(`Evento creado: ${res.agent_decision} (${(res.agent_confidence * 100).toFixed(1)}%)`)
        load()
      })
      .catch((e: Error) => setErr(e.message))
      .finally(() => setSeeding(false))
  }, [load])

  useEffect(() => {
    load()
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [load])

  return (
    <>
      <AppHeader />

      <main className="layout">
        <section className="block">
          <div className="debug-toolbar">
            <h2>Debug IA (decisiones + noticias)</h2>
            <div className="debug-actions">
              <button className="btn btn-secondary btn-small" onClick={load}>
                Recargar
              </button>
              <button className="btn btn-small" onClick={createDemoEvent} disabled={seeding}>
                {seeding ? 'Generando...' : 'Generar evento demo'}
              </button>
            </div>
          </div>
          <p className="lab-table-legend">
            Muestra los ultimos eventos del endpoint <code>/agent/debug/recent</code> para verificar la decision de la IA
            y los titulares usados como contexto.
          </p>

          {err && <div className="alert alert-error">No se pudo cargar debug IA: {err}</div>}
          {seedMsg && <div className="alert alert-success">{seedMsg}</div>}
          {!err && loading && rows.length === 0 && <p className="empty">Cargando…</p>}
          {!err && !loading && rows.length === 0 && <p className="empty">Sin eventos de agente todavia.</p>}

          {rows.length > 0 && (
            <table className="feed">
              <thead>
                <tr>
                  <th>Hora</th>
                  <th>Simbolo</th>
                  <th>Decision</th>
                  <th>Confianza</th>
                  <th>Exec</th>
                  <th>Noticias</th>
                  <th>Razon / Titulares</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.event_id}>
                    <td>{formatTs(r.ts)}</td>
                    <td>{r.symbol}</td>
                    <td className={decisionClass(r.decision)}>{r.decision ?? '—'}</td>
                    <td>
                      base: {formatPct(r.confidence)}
                      <br />
                      eff: {formatPct(r.effective_confidence)}
                    </td>
                    <td>{r.order_executed === null ? '—' : r.order_executed ? 'Si' : 'No'}</td>
                    <td>{r.news_count}</td>
                    <td>
                      <div>{r.reason ?? '—'}</div>
                      {r.news_headlines.length > 0 && (
                        <ul className="debug-news-list">
                          {r.news_headlines.map((h, i) => (
                            <li key={`${r.event_id}-${i}`}>
                              {h.url ? (
                                <a href={h.url} target="_blank" rel="noreferrer">
                                  {h.title}
                                </a>
                              ) : (
                                h.title
                              )}
                              {h.source ? <span className="debug-news-meta"> · {h.source}</span> : null}
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </main>
    </>
  )
}
