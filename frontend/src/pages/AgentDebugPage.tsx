import { useCallback, useEffect, useState } from 'react'
import { createAgentDebugDemoEvent, fetchAgentDebugRecent } from '../api/dashboardApi'
import type { AgentDebugItem } from '../types/api'
import { AppHeader } from '../components/AppHeader'
import { formatReportDateTime } from '../lib/datetime'
import {
  analystTitleEs,
  decisionLabelEs,
  humanizeDriverLine,
  scorePlainEs,
  stanceLabelEs,
} from '../lib/agentHumanize'

function decisionClass(decision: string | null): string {
  if (decision === 'ENTER') return 'pnl-pos'
  if (decision === 'SKIP') return 'pnl-neg'
  return ''
}

function formatPct(v: number | null): string {
  if (v === null || Number.isNaN(v)) return '—'
  return `${(v * 100).toFixed(2)}%`
}

function stanceClassName(stance: string): string {
  const s = stance.toLowerCase()
  if (s === 'bullish') return 'analyst-stance analyst-stance-bullish'
  if (s === 'bearish') return 'analyst-stance analyst-stance-bearish'
  if (s === 'mixed') return 'analyst-stance analyst-stance-mixed'
  return 'analyst-stance analyst-stance-neutral'
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
        setSeedMsg(
          `Listo: la IA eligió «${decisionLabelEs(res.agent_decision)}» con convicción ${(res.agent_confidence * 100).toFixed(0)}%.`,
        )
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
            <h2>Historial de la IA (legible)</h2>
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
            Aquí ves las últimas veces que el bot pidió opinión a la IA: qué decidió, con qué convicción, qué titulares
            vio si las noticias están activas y los tres resúmenes automáticos en palabras sencillas. Horas en{' '}
            <strong>America/Asuncion</strong> (Paraguay).
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
                  <th>Qué decidió la IA</th>
                  <th>Convicción</th>
                  <th>¿Se ejecutó orden?</th>
                  <th>Titulares</th>
                  <th>Lecturas automáticas</th>
                  <th>Explicación y noticias</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.event_id}>
                    <td>{formatReportDateTime(r.ts)}</td>
                    <td>{r.symbol}</td>
                    <td className={decisionClass(r.decision)}>{decisionLabelEs(r.decision)}</td>
                    <td>
                      <span className="debug-conf-label">Declarada:</span> {formatPct(r.confidence)}
                      <br />
                      <span className="debug-conf-label">Tras ajustes:</span>{' '}
                      {formatPct(r.effective_confidence)}
                    </td>
                    <td>
                      {r.order_executed === null
                        ? '—'
                        : r.order_executed
                          ? 'Sí (pasó riesgo)'
                          : 'No (riesgo u otro motivo)'}
                    </td>
                    <td>{r.news_count === 0 ? 'Ninguno' : `${r.news_count} titular(es)`}</td>
                    <td className="debug-analyst-cell">
                      {(r.analyst_summaries ?? []).length === 0 ? (
                        <span className="text-muted">—</span>
                      ) : (
                        <div className="analyst-cards analyst-cards-debug">
                          {(r.analyst_summaries ?? []).map((a) => (
                            <div key={`${r.event_id}-${a.analyst_id}`} className="analyst-card analyst-card-compact">
                              <div className="analyst-card-head">
                                <span className="analyst-card-title" title={a.analyst_id}>
                                  {analystTitleEs(a.analyst_id)}
                                </span>
                                <span className={stanceClassName(a.stance)}>{stanceLabelEs(a.stance)}</span>
                              </div>
                              <p className="debug-analyst-one-liner">{scorePlainEs(a.score, a.stance)}</p>
                              {a.drivers[0] ? (
                                <p className="debug-analyst-driver">{humanizeDriverLine(a.drivers[0])}</p>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      )}
                    </td>
                    <td>
                      <div className="debug-reason-wrap">
                        <span className="debug-conf-label">Motivo de la IA:</span> {r.reason ?? '—'}
                      </div>
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
