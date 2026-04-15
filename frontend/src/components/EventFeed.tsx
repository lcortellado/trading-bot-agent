import { useEffect, useState } from "react";

import type { DashboardEvent } from "../types/api";
import { fetchEvents } from "../api/dashboardApi";
import { formatReportDateTime } from "../lib/datetime";
import {
  analystSubtitleEs,
  analystTitleEs,
  decisionLabelEs,
  humanizeDriverLine,
  scorePlainEs,
  stanceLabelEs,
} from "../lib/agentHumanize";

function kindClass(k: string) {
  return `kind kind-${k}`;
}

/** Texto corto en español para la columna Tipo (el valor API sigue siendo el enum). */
function kindLabel(k: string): string {
  if (k === 'compare') return 'lab'
  return k
}

type LegacyLabTop = {
  strategy_name?: string
  description?: string
  total_pnl?: string
  total_trades?: number
  wins?: number
  losses?: number
}

type RankingRow = {
  puesto: number
  estrategia: string
  descripcion: string
  pnl_usd: string
  operaciones: number
  ganadas: number
  perdidas: number
}

function CompareEventDetail({ detail }: { detail: Record<string, unknown> }) {
  const resumen = typeof detail.resumen_ciclo === 'string' ? detail.resumen_ciclo : null
  const ranking = detail.ranking_top3
  const legacyTop = detail.leaderboard_top3

  const rows: RankingRow[] = Array.isArray(ranking)
    ? (ranking as RankingRow[]).filter(
        (r) =>
          typeof r.puesto === 'number' &&
          typeof r.estrategia === 'string' &&
          typeof r.pnl_usd === 'string',
      )
    : Array.isArray(legacyTop)
      ? (legacyTop as LegacyLabTop[]).map((r, i) => ({
          puesto: i + 1,
          estrategia: String(r.strategy_name ?? '—'),
          descripcion: String(r.description ?? ''),
          pnl_usd: String(r.total_pnl ?? '0'),
          operaciones: Number(r.total_trades ?? 0),
          ganadas: Number(r.wins ?? 0),
          perdidas: Number(r.losses ?? 0),
        }))
      : []

  const legacySignals = detail.signals_this_tick
  const legacySignalsText =
    Array.isArray(legacySignals) && legacySignals.length > 0 ? legacySignals.join('; ') : null

  return (
    <div className="compare-detail">
      {resumen && <p className="compare-resumen">{resumen}</p>}
      {!resumen && legacySignalsText && (
        <p className="compare-resumen">Señales (formato técnico): {legacySignalsText}</p>
      )}
      {rows.length > 0 && (
        <table className="compare-ranking">
          <thead>
            <tr>
              <th>#</th>
              <th>Estrategia</th>
              <th>PnL (USD)</th>
              <th>Ops</th>
              <th>G / P</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={`${r.puesto}-${r.estrategia}`}>
                <td>{r.puesto}</td>
                <td>
                  <code>{r.estrategia}</code>
                  {r.descripcion ? (
                    <span className="compare-desc"> — {r.descripcion}</span>
                  ) : null}
                </td>
                <td>{r.pnl_usd}</td>
                <td>{r.operaciones}</td>
                <td>
                  {r.ganadas} / {r.perdidas}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {!resumen && rows.length === 0 && (
        <pre className="detail-json">{JSON.stringify(detail)}</pre>
      )}
    </div>
  )
}

type AnalystRow = {
  analyst_id?: string
  stance?: string
  score?: number
  confidence?: number
  drivers?: string[]
}

function feedStanceClass(stance: string | undefined): string {
  const s = (stance ?? 'neutral').toLowerCase()
  if (s === 'bullish') return 'analyst-stance analyst-stance-bullish'
  if (s === 'bearish') return 'analyst-stance analyst-stance-bearish'
  if (s === 'mixed') return 'analyst-stance analyst-stance-mixed'
  return 'analyst-stance analyst-stance-neutral'
}

function AgentEventDetail({ detail }: { detail: Record<string, unknown> }) {
  const raw = detail.analyst_summaries
  const rows: AnalystRow[] = Array.isArray(raw)
    ? (raw as AnalystRow[]).filter((x) => typeof x?.analyst_id === 'string')
    : []

  if (rows.length === 0) {
    return <pre className="detail-json">{JSON.stringify(detail)}</pre>
  }

  return (
    <div className="agent-feed-detail">
      <div className="agent-feed-meta">
        {typeof detail.decision === 'string' && (
          <span className="agent-feed-decision">{decisionLabelEs(detail.decision)}</span>
        )}
        {typeof detail.confidence === 'number' && (
          <span className="agent-feed-conf">
            seguridad IA {(detail.confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
      {typeof detail.reason === 'string' && (
        <p className="agent-feed-reason">
          <span className="agent-feed-reason-label">Motivo: </span>
          {detail.reason}
        </p>
      )}
      <p className="agent-feed-sub">Resumen automático (no es la orden final):</p>
      <div className="analyst-cards analyst-cards-inline">
        {rows.map((a) => (
          <div key={String(a.analyst_id)} className="analyst-card analyst-card-compact">
            <div className="analyst-card-head">
              <span className="analyst-card-title">{analystTitleEs(String(a.analyst_id))}</span>
              <span className={feedStanceClass(a.stance)}>{stanceLabelEs(a.stance)}</span>
            </div>
            <p className="analyst-card-hint analyst-card-hint-compact">
              {analystSubtitleEs(String(a.analyst_id))}
            </p>
            {typeof a.score === 'number' && (
              <p className="analyst-human-line analyst-human-line-compact">
                {scorePlainEs(a.score, String(a.stance ?? 'neutral'))}
              </p>
            )}
            {Array.isArray(a.drivers) && a.drivers.length > 0 && (
              <ul className="analyst-drivers analyst-drivers-compact">
                {a.drivers.slice(0, 2).map((d, i) => (
                  <li key={`${String(a.analyst_id)}-${i}`}>{humanizeDriverLine(String(d))}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

type Props = {
  /** Increment from the parent after a successful POST so the feed refreshes immediately (polling is every 2.5s). */
  refreshToken?: number;
};

export function EventFeed({ refreshToken = 0 }: Props) {
  const [events, setEvents] = useState<DashboardEvent[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const load = () => {
    fetchEvents(150)
      .then((d) => {
        setEvents(d.events);
        setErr(null);
      })
      .catch((e: Error) => setErr(e.message));
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 2500);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (refreshToken > 0) load();
  }, [refreshToken]);

  if (err) {
    return (
      <div className="alert alert-error">
        No se pudo cargar el feed: {err}
        <br />
        ¿Está el backend en :8000 y el proxy de Vite activo?
        <br />
        <button
          type="button"
          className="btn btn-secondary feed-retry"
          onClick={() => load()}
        >
          Reintentar
        </button>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="feed-empty-wrap">
        <p className="empty">
          Aún no hay filas en el registro. Este listado <strong>no</strong> es
          el libro de órdenes del exchange: solo muestra lo que{" "}
          <strong>este bot ha procesado</strong> en esta API (memoria).
        </p>
        <ul className="feed-hints">
          <li>
            Envía una señal con el formulario <strong>Enviar señal</strong> o
            ejecuta <strong>Estrategia</strong> / <strong>Agente</strong>.
          </li>
          <li>
            Con <code>AUTO_TRADING_ENABLED=true</code> aparecerán filas{" "}
            <span className="kind kind-auto">auto</span> en cada ciclo que
            genere decisión.
          </li>
          <li>
            Si acabas de enviar algo y no ves nada, prueba recargar o espera
            unos segundos.
          </li>
        </ul>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => load()}
        >
          Recargar ahora
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="feed-toolbar">
        <button
          type="button"
          className="btn btn-secondary btn-small"
          onClick={() => load()}
        >
          Recargar
        </button>
      </div>
      <table className="feed">
        <thead>
          <tr>
            <th>Hora (Paraguay)</th>
            <th>Tipo</th>
            <th>Símbolo</th>
            <th>Resumen</th>
          </tr>
        </thead>
        <tbody>
          {events.map((ev) => (
            <tr key={ev.id + ev.ts}>
              <td>{formatReportDateTime(ev.ts)}</td>
              <td>
                <span className={kindClass(ev.kind)} title={ev.kind}>
                  {kindLabel(ev.kind)}
                </span>
              </td>
              <td>{ev.symbol}</td>
              <td>
                <strong>{ev.title}</strong>
                {ev.kind === 'compare' ? (
                  <CompareEventDetail detail={ev.detail} />
                ) : ev.kind === 'agent' ? (
                  <AgentEventDetail detail={ev.detail} />
                ) : (
                  <pre className="detail-json">{JSON.stringify(ev.detail)}</pre>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
