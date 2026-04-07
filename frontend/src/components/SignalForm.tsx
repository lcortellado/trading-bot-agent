import { useState } from 'react'
import { postSignal } from '../api/tradingApi'
import type { SignalAction, Timeframe } from '../types/api'

export function SignalForm({ onDone }: { onDone: () => void }) {
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [timeframe, setTimeframe] = useState<Timeframe>('1h')
  const [action, setAction] = useState<SignalAction>('buy')
  const [strategyName, setStrategyName] = useState('web_ui')
  const [confidence, setConfidence] = useState(0.75)
  const [reason, setReason] = useState('Manual desde el panel web')
  const [price, setPrice] = useState('50000')
  const [sizeMult, setSizeMult] = useState(1)
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setMsg(null)
    try {
      const res = await postSignal({
        symbol,
        timeframe,
        action,
        strategy_name: strategyName,
        confidence,
        reason,
        price,
        size_multiplier: sizeMult,
      })
      setMsg({
        ok: true,
        text: JSON.stringify(res, null, 2),
      })
      onDone()
    } catch (er) {
      setMsg({ ok: false, text: er instanceof Error ? er.message : String(er) })
    } finally {
      setLoading(false)
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h3>Enviar señal → riesgo → orden</h3>
      <div className="form-row">
        <label>Símbolo</label>
        <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} required />
      </div>
      <div className="form-row">
        <label>Timeframe</label>
        <select value={timeframe} onChange={(e) => setTimeframe(e.target.value as Timeframe)}>
          <option value="1m">1m</option>
          <option value="5m">5m</option>
          <option value="15m">15m</option>
          <option value="30m">30m</option>
          <option value="1h">1h</option>
          <option value="4h">4h</option>
          <option value="1d">1d</option>
        </select>
      </div>
      <div className="form-row">
        <label>Acción</label>
        <select value={action} onChange={(e) => setAction(e.target.value as SignalAction)}>
          <option value="buy">buy</option>
          <option value="sell">sell</option>
          <option value="hold">hold</option>
        </select>
      </div>
      <div className="form-row">
        <label>Estrategia (nombre)</label>
        <input value={strategyName} onChange={(e) => setStrategyName(e.target.value)} required />
      </div>
      <div className="form-row">
        <label>Confianza (0–1)</label>
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
        <label>Precio (referencia)</label>
        <input value={price} onChange={(e) => setPrice(e.target.value)} required />
      </div>
      <div className="form-row">
        <label>Size multiplier (0.01–1)</label>
        <input
          type="number"
          step="0.05"
          min={0.01}
          max={1}
          value={sizeMult}
          onChange={(e) => setSizeMult(parseFloat(e.target.value))}
        />
      </div>
      <div className="form-row">
        <label>Motivo</label>
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} required />
      </div>
      <button type="submit" className="btn" disabled={loading}>
        {loading ? 'Enviando…' : 'POST /signal'}
      </button>
      {msg && (
        <div className={msg.ok ? 'alert alert-success' : 'alert alert-error'}>{msg.text}</div>
      )}
    </form>
  )
}
