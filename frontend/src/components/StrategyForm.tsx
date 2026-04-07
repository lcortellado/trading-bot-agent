import { useState } from 'react'
import { postStrategyRun } from '../api/tradingApi'

export function StrategyForm({ onDone }: { onDone: () => void }) {
  const [strategyName, setStrategyName] = useState('sma_crossover')
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [timeframe, setTimeframe] = useState('1h')
  const [limit, setLimit] = useState(100)
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setMsg(null)
    try {
      const res = await postStrategyRun({
        strategy_name: strategyName,
        symbol,
        timeframe,
        limit,
      })
      setMsg({ ok: true, text: JSON.stringify(res, null, 2) })
      onDone()
    } catch (er) {
      setMsg({ ok: false, text: er instanceof Error ? er.message : String(er) })
    } finally {
      setLoading(false)
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h3>Estrategia SMA (POST /strategy/run)</h3>
      <p style={{ fontSize: '0.8rem', color: 'var(--muted)', marginTop: 0 }}>
        Descarga velas del testnet y calcula la señala. Requiere red al exchange.
      </p>
      <div className="form-row">
        <label>Estrategia</label>
        <input value={strategyName} onChange={(e) => setStrategyName(e.target.value)} />
      </div>
      <div className="form-row">
        <label>Símbolo</label>
        <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
      </div>
      <div className="form-row">
        <label>Timeframe</label>
        <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
          <option value="1h">1h</option>
          <option value="4h">4h</option>
          <option value="1d">1d</option>
        </select>
      </div>
      <div className="form-row">
        <label>Límite de velas</label>
        <input
          type="number"
          min={20}
          max={500}
          value={limit}
          onChange={(e) => setLimit(parseInt(e.target.value, 10))}
        />
      </div>
      <button type="submit" className="btn btn-secondary" disabled={loading}>
        {loading ? 'Ejecutando…' : 'Ejecutar estrategia'}
      </button>
      {msg && (
        <div className={msg.ok ? 'alert alert-success' : 'alert alert-error'}>{msg.text}</div>
      )}
    </form>
  )
}
