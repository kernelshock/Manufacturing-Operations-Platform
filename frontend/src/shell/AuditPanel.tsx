import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { AuditEntry } from "../api/types";

export function AuditPanel() {
  const [events, setEvents] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .audit(20)
      .then(setEvents)
      .catch((caught) =>
        setError(
          caught instanceof Error
            ? caught.message
            : "No fue posible consultar auditoría."
        )
      );
  }, []);

  return (
    <section className="content-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Trazabilidad</p>
          <h2>Eventos de auditoría</h2>
        </div>
        <span className="status-pill neutral">Append-only</span>
      </div>
      {error ? <p className="inline-error">{error}</p> : null}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Actor</th>
              <th>Acción</th>
              <th>Objeto</th>
              <th>Resultado</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.id}>
                <td>{new Date(event.occurred_at).toLocaleString()}</td>
                <td>{event.actor_username ?? "Sistema / desconocido"}</td>
                <td><code>{event.action}</code></td>
                <td>{event.object_type}</td>
                <td>{event.outcome}</td>
              </tr>
            ))}
            {!events.length && !error ? (
              <tr>
                <td colSpan={5}>No hay eventos disponibles.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
