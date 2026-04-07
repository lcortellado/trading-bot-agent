import { useState } from 'react'
import { postAgentDecide } from '../api/tradingApi'
import type { SignalAction, Timeframe } from '../types/api'

export function AgentForm({ onDone }: { onDone: () => void }) {
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [timeframe, setTimeframe] = useState<Timeframe>('1h')
  const [action, setAction] = useState<SignalAction>('buy')
  const [strategyName, setStrategyName] = useState('sma_crossover')
  const [confidence, setConfidence] = useState(0.72)
  const [reason, setReason] = useState('Bundle demo: cruce alcista + volumen')
  const [price, setPrice] = useState('50000')
  const [secReason, setSecReason] = useState('RSI no sobrecomprado')
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setMsg(null)
    const primary = {
      symbol,
      timeframe,
      action,
      strategy_name: strategyName,
      confidence,
      reason,
      price,
    }
    const secondary = {
      symbol,
      timeframe,
      action: 'hold' as const,
      strategy_name: 'context_rsi',
      confidence: 0.55,
      reason: secReason,
      price,
    }
    try {
      const res = await postAgentDecide({
        primary_signal: primary,
        signals: [primary, secondary],
        market_context: { trend: 'bullish', volume_ratio: 1.15 },
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
      <h3>Agente IA (POST /agent/decide)</h3>
      <p style={{ fontSize: '0.8rem', color: 'var(--muted)', marginTop: 0 }}>
        Requiere API key (OpenAI o Anthropic) en el backend. Sin clave, la IA devuelve SKIP.
      </p>
      <div className="form-row">
        <label>Símbolo</label>
        <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} required />
      </div>
      <div className="form-row">
        <label>Timeframe</label>
        <select value={timeframe} onChange={(e) => setTimeframe(e.target.value as Timeframe)}>
          <option value="1h">1h</option>
          <option value="4h">4h</option>
          <option value="1d">1d</option>
        </select>
      </div>
      <div className="form-row">
        <label>Acción primaria</label>
        <select value={action} onChange={(e) => setAction(e.target.value as SignalAction)}>
          <option value="buy">buy</option>
          <option value="sell">sell</option>
        </select>
      </div>
      <div className="form-row">
        <label>Estrategia</label>
        <input value={strategyName} onChange={(e) => setStrategyName(e.target.value)} required />
      </div>
      <div className="form-row">
        <label>Confianza</label>
        <input
          type="number"
          step="0.01"
          min={0}
          max={1}
          value={confidence}
          onChange={(e) => setConfidence(parseFloat(e.target.value))}
        />
      </div>
      <div className="form-row">
        <label>Precio</label>
        <input value={price} onChange={(e) => setPrice(e.target.value)} required />
      </div>
      <div className="form-row">
        <label>Motivo señal principal</label>
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} required />
      </div>
      <div className="form-row">
        <label>Motivo señal secundaria (contexto)</label>
        <textarea value={secReason} onChange={(e) => setSecReason(e.target.value)} required />
      </div>
      <button type="submit" className="btn" disabled={loading}>
        {loading ? 'Consultando…' : 'Consultar agente'}
      </button>
      {msg && (
        <div className={msg.ok ? 'alert alert-success' : 'alert alert-error'}>{msg.text}</div>
      )}
    </form>
  )
}
