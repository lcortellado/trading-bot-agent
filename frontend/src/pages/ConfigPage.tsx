import { useEffect, useState } from 'react'
import { fetchPublicConfig } from '../api/dashboardApi'
import type { DashboardPublicConfig } from '../types/api'
import { AppHeader } from '../components/AppHeader'

function ConfigTable({ rows }: { rows: { label: string; value: string | number | boolean }[] }) {
  return (
    <table className="config-table">
      <tbody>
        {rows.map((row) => (
          <tr key={row.label}>
            <th scope="row">{row.label}</th>
            <td>{typeof row.value === 'boolean' ? (row.value ? 'Sí' : 'No') : String(row.value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function ConfigPage() {
  const [cfg, setCfg] = useState<DashboardPublicConfig | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    fetchPublicConfig()
      .then((c) => {
        setCfg(c)
        setErr(null)
      })
      .catch((e: Error) => setErr(e.message))
  }, [])

  return (
    <>
      <AppHeader />

      <main className="layout config-layout">
        <section className="block">
          <h2>Configuración</h2>
          <p className="config-intro">
            Valores efectivos al iniciar el servidor (variables de entorno / <code>.env</code>). Para
            cambiarlos, edita el entorno y reinicia la API. Las claves de API no se muestran; solo si
            están definidas.
          </p>

          {err && (
            <div className="alert alert-error">
              No se pudo cargar la configuración: {err}
            </div>
          )}

          {!err && !cfg && <p className="empty">Cargando…</p>}

          {cfg && (
            <div className="config-sections">
              <div className="card">
                <h3>Aplicación</h3>
                <ConfigTable
                  rows={[
                    { label: 'Nombre', value: cfg.app_name },
                    { label: 'Versión', value: cfg.app_version },
                    { label: 'Debug', value: cfg.debug },
                  ]}
                />
              </div>

              <div className="card">
                <h3>Trading</h3>
                <ConfigTable
                  rows={[
                    { label: 'Modo', value: cfg.trading_mode },
                    { label: 'Capital paper (inicial)', value: cfg.paper_initial_capital },
                    { label: 'Símbolo por defecto', value: cfg.default_symbol },
                    { label: 'Timeframe por defecto', value: cfg.default_timeframe },
                  ]}
                />
              </div>

              <div className="card">
                <h3>Riesgo</h3>
                <ConfigTable
                  rows={[
                    { label: 'Máx. % capital por posición', value: cfg.max_position_size_pct },
                    { label: 'Máx. posiciones abiertas', value: cfg.max_open_positions },
                    { label: 'Máx. drawdown diario', value: cfg.max_daily_drawdown_pct },
                    { label: 'Stop loss por defecto', value: cfg.default_stop_loss_pct },
                    { label: 'Take profit por defecto', value: cfg.default_take_profit_pct },
                  ]}
                />
              </div>

              <div className="card">
                <h3>Estrategia SMA (por defecto)</h3>
                <ConfigTable
                  rows={[
                    { label: 'Periodo corto', value: cfg.sma_short_period },
                    { label: 'Periodo largo', value: cfg.sma_long_period },
                  ]}
                />
              </div>

              <div className="card">
                <h3>Monitor de posiciones</h3>
                <ConfigTable
                  rows={[
                    {
                      label: 'Intervalo comprobación SL/TP (s)',
                      value: cfg.position_monitor_interval,
                    },
                  ]}
                />
              </div>

              <div className="card">
                <h3>Dashboard</h3>
                <ConfigTable
                  rows={[{ label: 'Máx. eventos en memoria', value: cfg.dashboard_max_events }]}
                />
              </div>

              <div className="card">
                <h3>IA</h3>
                <ConfigTable
                  rows={[
                    { label: 'IA habilitada', value: cfg.ai_enabled },
                    { label: 'Proveedor', value: cfg.ai_provider },
                    { label: 'Modelo Anthropic', value: cfg.ai_model },
                    { label: 'Modelo OpenAI', value: cfg.openai_model },
                    { label: 'Timeout (s)', value: cfg.ai_timeout },
                    { label: 'Clave Anthropic configurada', value: cfg.ai_anthropic_key_configured },
                    { label: 'Clave OpenAI configurada', value: cfg.ai_openai_key_configured },
                    { label: 'Contexto noticias para IA (RSS/CryptoPanic)', value: cfg.news_context_enabled },
                    { label: 'CryptoPanic token configurado', value: cfg.news_cryptopanic_configured },
                  ]}
                />
              </div>

              <div className="card">
                <h3>Trading automático</h3>
                <ConfigTable
                  rows={[
                    { label: 'Activado', value: cfg.auto_trading_enabled },
                    { label: 'Intervalo (s)', value: cfg.auto_trading_interval_seconds },
                    { label: 'Símbolos', value: cfg.auto_trading_symbols },
                    { label: 'Timeframe velas', value: cfg.auto_trading_timeframe },
                    { label: 'Estrategias', value: cfg.auto_trading_strategy_names },
                    { label: 'Usar IA en el ciclo', value: cfg.auto_trading_use_ai },
                    { label: 'Omitir si hay posición abierta', value: cfg.auto_trading_skip_if_open },
                    { label: 'Cooldown tras orden (s)', value: cfg.auto_trading_cooldown_seconds },
                    { label: 'Límite de velas', value: cfg.auto_trading_candle_limit },
                  ]}
                />
              </div>

              <div className="card">
                <h3>Laboratorio (comparar estrategias en paper)</h3>
                <ConfigTable
                  rows={[
                    { label: 'Activado', value: cfg.strategy_lab_enabled },
                    { label: 'Intervalo (s)', value: cfg.strategy_lab_interval_seconds },
                    { label: 'Símbolos', value: cfg.strategy_lab_symbols },
                    { label: 'Timeframe', value: cfg.strategy_lab_timeframe },
                    { label: 'Estrategias a comparar', value: cfg.strategy_lab_strategy_names },
                    { label: 'Límite de velas', value: cfg.strategy_lab_candle_limit },
                    { label: 'Notional simulado (USD)', value: cfg.strategy_lab_notional_usd },
                    { label: 'TP multiplicador (R)', value: cfg.strategy_lab_tp_multiplier },
                    { label: 'SL mínimo (%)', value: cfg.strategy_lab_sl_min_pct },
                    { label: 'SL máximo (%)', value: cfg.strategy_lab_sl_max_pct },
                    { label: 'Usar señal combinada', value: cfg.strategy_lab_use_combined_signals },
                  ]}
                />
              </div>
            </div>
          )}
        </section>
      </main>

      <footer className="app-footer">
        Desarrollo: Vite :5173 → proxy al API :8000 · Producción: mismo origen bajo /dashboard/
      </footer>
    </>
  )
}
