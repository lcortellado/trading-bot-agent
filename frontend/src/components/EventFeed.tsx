import { useEffect, useState } from "react";

import type { DashboardEvent } from "../types/api";
import { fetchEvents } from "../api/dashboardApi";

function kindClass(k: string) {
  return `kind kind-${k}`;
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
            <th>Hora (UTC)</th>
            <th>Tipo</th>
            <th>Símbolo</th>
            <th>Resumen</th>
          </tr>
        </thead>
        <tbody>
          {events.map((ev) => (
            <tr key={ev.id + ev.ts}>
              <td>{ev.ts.replace("T", " ").slice(0, 19)}</td>
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
    </>
  );
}
