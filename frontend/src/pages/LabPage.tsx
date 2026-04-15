import { useCallback, useEffect, useState } from 'react'
import { fetchStrategyLab, fetchStrategyLabChart } from '../api/dashboardApi'
import { StrategyLabChart } from '../components/StrategyLabChart'
import type { StrategyLabChartData, StrategyLabSnapshot } from '../types/api'
import { AppHeader } from '../components/AppHeader'
import { formatReportDateTime } from '../lib/datetime'

function pnlClass(pnl: string): string {
  const n = parseFloat(pnl)
  if (Number.isNaN(n) || n === 0) return ''
  return n > 0 ? 'pnl-pos' : 'pnl-neg'
}

function pnlClassNullable(pnl: string | null): string {
  if (!pnl) return ''
  const n = parseFloat(pnl)
  if (Number.isNaN(n) || n === 0) return ''
  return n > 0 ? 'pnl-pos' : 'pnl-neg'
}

/** USD redondeado + % vs precio de entrada (solo posición abierta). */
function formatUnrealizedPnl(
  unrealizedUsd: string | null,
  entryPrice: string | null,
  markPrice: string | null,
): string {
  if (!unrealizedUsd) return '—'
  const usd = parseFloat(unrealizedUsd)
  if (Number.isNaN(usd)) return unrealizedUsd
  const entry = parseFloat(entryPrice ?? '')
  const mark = parseFloat(markPrice ?? '')
  const usdPart = `${usd.toFixed(2)} USD`
  if (!Number.isNaN(entry) && entry !== 0 && !Number.isNaN(mark)) {
    const pct = ((mark - entry) / entry) * 100
    const sign = pct > 0 ? '+' : ''
    return `${usdPart} (${sign}${pct.toFixed(2)}%)`
  }
  return usdPart
}

function formatUsdRounded(value: string): string {
  const n = parseFloat(value)
  if (Number.isNaN(n)) return value
  return `${n.toFixed(2)} USD`
}

export function LabPage() {
  const [data, setData] = useState<StrategyLabSnapshot | null>(null)
  const [chartData, setChartData] = useState<StrategyLabChartData | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [chartErr, setChartErr] = useState<string | null>(null)
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [strategyName, setStrategyName] = useState('sma_crossover')

  const load = useCallback(() => {
    fetchStrategyLab()
      .then((d) => {
        setData(d)
        setErr(null)
        if (d.rows.length > 0) {
          setSymbol((prev) => prev || d.rows[0].symbol)
          setStrategyName((prev) => prev || d.rows[0].strategy_name)
        }
      })
      .catch((e: Error) => setErr(e.message))
  }, [])

  const loadChart = useCallback(() => {
    if (!data?.enabled) return
    fetchStrategyLabChart({
      symbol,
      strategy_name: strategyName,
      limit: 300,
    })
      .then((d) => {
        setChartData(d)
        setChartErr(null)
      })
      .catch((e: Error) => setChartErr(e.message))
  }, [data?.enabled, strategyName, symbol])

  useEffect(() => {
    load()
    const id = setInterval(load, 4000)
    return () => clearInterval(id)
  }, [load])

  useEffect(() => {
    if (!data?.enabled) return
    loadChart()
    const id = setInterval(loadChart, 4000)
    return () => clearInterval(id)
  }, [data?.enabled, loadChart])

  const strategyOptions = Array.from(
    new Set((data?.rows.map((r) => r.strategy_name) ?? []).filter((n) => !n.startsWith('combo_'))),
  )
  const symbolOptions = Array.from(new Set(data?.rows.map((r) => r.symbol) ?? []))

  return (
    <>
      <AppHeader />

      <main className="layout config-layout">
        <section className="block">
          <h2>Laboratorio de estrategias (paper)</h2>
          <p className="config-intro">
            Misma vela para todas: cada estrategia tiene su carril virtual (solo largos) y un PnL simulado
            independiente. No son órdenes reales ni el capital del panel principal. Activa con{' '}
            <code>STRATEGY_LAB_ENABLED=true</code> y reinicia la API. Notional por operación simulada:{' '}
            {data ? `${data.notional_usd} USD` : '—'}.
          </p>
          <p className="config-intro lab-why-empty">
            <strong>¿Todo en cero y “hold”?</strong> Es lo habitual al principio. El SMA solo emite{' '}
            <code>buy</code>/<code>sell</code> en el momento de un cruce; el resto del tiempo la señal es{' '}
            <code>hold</code>. El PnL solo sube cuando hay una venta que cierra un largo simulado — puede
            tardar varias velas u horas según el mercado y el timeframe (p. ej. 1h).
          </p>

          {err && (
            <div className="alert alert-error">
              No se pudo cargar el laboratorio: {err}
            </div>
          )}

          {data && !data.enabled && (
            <div className="alert alert-error">
              El laboratorio está desactivado. Pon <code>STRATEGY_LAB_ENABLED=true</code> en{' '}
              <code>.env</code> y reinicia el servidor para comparar estrategias en segundo plano.
            </div>
          )}

          {data?.enabled && (
            <>
              <div className="card lab-controls">
                <h3>Chart en tiempo real</h3>
                <div className="forms-grid">
                  <div className="form-row">
                    <label>Estrategia</label>
                    <select value={strategyName} onChange={(e) => setStrategyName(e.target.value)}>
                      {(strategyOptions.length > 0 ? strategyOptions : [strategyName]).map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="form-row">
                    <label>Símbolo</label>
                    <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
                      {(symbolOptions.length > 0 ? symbolOptions : [symbol]).map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                {chartErr && <div className="alert alert-error">No se pudo cargar el chart: {chartErr}</div>}
                <StrategyLabChart data={chartData} />
              </div>

              <p className="lab-status">
                Último ciclo:{' '}
                <strong>
                  {data.last_tick_at ? formatReportDateTime(data.last_tick_at) : '—'} (Paraguay)
                </strong>
                {' · '}
                Ciclos completados: <strong>{data.tick_count}</strong>
                {data.tick_count === 0 && (
                  <span className="lab-status-warn">
                    {' '}
                    (esperando el 1.er ciclo; ocurre cada intervalo configurado en{' '}
                    <code>STRATEGY_LAB_INTERVAL_SECONDS</code>. Si no sube nunca, revisa logs del API.)
                  </span>
                )}
              </p>
              <h3 className="lab-subtitle">Ranking (PnL total simulado)</h3>
              <table className="feed lab-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Estrategia</th>
                    <th>Descripción</th>
                    <th>Ops</th>
                    <th>G / P</th>
                    <th>PnL total</th>
                  </tr>
                </thead>
                <tbody>
                  {data.leaderboard.map((row, i) => (
                    <tr key={row.strategy_name}>
                      <td>{i + 1}</td>
                      <td>
                        <code>{row.strategy_name}</code>
                      </td>
                      <td>{row.description}</td>
                      <td>{row.total_trades}</td>
                      <td>
                        {row.wins} / {row.losses}
                      </td>
                      <td className={pnlClass(row.total_pnl)}>{formatUsdRounded(row.total_pnl)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h3 className="lab-subtitle">Detalle por símbolo</h3>
              <p className="lab-table-legend">
                <strong>Colores:</strong> en <em>PnL activo</em>, verde = la posición abierta va ganando frente al precio
                actual (no realizado). El valor se muestra en USD (2 decimales) y el porcentaje es el cambio del precio
                actual respecto al precio de entrada. En <em>PnL cerrado</em>, verde/rojo = suma de operaciones ya
                cerradas; puede ser negativo aunque el activo esté en verde.
              </p>
              <table className="feed lab-table">
                <thead>
                  <tr>
                    <th>Estrategia</th>
                    <th>Símbolo</th>
                    <th>Compra (entrada)</th>
                    <th>Monto (USD)</th>
                    <th>Precio actual</th>
                    <th>PnL activo</th>
                    <th>PnL cerrado</th>
                    <th>Ops</th>
                    <th>En posición</th>
                    <th>SL / TP</th>
                    <th>Última acción</th>
                    <th>Salida</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row) => (
                    <tr key={`${row.strategy_name}-${row.symbol}`}>
                      <td>
                        <code>{row.strategy_name}</code>
                      </td>
                      <td>{row.symbol}</td>
                      <td>{row.entry_price ?? '—'}</td>
                      <td>{row.position_notional_usd ?? '—'}</td>
                      <td>{row.mark_price ?? '—'}</td>
                      <td className={pnlClassNullable(row.unrealized_pnl)}>
                        {formatUnrealizedPnl(row.unrealized_pnl, row.entry_price, row.mark_price)}
                      </td>
                      <td className={pnlClass(row.realized_pnl)}>{formatUsdRounded(row.realized_pnl)}</td>
                      <td>{row.trades}</td>
                      <td>{row.in_position ? 'Sí' : 'No'}</td>
                      <td>
                        {row.stop_loss ?? '—'} / {row.take_profit ?? '—'}
                      </td>
                      <td>{row.last_action ?? '—'}</td>
                      <td>{row.last_exit_reason ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </section>
      </main>

      <footer className="app-footer">
        Desarrollo: Vite :5173 → proxy al API :8000 · Producción: mismo origen bajo /dashboard/
      </footer>
    </>
  )
}
