import { useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../api/client";
import { WhatIfPanel } from "./WhatIfPanel";
import type { GanttOperation, GanttProjection, ProductionPlan } from "../api/types";
import {
  offsetHours,
  pixelsPerHour,
  timelineWidthPx,
  widthHours,
  type GanttScale
} from "./ganttMath";

function fmt(value: string) {
  return new Intl.DateTimeFormat("es-AR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function durationMinutes(operation: GanttOperation) {
  return Math.round(Number(operation.processing_seconds) / 60);
}

export function GanttPanel({ canEdit }: { canEdit: boolean }) {
  const [plans, setPlans] = useState<ProductionPlan[]>([]);
  const [planId, setPlanId] = useState("");
  const [projection, setProjection] = useState<GanttProjection | null>(null);
  const [scale, setScale] = useState<GanttScale>("shift");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    api.productionPlans()
      .then((items) => {
        if (active) setPlans(items);
      })
      .catch(() => {
        if (active) setPlans([]);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.ganttProjection(planId || undefined)
      .then((data) => {
        if (!active) return;
        setProjection(data);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof ApiError ? reason.message : "No fue posible cargar el Gantt APS.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [planId, refreshKey]);

  const timelineWidth = useMemo(() => {
    if (!projection?.window_start || !projection.window_end) return 900;
    return timelineWidthPx(projection.window_start, projection.window_end, scale);
  }, [projection, scale]);

  const grouped = useMemo(() => {
    const map = new Map<string, GanttOperation[]>();
    for (const op of projection?.operations ?? []) {
      const key = `${op.plan_number} · ${op.taquilla_code}`;
      const rows = map.get(key) ?? [];
      rows.push(op);
      map.set(key, rows);
    }
    return Array.from(map.entries());
  }, [projection]);

  return (
    <>
      <section className="hero-panel">
        <div>
          <p className="eyebrow">G4 · APS</p>
          <h2>Gantt de capacidad finita publicado</h2>
          <p>
            Proyección de lectura del schedule backend. Las barras reflejan tiempos,
            recursos y pausas ya calculados por APS; el frontend no replanifica.
          </p>
        </div>
        <div className="gantt-controls">
          <label>
            Alcance
            <select value={planId} onChange={(event) => setPlanId(event.target.value)}>
              <option value="">Vista maestra</option>
              {plans.map((plan) => (
                <option key={plan.id} value={plan.id}>{plan.plan_number}</option>
              ))}
            </select>
          </label>
          <label>
            Escala
            <select value={scale} onChange={(event) => setScale(event.target.value as GanttScale)}>
              <option value="hour">Hora</option>
              <option value="shift">Turno</option>
              <option value="day">Día</option>
            </select>
          </label>
        </div>
      </section>

      {error ? <p className="inline-error">{error}</p> : null}
      {loading ? <p className="muted">Cargando schedule publicado…</p> : null}

      {projection ? (
        <>
          <section className="metric-grid">
            <article className="metric-card">
              <span>Operaciones</span><strong>{projection.operation_count}</strong><small>Publicado actual</small>
            </article>
            <article className="metric-card">
              <span>Taquillas</span><strong>{projection.taquilla_count}</strong><small>{projection.scope}</small>
            </article>
            <article className="metric-card">
              <span>Recursos</span><strong>{projection.resource_count}</strong><small>Asignados por APS</small>
            </article>
            <article className="metric-card">
              <span>Publicaciones</span><strong>{projection.publications.length}</strong><small>CURRENT visibles</small>
            </article>
          </section>

          <section className="content-section">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Estado explicable</p>
                <h2>Restricciones del schedule</h2>
              </div>
            </div>
            <div className="constraint-grid">
              <div>
                <strong>Evaluadas</strong>
                {projection.constraints_evaluated.map((item) => <span className="status-pill success" key={item}>{item}</span>)}
              </div>
              <div>
                <strong>No evaluadas todavía</strong>
                {projection.constraints_not_evaluated.map((item) => <span className="status-pill warning" key={item}>{item}</span>)}
              </div>
            </div>
          </section>

          <WhatIfPanel
            projection={projection}
            canEdit={canEdit}
            onApplied={() => setRefreshKey((value) => value + 1)}
          />

          <section className="content-section gantt-section">
            <div className="section-heading">
              <div>
                <p className="eyebrow">{projection.plan_number ?? "Master APS"}</p>
                <h2>Secuencia publicada</h2>
              </div>
              {projection.window_start && projection.window_end ? (
                <span className="muted">{fmt(projection.window_start)} → {fmt(projection.window_end)}</span>
              ) : null}
            </div>

            {projection.operations.length === 0 ? (
              <p className="muted">No existe un schedule CURRENT publicado para este alcance.</p>
            ) : (
              <div className="gantt-scroll">
                <div className="gantt-board" style={{ width: timelineWidth + 320 }}>
                  <div className="gantt-header-row">
                    <div className="gantt-label">Plan / Taquilla / Operación</div>
                    <div className="gantt-time-header" style={{ width: timelineWidth }}>
                      Escala {scale} · {pixelsPerHour(scale)} px/h
                    </div>
                  </div>
                  {grouped.flatMap(([group, operations]) => [
                    <div className="gantt-group" key={group}>{group}</div>,
                    ...operations.map((op) => {
                      const base = projection.window_start!;
                      const left = offsetHours(base, op.planned_start) * pixelsPerHour(scale);
                      const width = Math.max(3, widthHours(op.planned_start, op.planned_finish) * pixelsPerHour(scale));
                      return (
                        <div className="gantt-row" key={op.publication_id + op.sequence_no}>
                          <div className="gantt-label">
                            <strong>{op.operation_code}</strong>
                            <small>{op.article_code} · {op.resource_code}</small>
                            <small>{op.work_center_code} · {durationMinutes(op)} min productivos</small>
                          </div>
                          <div className="gantt-lane" style={{ width: timelineWidth }}>
                            <div className="gantt-envelope" style={{ left, width }} title={`${fmt(op.planned_start)} → ${fmt(op.planned_finish)}`}>
                              {op.segments.map((segment) => (
                                <span
                                  className="gantt-segment"
                                  key={segment.segment_no}
                                  style={{
                                    left: (offsetHours(op.planned_start, segment.start_at) / Math.max(widthHours(op.planned_start, op.planned_finish), 0.0001)) * 100 + "%",
                                    width: (widthHours(segment.start_at, segment.end_at) / Math.max(widthHours(op.planned_start, op.planned_finish), 0.0001)) * 100 + "%"
                                  }}
                                  title={`Segmento ${segment.segment_no}: ${fmt(segment.start_at)} → ${fmt(segment.end_at)}`}
                                />
                              ))}
                            </div>
                          </div>
                        </div>
                      );
                    })
                  ])}
                </div>
              </div>
            )}
          </section>
        </>
      ) : null}
    </>
  );
}
