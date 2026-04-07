import { useEffect, useState } from 'react'
import { fetchEvents } from '../api/dashboardApi'
import type { DashboardEvent } from '../types/api'

function kindClass(k: string) {
  return `kind kind-${k}`
}

export function EventFeed() {
  const [events, setEvents] = useState<DashboardEvent[]>([])
  const [err, setErr] = useState<string | null>(null)

  const load = () => {
    fetchEvents(150)
      .then((d) => {
        setEvents(d.events)
        setErr(null)
      })
      .catch((e: Error) => setErr(e.message))
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 2500)
    return () => clearInterval(id)
  }, [])

  if (err) {
    return (
      <div className="alert alert-error">
        No se pudo cargar el feed: {err}
        <br />
        ¿Está el backend en :8000 y el proxy de Vite activo?
      </div>
    )
  }

  if (events.length === 0) {
    return (
      <p className="empty">
        Sin eventos. Usa los formularios de abajo o la API. La actividad aparecerá aquí.
      </p>
    )
  }

  return (
    <table className="feed">
      <thead>
        <tr>
          <th>Hora (UTC)</th>
          <th>Tipo</th>
          <th>Símbolo</th>
          <th>Resumen</th>
        </tr>
      </thead>
      <tbody>
        {events.map((ev) => (
          <tr key={ev.id + ev.ts}>
            <td>{ev.ts.replace('T', ' ').slice(0, 19)}</td>
            <td>
              <span className={kindClass(ev.kind)}>{ev.kind}</span>
            </td>
            <td>{ev.symbol}</td>
            <td>
              <strong>{ev.title}</strong>
              <pre className="detail-json">{JSON.stringify(ev.detail)}</pre>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
