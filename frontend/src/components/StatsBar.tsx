import type { DashboardSnapshot } from '../types/api'

interface Props {
  snapshot: DashboardSnapshot | null
}

export function StatsBar({ snapshot }: Props) {
  if (!snapshot) {
    return (
      <section className="stats">
        <div className="stat">
          <label>Capital (paper)</label>
          <strong>—</strong>
        </div>
        <div className="stat">
          <label>PnL diario</label>
          <strong>—</strong>
        </div>
        <div className="stat">
          <label>Posiciones</label>
          <strong>—</strong>
        </div>
      </section>
    )
  }

  const pnl = parseFloat(snapshot.daily_pnl)
  const pnlClass = pnl >= 0 ? 'pnl-pos' : 'pnl-neg'

  return (
    <section className="stats">
      <div className="stat">
        <label>Capital (paper)</label>
        <strong>{snapshot.capital}</strong>
      </div>
      <div className="stat">
        <label>PnL diario</label>
        <strong className={pnlClass}>{snapshot.daily_pnl}</strong>
      </div>
      <div className="stat">
        <label>Posiciones abiertas</label>
        <strong>{snapshot.open_positions}</strong>
      </div>
      {snapshot.positions.length > 0 && (
        <div className="positions-mini">
          Abiertas:{' '}
          {snapshot.positions.map((p) => (
            <span key={`${p.symbol}-${p.side}`}>
              {p.symbol} {p.side} @ {p.entry_price}{' '}
            </span>
          ))}
        </div>
      )}
    </section>
  )
}
