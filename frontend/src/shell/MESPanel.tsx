import { useCallback, useEffect, useMemo, useState } from "react";
import { api, apiFetch } from "../api/client";
import type { OperationalPlanProjection } from "../api/types";
import { mesDisplayLabels } from "./mesDisplayLabels";
import { canCaptureOperation } from "./mesCaptureGuards";
import { MESAdvancedPanel } from "./MESAdvancedPanel";

type ResourceOption = { id: string; code: string; name: string; work_center_id: string };
type Dispatch = { id: string; dispatch_code: string; plan_id: string; status: string; operation_count: number };
type Operation = {
  id: string; dispatch_id: string; taquilla_id: string; product_line_id: string;
  operation_code: string; operation_description: string; status: string;
  routing_sequence_no: number; product_sequence_no: number; requested_quantity: string;
  produced_quantity: string | null; planned_start: string; planned_finish: string;
  actual_start: string | null; actual_finish: string | null;
};
type OperationFeedback = { classification: string; finish_delta_seconds: string | null; quantity_delta: string | null };
type DispatchFeedback = {
  classification: string; operation_count: number; completed_count: number;
  delayed_count: number; open_rework_count: number; quantity_shortfall_count: number;
  replan_review_recommended: boolean;
};
type ActionResponse = { idempotent_replay: boolean };
const base = "/api/v1/mes";
const states: Record<string, string> = {
  PENDING: "Pendiente", RUNNING: "En proceso", PAUSED: "Pausada",
  COMPLETED: "Completada", NOT_STARTED: "Sin iniciar", IN_PROGRESS: "En ejecución",
  ON_TIME: "En término", DELAYED: "Con demora", DRAFT: "Borrador",
  RELEASED: "Liberado", CANCELLED: "Cancelado",
};
const label = (s: string) => states[s] ?? s;
function date(value: string | null) {
  return value ? new Intl.DateTimeFormat("es-AR", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  }).format(new Date(value)) : "No registrado";
}
function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "No fue posible completar la operación.";
}

export function MESPanel({ canEdit, canReadDemand }: { canEdit: boolean; canReadDemand: boolean }) {
  const [dispatches, setDispatches] = useState<Dispatch[]>([]);
  const [dispatchId, setDispatchId] = useState("");
  const [operations, setOperations] = useState<Operation[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [feedback, setFeedback] = useState<DispatchFeedback | null>(null);
  const [planProjection, setPlanProjection] = useState<OperationalPlanProjection | null>(null);
  const [operationFeedback, setOperationFeedback] = useState<OperationFeedback | null>(null);
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState("");
  const [resourceId, setResourceId] = useState("");
  const [resourceReason, setResourceReason] = useState("");
  const [resourceOptions, setResourceOptions] = useState<ResourceOption[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let live = true;
    setLoading(true);
    apiFetch<Dispatch[]>(`${base}/dispatches`).then((items) => {
      if (!live) return;
      setDispatches(items);
      setDispatchId(current => items.some(item => item.id === current) ? current : (items[0]?.id ?? ""));
      setError("");
    }).catch((e: unknown) => { if (live) setError(errorMessage(e)); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [refresh]);

  useEffect(() => {
    let live = true;
    apiFetch<ResourceOption[]>(`${base}/resources`)
      .then(items => { if (live) setResourceOptions(items); })
      .catch(() => { if (live) setResourceOptions([]); });
    return () => { live = false; };
  }, []);

  useEffect(() => {
    if (!dispatchId) { setOperations([]); setFeedback(null); return; }
    let live = true;
    Promise.all([
      apiFetch<Operation[]>(`${base}/dispatches/${encodeURIComponent(dispatchId)}/operations`),
      apiFetch<DispatchFeedback>(`${base}/feedback/dispatches/${encodeURIComponent(dispatchId)}`),
    ]).then(([items, result]) => {
      if (!live) return;
      setOperations(items);
      setFeedback(result);
      setSelectedId(current => items.some(item => item.id === current) ? current : (items[0]?.id ?? ""));
      setError("");
    }).catch((e: unknown) => { if (live) setError(errorMessage(e)); });
    return () => { live = false; };
  }, [dispatchId, refresh]);

  useEffect(() => {
    if (!canReadDemand || !dispatchId) { setPlanProjection(null); return; }
    const dispatch = dispatches.find(item => item.id === dispatchId);
    if (!dispatch) { setPlanProjection(null); return; }
    let active = true;
    api.operationalProjection(dispatch.plan_id)
      .then(projection => { if (active) setPlanProjection(projection); })
      .catch(() => { if (active) setPlanProjection(null); });
    return () => { active = false; };
  }, [canReadDemand, dispatchId, dispatches]);

  useEffect(() => {
    if (!selectedId) { setOperationFeedback(null); return; }
    let live = true;
    apiFetch<OperationFeedback>(`${base}/feedback/operations/${encodeURIComponent(selectedId)}`)
      .then(item => { if (live) setOperationFeedback(item); })
      .catch(() => { if (live) setOperationFeedback(null); });
    return () => { live = false; };
  }, [selectedId, refresh]);

  const selected = operations.find(op => op.id === selectedId && op.dispatch_id === dispatchId) ?? null;
  const dispatch = dispatches.find(item => item.id === dispatchId) ?? null;
  const labels = useMemo(() => mesDisplayLabels(planProjection), [planProjection]);
  const groups = useMemo(() => {
    const result = new Map<string, Operation[]>();
    for (const op of operations.filter(item => item.dispatch_id === dispatchId)) {
      const key = `${op.taquilla_id} / ${op.product_line_id}`;
      result.set(key, [...(result.get(key) ?? []), op]);
    }
    return [...result.entries()];
  }, [operations, dispatchId]);

  const reload = useCallback(() => setRefresh(current => current + 1), []);
  async function submit(action: "start" | "complete" | "pause" | "resume") {
    if (!canCaptureOperation(selected, dispatchId, canEdit, dispatch?.status ?? null) || !selected) return;
    if (action === "complete" && (!/^(?:\d+)(?:\.\d{1,8})?$/.test(quantity) || Number(quantity) <= 0)) {
      setError("Ingresá una cantidad producida positiva con hasta ocho decimales.");
      return;
    }
    if (action === "pause" && !reason.trim()) {
      setError("Indicá el motivo de la interrupción.");
      return;
    }
    if (action === "start" && resourceReason.trim() && !resourceId.trim()) {
      setError("El motivo de desvío requiere indicar el recurso utilizado.");
      return;
    }
    setBusy(true); setError(""); setMessage("");
    try {
      let endpoint = `${base}/operations/${encodeURIComponent(selected.id)}/${action}`;
      let payload: Record<string, string> = {};
      if (action === "complete") payload = { produced_quantity: quantity };
      if (action === "pause") {
        endpoint = `${base}/operations/${encodeURIComponent(selected.id)}/pause`;
        payload = { reason_code: reason.trim() };
      }
      if (action === "resume") endpoint = `${base}/operations/${encodeURIComponent(selected.id)}/resume`;
      if (action === "start" && resourceId.trim()) {
        payload = { actual_resource_id: resourceId.trim() };
        if (resourceReason.trim()) payload.resource_deviation_reason = resourceReason.trim();
      }
      const result = await apiFetch<ActionResponse>(endpoint, { method: "POST", body: JSON.stringify(payload) });
      setMessage(result.idempotent_replay ? "Acción ya registrada (repetición idempotente)." : "Registro confirmado por MES.");
      setQuantity(""); setReason("");
      reload();
    } catch (e: unknown) {
      setError(errorMessage(e));
    } finally { setBusy(false); }
  }

  return (
    <>
      <section className="hero-panel">
        <div>
          <p className="eyebrow">G5.7 · Shop-floor</p>
          <h2>Seguimiento real de producción</h2>
          <p>Inicio, pausa, reanudación, fin y cantidades por operación. El registro real no modifica la programación APS publicada.</p>
        </div>
        <div className="demand-plan-selector">
          <label htmlFor="mes-dispatch">Despacho de producción</label>
          <select id="mes-dispatch" value={dispatchId} onChange={event => { setDispatchId(event.target.value); setOperations([]); setSelectedId(""); setFeedback(null); setOperationFeedback(null); setPlanProjection(null); setQuantity(""); setReason(""); setResourceId(""); setResourceReason(""); setMessage(""); setError(""); }}>
            {dispatches.length === 0 ? <option value="">Sin despachos</option> : null}
            {dispatches.map(item => (
              <option key={item.id} value={item.id}>{item.dispatch_code} · {label(item.status)}</option>
            ))}
          </select>
          <button type="button" onClick={reload} disabled={busy}>Actualizar datos</button>
        </div>
      </section>
      {loading ? <p className="muted">Cargando despachos…</p> : null}
      {error ? <p className="inline-error" role="alert">{error}</p> : null}
      {message ? <p className="status-pill success" role="status">{message}</p> : null}
      {dispatch && feedback ? (
        <section className="metric-grid">
          <article className="metric-card"><span>Operaciones completadas</span><strong>{feedback.completed_count} / {feedback.operation_count}</strong><small>{label(feedback.classification)}</small></article>
          <article className="metric-card"><span>Con demora</span><strong>{feedback.delayed_count}</strong><small>Según fecha publicada</small></article>
          <article className="metric-card"><span>Con menor cantidad</span><strong>{feedback.quantity_shortfall_count}</strong><small>Sin inferir scrap</small></article>
          <article className="metric-card"><span>Retrabajos abiertos</span><strong>{feedback.open_rework_count}</strong><small>{feedback.replan_review_recommended ? "Revisión recomendada" : "Sin alerta de revisión"}</small></article>
        </section>
      ) : null}
      {dispatches.length === 0 && !loading ? <section className="content-section"><p>Sin despachos disponibles. Es necesario crear y liberar un despacho MES desde una publicación APS antes de registrar ejecución.</p></section> : null}
      <section className="content-section">
        <div className="section-heading"><div><p className="eyebrow">Plan → Taquilla → Producto → Operación</p><h2>Operaciones del despacho</h2></div></div>
        <div className="mes-operation-grid">
          <div className="mes-operation-list">
            {groups.map(([key, items]) => (
              <div key={key}>
                <p className="muted mes-group-label">Taquilla {labels.get(`taquilla:${items[0].taquilla_id}`) ?? items[0].taquilla_id.slice(0, 8)} · Producto {labels.get(`product:${items[0].product_line_id}`) ?? items[0].product_line_id.slice(0, 8)}</p>
                {items.map(op => (
                  <button key={op.id} className={`mes-operation-row ${selectedId === op.id ? "selected" : ""}`}
                    type="button" aria-pressed={selectedId === op.id} onClick={() => { setSelectedId(op.id); setMessage(""); setError(""); }}>
                    <strong>{op.routing_sequence_no}. {op.operation_code} · {op.operation_description}</strong>
                    <span>{label(op.status)} · {op.produced_quantity ?? "—"} / {op.requested_quantity}</span>
                  </button>
                ))}
              </div>
            ))}
          </div>
          <div className="mes-capture-panel">
            {selected ? (
              <>
                <h3>{selected.operation_code} · {label(selected.status)}</h3>
                <p className="muted">{selected.operation_description}</p>
                <dl className="mes-facts">
                  <div><dt>Previsto</dt><dd>{date(selected.planned_start)} — {date(selected.planned_finish)}</dd></div>
                  <div><dt>Inicio real</dt><dd>{date(selected.actual_start)}</dd></div>
                  <div><dt>Fin real</dt><dd>{date(selected.actual_finish)}</dd></div>
                  <div><dt>Resultado</dt><dd>{operationFeedback ? label(operationFeedback.classification) : "Sin clasificación"}</dd></div>
                  <div><dt>Cantidad producida</dt><dd>{selected.produced_quantity ?? "No registrada"}</dd></div>
                </dl>
                {!canEdit ? <p className="muted">Acceso de consulta. La captura requiere permiso mes.edit.</p> : null}
                {dispatch?.status !== "RELEASED" ? <p className="muted">El despacho debe estar liberado para registrar ejecución.</p> : null}
                {canEdit && dispatch?.status === "RELEASED" && selected.status === "PENDING" ? (
                  <div className="mes-form">
                    <label>Recurso real (opcional)<select aria-label="Recurso real" value={resourceId} onChange={e => setResourceId(e.target.value)}><option value="">No informado (utilizar planificación)</option>{resourceOptions.map(resource => <option key={resource.id} value={resource.id}>{resource.code} · {resource.name}</option>)}</select></label>
                    <label>Motivo de desvío de recurso<input value={resourceReason} onChange={e => setResourceReason(e.target.value)} /></label>
                    <button className="primary-button" type="button" disabled={busy} onClick={() => void submit("start")}>Iniciar operación</button>
                    <small>El backend verifica WIP recibido y setup; una operación bloqueada no puede iniciarse.</small>
                  </div>
                ) : null}
                {canEdit && dispatch?.status === "RELEASED" && selected.status === "RUNNING" ? (
                  <div className="mes-form">
                    <label>Cantidad producida al finalizar<input inputMode="decimal" value={quantity} onChange={e => setQuantity(e.target.value.replace(",", "."))} placeholder="Cantidad real"/></label>
                    <button className="primary-button" type="button" disabled={busy} onClick={() => void submit("complete")}>Finalizar y registrar cantidad</button>
                    <label>Motivo de pausa<input value={reason} onChange={e => setReason(e.target.value)} placeholder="Código de causa"/></label>
                    <button type="button" disabled={busy} onClick={() => void submit("pause")}>Pausar operación</button>
                  </div>
                ) : null}
                {canEdit && dispatch?.status === "RELEASED" && selected.status === "PAUSED" ? (
                  <button className="primary-button" type="button" disabled={busy} onClick={() => void submit("resume")}>Reanudar operación</button>
                ) : null}
              </>
            ) : <p className="muted">Seleccioná una operación para consultar o registrar su avance.</p>}
          </div>
        </div>
      </section>
      <MESAdvancedPanel dispatchId={dispatchId} operations={operations} selectedId={selectedId} canEdit={canEdit && dispatch?.status === "RELEASED"} resources={resourceOptions} refresh={refresh} onChanged={reload} />
    </>
  );
}
