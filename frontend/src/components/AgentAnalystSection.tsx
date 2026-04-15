import { useCallback, useEffect, useState } from 'react'

import { fetchAgentDebugRecent } from '../api/dashboardApi'
import type { AgentDebugAnalystRow, AgentDebugItem } from '../types/api'
import { formatReportDateTime } from '../lib/datetime'
import {
  analystConfidencePlainEs,
  analystSubtitleEs,
  analystTitleEs,
  decisionLabelEs,
  humanizeDriverLine,
  scorePlainEs,
  stanceLabelEs,
} from '../lib/agentHumanize'

function stanceClass(stance: string): string {
  const s = stance.toLowerCase()
  if (s === 'bullish') return 'analyst-stance analyst-stance-bullish'
  if (s === 'bearish') return 'analyst-stance analyst-stance-bearish'
  if (s === 'mixed') return 'analyst-stance analyst-stance-mixed'
  return 'analyst-stance analyst-stance-neutral'
}

function AnalystCards({ rows }: { rows: AgentDebugAnalystRow[] }) {
  if (!rows.length) {
    return (
      <p className="analyst-empty">
        Aquí aparecerían tres lecturas automáticas (señales, mercado, titulares), pero este evento no las
        trae guardadas.
      </p>
    )
  }
  return (
    <div className="analyst-cards">
      {rows.map((a) => (
        <div key={a.analyst_id} className="analyst-card">
          <div className="analyst-card-head">
            <span className="analyst-card-title">{analystTitleEs(a.analyst_id)}</span>
            <span className={stanceClass(a.stance)} title="Lectura automática, no una orden">
              {stanceLabelEs(a.stance)}
            </span>
          </div>
          <p className="analyst-card-hint">{analystSubtitleEs(a.analyst_id)}</p>
          <p className="analyst-human-line">{scorePlainEs(a.score, a.stance)}</p>
          <p className="analyst-human-line analyst-human-muted">{analystConfidencePlainEs(a.confidence)}</p>
          {a.drivers.length > 0 && (
            <ul className="analyst-drivers">
              {a.drivers.map((d, i) => (
                <li key={`${a.analyst_id}-${i}`}>{humanizeDriverLine(d)}</li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  )
}

type Props = {
  refreshToken?: number
}

export function AgentAnalystSection({ refreshToken = 0 }: Props) {
  const [rows, setRows] = useState<AgentDebugItem[]>([])
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(() => {
    fetchAgentDebugRecent(12)
      .then((r) => {
        setRows(r.events)
        setErr(null)
      })
      .catch((e: Error) => setErr(e.message))
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 4000)
    return () => clearInterval(id)
  }, [load])

  useEffect(() => {
    if (refreshToken > 0) load()
  }, [refreshToken, load])

  return (
    <section className="block analyst-section-block">
      <div className="analyst-section-head">
        <h2>Qué miró el sistema antes de la IA</h2>
        <button type="button" className="btn btn-secondary btn-small" onClick={() => load()}>
          Recargar
        </button>
      </div>
      <p className="analyst-section-intro">
        Son <strong>tres chequeos automáticos</strong> en lenguaje sencillo: señales del bot, datos de mercado
        que enviaste y titulares si están activos. No sustituyen al modelo de IA ni a las reglas de riesgo:
        solo ayudan a contextualizar la última decisión.
      </p>

      {err && (
        <div className="alert alert-error">
          No se pudo cargar esta sección: {err}
          <br />
          Comprueba que el backend esté en marcha y el proxy de Vite apunte al API.
        </div>
      )}

      {!err && rows.length === 0 && (
        <p className="empty">
          Todavía no hay decisiones recientes. Cuando uses el formulario <strong>Agente</strong> (o el
          auto-trading con IA), aquí verás el mismo resumen que recibió el modelo.
        </p>
      )}

      {!err && rows.length > 0 && (
        <div className="analyst-runs">
          {rows.map((r) => (
            <article key={r.event_id} className="analyst-run-card">
              <header className="analyst-run-head">
                <span className="analyst-run-time">{formatReportDateTime(r.ts)}</span>
                <span className="analyst-run-symbol">{r.symbol}</span>
                <span
                  className={
                    r.decision === 'ENTER'
                      ? 'analyst-run-decision pnl-pos'
                      : r.decision === 'SKIP'
                        ? 'analyst-run-decision pnl-neg'
                        : 'analyst-run-decision'
                  }
                  title="Decisión sugerida por la IA (luego pasa por riesgo)"
                >
                  {decisionLabelEs(r.decision)}
                </span>
                {r.confidence != null && (
                  <span className="analyst-run-conf" title="Grado de convicción declarado por la IA (0–100%)">
                    seguridad de la IA: {(r.confidence * 100).toFixed(0)}%
                  </span>
                )}
              </header>
              {r.reason && (
                <p className="analyst-run-reason">
                  <span className="analyst-run-reason-label">Por qué decidió así la IA:</span> {r.reason}
                </p>
              )}
              <h3 className="analyst-run-sub">Lecturas automáticas que vio antes</h3>
              <AnalystCards rows={r.analyst_summaries ?? []} />
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
