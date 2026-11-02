import { useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../api/client";
import type {
  OperationalPlanProjection,
  ProductionPlan,
  TaquillaAssimilationBatch
} from "../api/types";

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    DRAFT: "Borrador",
    OPEN: "Abierto",
    READY: "Listo",
    COMPLETED: "Completado",
    CANCELLED: "Cancelado",
    APPLIED: "Aplicado",
    REVIEW_REQUIRED: "Revisión requerida",
    VALIDATED: "Validado",
    RECEIVED: "Recibido",
    REJECTED: "Rechazado",
    ON_TIME: "En término",
    DELAYED: "Con demora"
  };
  return labels[status] ?? status;
}

function statusClass(status: string) {
  if (["COMPLETED", "APPLIED", "VALIDATED", "ON_TIME", "READY"].includes(status)) {
    return "status-pill success";
  }
  if (["REVIEW_REQUIRED", "DELAYED", "DRAFT", "OPEN", "RECEIVED"].includes(status)) {
    return "status-pill warning";
  }
  if (["CANCELLED", "REJECTED"].includes(status)) {
    return "status-pill danger";
  }
  return "status-pill neutral";
}

export function DemandPanel({ canEdit }: { canEdit: boolean }) {
  const [plans, setPlans] = useState<ProductionPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [projection, setProjection] = useState<OperationalPlanProjection | null>(null);
  const [batches, setBatches] = useState<TaquillaAssimilationBatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [projectionLoading, setProjectionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importPayload, setImportPayload] = useState("");
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([api.productionPlans(), api.assimilationBatches()])
      .then(([planData, batchData]) => {
        if (!active) return;
        setPlans(planData);
        setBatches(batchData);
        setSelectedPlanId((current) => current || planData[0]?.id || "");
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(
          reason instanceof ApiError
            ? reason.message
            : "No fue posible cargar la demanda operativa."
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedPlanId) {
      setProjection(null);
      return;
    }
    let active = true;
    setProjectionLoading(true);
    api.operationalProjection(selectedPlanId)
      .then((data) => {
        if (!active) return;
        setProjection(data);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(
          reason instanceof ApiError
            ? reason.message
            : "No fue posible cargar la proyección operativa."
        );
      })
      .finally(() => {
        if (active) setProjectionLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedPlanId]);

  const currentPlan = useMemo(
    () => plans.find((plan) => plan.id === selectedPlanId) ?? null,
    [plans, selectedPlanId]
  );

  const reviewBatches = batches.filter(
    (batch) => batch.status === "REVIEW_REQUIRED"
  );

  async function refreshDemand() {
    const [planData, batchData] = await Promise.all([
      api.productionPlans(),
      api.assimilationBatches()
    ]);
    setPlans(planData);
    setBatches(batchData);
    if (selectedPlanId) {
      setProjection(await api.operationalProjection(selectedPlanId));
    }
  }

  async function submitImport() {
    setImportMessage(null);
    setError(null);
    let payload: unknown;
    try {
      payload = JSON.parse(importPayload);
    } catch {
      setError("El contrato de importación debe ser JSON válido.");
      return;
    }
    setImporting(true);
    try {
      const result = await api.importTaquilla(payload);
      setImportMessage(
        result.batch.status === "APPLIED"
          ? `Taquilla aplicada: ${result.batch.taquilla_code}`
          : `Importación en ${statusLabel(result.batch.status)} con ${result.issues.length} observaciones.`
      );
      await refreshDemand();
    } catch (reason: unknown) {
      setError(
        reason instanceof ApiError
          ? reason.message
          : "No fue posible importar la Taquilla."
      );
    } finally {
      setImporting(false);
    }
  }

  return (
    <>
      <section className="hero-panel demand-hero">
        <div>
          <p className="eyebrow">G3 · Demanda operativa</p>
          <h2>Plan → Taquillas → Productos → Piso → Routing</h2>
          <p>
            Vista consolidada de intención productiva. No contiene secuenciación,
            capacidad finita, Gantt ni tiempos reales de ejecución.
          </p>
        </div>
        <div className="demand-plan-selector">
          <label htmlFor="plan-selector">Plan activo</label>
          <select
            id="plan-selector"
            value={selectedPlanId}
            onChange={(event) => setSelectedPlanId(event.target.value)}
            disabled={loading || plans.length === 0}
          >
            {plans.length === 0 ? <option value="">Sin planes</option> : null}
            {plans.map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.plan_number} · {statusLabel(plan.status)}
              </option>
            ))}
          </select>
          {currentPlan?.historical_completion_classification ? (
            <span className={statusClass(currentPlan.historical_completion_classification)}>
              {statusLabel(currentPlan.historical_completion_classification)}
            </span>
          ) : null}
        </div>
      </section>

      {error ? <p className="inline-error">{error}</p> : null}
      {loading || projectionLoading ? (
        <p className="muted">Cargando proyección operativa…</p>
      ) : null}

      {projection ? (
        <>
          <section className="metric-grid">
            <article className="metric-card">
              <span>Taquillas</span>
              <strong>{projection.taquilla_count}</strong>
              <small>Ordenadas dentro del Plan</small>
            </article>
            <article className="metric-card">
              <span>Líneas de producto</span>
              <strong>{projection.product_line_count}</strong>
              <small>Demanda exacta G2</small>
            </article>
            <article className="metric-card">
              <span>Routing pendiente</span>
              <strong>{projection.routing_missing_count}</strong>
              <small>Sin RoutingRevision vinculada</small>
            </article>
            <article className="metric-card">
              <span>Taquillas bloqueadas</span>
              <strong>{projection.blocked_taquilla_count}</strong>
              <small>Borrador sin composición o routing completo</small>
            </article>
          </section>

          <section className="content-section">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Plan {projection.plan_number}</p>
                <h2>Secuencia de Taquillas</h2>
              </div>
              <span className={statusClass(projection.status)}>
                {statusLabel(projection.status)}
              </span>
            </div>

            {projection.taquillas.length === 0 ? (
              <p className="muted">El Plan todavía no contiene Taquillas.</p>
            ) : (
              <div className="taquilla-stack">
                {projection.taquillas.map((taquilla) => (
                  <article className="taquilla-card" key={taquilla.id}>
                    <header>
                      <div>
                        <span className="sequence-badge">
                          {String(taquilla.sequence_no).padStart(2, "0")}
                        </span>
                        <div>
                          <strong>{taquilla.taquilla_code}</strong>
                          <small>
                            {taquilla.vehicle_topology === "DOUBLE_DECK"
                              ? "Doble piso"
                              : "Piso simple"}
                          </small>
                        </div>
                      </div>
                      <div className="taquilla-statuses">
                        <span className={statusClass(taquilla.status)}>
                          {statusLabel(taquilla.status)}
                        </span>
                        {taquilla.historical_completion_classification ? (
                          <span className={statusClass(taquilla.historical_completion_classification)}>
                            {statusLabel(taquilla.historical_completion_classification)}
                          </span>
                        ) : null}
                      </div>
                    </header>

                    <div className="taquilla-summary">
                      <span>{taquilla.product_count} productos</span>
                      <span>{taquilla.total_requested_quantity} unidades solicitadas</span>
                      <span>{taquilla.routing_bound_count} rutas vinculadas</span>
                      {taquilla.routing_missing_count ? (
                        <strong>{taquilla.routing_missing_count} routing pendiente</strong>
                      ) : (
                        <span>Routing completo</span>
                      )}
                    </div>

                    {taquilla.cancellation_reason ? (
                      <p className="inline-error">
                        Cancelación: {taquilla.cancellation_reason}
                      </p>
                    ) : null}

                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>#</th>
                            <th>Producto</th>
                            <th>Cantidad</th>
                            <th>Piso</th>
                            <th>Routing</th>
                            <th>Fuente</th>
                          </tr>
                        </thead>
                        <tbody>
                          {taquilla.products.map((product) => (
                            <tr key={product.id}>
                              <td>{product.sequence_no}</td>
                              <td>
                                <strong>{product.article_code}</strong>
                                <br />
                                <small>{product.article_description}</small>
                              </td>
                              <td>{product.requested_quantity}</td>
                              <td>
                                <span className="deck-chip">
                                  {product.deck_position}
                                </span>
                              </td>
                              <td>
                                {product.routing.routing_revision_id ? (
                                  <>
                                    <strong>
                                      Rev. {product.routing.revision_no ?? "—"}
                                    </strong>
                                    <br />
                                    <small>
                                      {product.routing.binding_mode ?? "—"} ·{" "}
                                      {product.routing.status ?? "—"}
                                    </small>
                                  </>
                                ) : (
                                  <span className="routing-missing">
                                    Pendiente
                                  </span>
                                )}
                              </td>
                              <td>
                                <small>
                                  {product.source_document_key ?? "Manual"}
                                  {product.source_line_key
                                    ? " · " + product.source_line_key
                                    : ""}
                                </small>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      ) : null}


      {canEdit ? (
        <section className="content-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Carga controlada</p>
              <h2>Importar contrato normalizado de Taquilla</h2>
            </div>
            <span className="status-pill neutral">demand.edit</span>
          </div>
          <p className="muted">
            Pegá únicamente el contrato JSON normalizado de G3.6. Esta pantalla no
            interpreta PDFs, nombres de archivo ni orden de páginas.
          </p>
          <textarea
            className="import-textarea"
            value={importPayload}
            onChange={(event) => setImportPayload(event.target.value)}
            placeholder='{"schema_version":"1.0.0", ...}'
            rows={10}
          />
          <div className="form-actions">
            <button
              type="button"
              className="primary-button"
              disabled={importing || !importPayload.trim()}
              onClick={() => void submitImport()}
            >
              {importing ? "Validando…" : "Validar e importar"}
            </button>
            {importMessage ? <span className="muted">{importMessage}</span> : null}
          </div>
        </section>
      ) : null}

      <section className="content-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Asimilación</p>
            <h2>Importaciones que requieren intervención</h2>
          </div>
          <span className={reviewBatches.length ? "status-pill warning" : "status-pill success"}>
            {reviewBatches.length} pendientes
          </span>
        </div>
        {reviewBatches.length === 0 ? (
          <p className="muted">
            No hay lotes de Taquilla en REVIEW_REQUIRED.
          </p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Taquilla</th>
                  <th>Topología</th>
                  <th>Líneas aceptadas</th>
                  <th>Rechazadas</th>
                  <th>Origen</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {reviewBatches.map((batch) => (
                  <tr key={batch.id}>
                    <td><strong>{batch.taquilla_code}</strong></td>
                    <td>{batch.vehicle_topology}</td>
                    <td>{batch.accepted_lines}</td>
                    <td>{batch.rejected_lines}</td>
                    <td>{batch.source_system}</td>
                    <td>
                      <span className="status-pill warning">
                        Revisión requerida
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
