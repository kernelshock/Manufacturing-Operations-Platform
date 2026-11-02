import { useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../api/client";
import type {
  GanttProjection,
  WhatIfComparison,
  WhatIfScenario
} from "../api/types";

function statusClass(status: WhatIfScenario["status"]) {
  if (status === "APPLIED") return "status-pill success";
  if (status === "EVALUATED") return "status-pill neutral";
  if (status === "DISCARDED") return "status-pill danger";
  return "status-pill warning";
}

function localInputToIso(value: string) {
  return new Date(value).toISOString();
}

export function WhatIfPanel({
  projection,
  canEdit,
  onApplied
}: {
  projection: GanttProjection;
  canEdit: boolean;
  onApplied: () => void;
}) {
  const [items, setItems] = useState<WhatIfScenario[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [comparison, setComparison] = useState<WhatIfComparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [baselinePublicationId, setBaselinePublicationId] = useState(
    projection.publications[0]?.publication_id ?? ""
  );

  const [exceptionType, setExceptionType] = useState<
    "RESOURCE_BLACKOUT" | "RESOURCE_CAPACITY_FACTOR"
  >("RESOURCE_BLACKOUT");
  const [resourceId, setResourceId] = useState("");
  const [startAt, setStartAt] = useState("");
  const [endAt, setEndAt] = useState("");
  const [factor, setFactor] = useState("0.5");
  const [reason, setReason] = useState("");

  const resources = useMemo(() => {
    const seen = new Map<string, string>();
    for (const operation of projection.operations) {
      seen.set(
        operation.resource_id,
        `${operation.resource_code} · ${operation.resource_name}`
      );
    }
    return Array.from(seen.entries()).map(([id, label]) => ({ id, label }));
  }, [projection]);

  const selected = items.find((item) => item.id === selectedId) ?? null;

  async function refresh() {
    const data = await api.whatIfScenarios();
    setItems(data);
    setSelectedId((current) => current || data[0]?.id || "");
  }

  useEffect(() => {
    void refresh().catch((reason: unknown) => {
      setError(reason instanceof ApiError ? reason.message : "No fue posible cargar los escenarios what-if.");
    });
  }, []);

  useEffect(() => {
    if (!baselinePublicationId && projection.publications[0]) {
      setBaselinePublicationId(projection.publications[0].publication_id);
    }
    if (!resourceId && resources[0]) {
      setResourceId(resources[0].id);
    }
  }, [baselinePublicationId, projection.publications, resourceId, resources]);

  useEffect(() => {
    if (!selected || selected.status !== "EVALUATED") {
      setComparison(null);
      return;
    }
    let active = true;
    api.compareWhatIf(selected.id)
      .then((data) => {
        if (active) setComparison(data);
      })
      .catch(() => {
        if (active) setComparison(null);
      });
    return () => { active = false; };
  }, [selected?.id, selected?.status]);

  async function createScenario() {
    if (!code.trim() || !name.trim() || !baselinePublicationId) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.createWhatIf({
        scenario_code: code.trim(),
        name: name.trim(),
        baseline_publication_id: baselinePublicationId
      });
      await refresh();
      setSelectedId(created.id);
      setCode("");
      setName("");
    } catch (reasonValue: unknown) {
      setError(reasonValue instanceof ApiError ? reasonValue.message : "No fue posible crear el what-if.");
    } finally {
      setBusy(false);
    }
  }

  async function addException() {
    if (!selected || !resourceId || !startAt || !endAt || !reason.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.addWhatIfException(selected.id, {
        exception_type: exceptionType,
        resource_id: resourceId,
        start_at: localInputToIso(startAt),
        end_at: localInputToIso(endAt),
        capacity_factor:
          exceptionType === "RESOURCE_CAPACITY_FACTOR" ? factor : undefined,
        reason: reason.trim()
      });
      setReason("");
    } catch (reasonValue: unknown) {
      setError(reasonValue instanceof ApiError ? reasonValue.message : "No fue posible agregar la excepción.");
    } finally {
      setBusy(false);
    }
  }

  async function evaluate() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.evaluateWhatIf(selected.id);
      setComparison(result.comparison);
      await refresh();
      setSelectedId(result.scenario.id);
    } catch (reasonValue: unknown) {
      setError(reasonValue instanceof ApiError ? reasonValue.message : "La hipótesis no pudo resolverse con capacidad finita.");
    } finally {
      setBusy(false);
    }
  }

  async function applyScenario() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await api.applyWhatIf(selected.id);
      await refresh();
      onApplied();
    } catch (reasonValue: unknown) {
      setError(reasonValue instanceof ApiError ? reasonValue.message : "No fue posible aplicar el what-if.");
    } finally {
      setBusy(false);
    }
  }

  async function discardScenario() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await api.discardWhatIf(selected.id);
      await refresh();
    } catch (reasonValue: unknown) {
      setError(reasonValue instanceof ApiError ? reasonValue.message : "No fue posible descartar el what-if.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="content-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">G4.7 · Hipótesis aisladas</p>
          <h2>What-if & excepciones de capacidad</h2>
        </div>
        <span className="status-pill neutral">Baseline CURRENT intacto hasta Aplicar</span>
      </div>

      {error ? <p className="inline-error">{error}</p> : null}

      {canEdit ? (
        <div className="whatif-create-grid">
          <input value={code} onChange={(event) => setCode(event.target.value)} placeholder="Código (ej. WI-R4-OFF)" />
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Nombre de hipótesis" />
          <select value={baselinePublicationId} onChange={(event) => setBaselinePublicationId(event.target.value)}>
            {projection.publications.map((publication) => (
              <option key={publication.publication_id} value={publication.publication_id}>
                {publication.plan_number} · publicación v{publication.version_no}
              </option>
            ))}
          </select>
          <button className="primary-button" type="button" disabled={busy || !code.trim() || !name.trim()} onClick={() => void createScenario()}>
            Crear what-if
          </button>
        </div>
      ) : null}

      <div className="whatif-workspace">
        <div>
          <label className="field-label" htmlFor="whatif-selector">Escenario</label>
          <select id="whatif-selector" value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
            <option value="">Sin escenario</option>
            {items.map((item) => (
              <option key={item.id} value={item.id}>{item.scenario_code} · {item.status}</option>
            ))}
          </select>
          {selected ? (
            <div className="whatif-summary">
              <strong>{selected.name}</strong>
              <span className={statusClass(selected.status)}>{selected.status}</span>
              <small>Baseline: {selected.baseline_publication_id.slice(0, 8)}</small>
            </div>
          ) : null}
        </div>

        {selected?.status === "DRAFT" && canEdit ? (
          <div className="whatif-exception-form">
            <select value={exceptionType} onChange={(event) => setExceptionType(event.target.value as typeof exceptionType)}>
              <option value="RESOURCE_BLACKOUT">Recurso no disponible</option>
              <option value="RESOURCE_CAPACITY_FACTOR">Factor de capacidad</option>
            </select>
            <select value={resourceId} onChange={(event) => setResourceId(event.target.value)}>
              {resources.map((resource) => <option key={resource.id} value={resource.id}>{resource.label}</option>)}
            </select>
            <input type="datetime-local" value={startAt} onChange={(event) => setStartAt(event.target.value)} />
            <input type="datetime-local" value={endAt} onChange={(event) => setEndAt(event.target.value)} />
            {exceptionType === "RESOURCE_CAPACITY_FACTOR" ? (
              <input type="number" min="0.01" step="0.05" value={factor} onChange={(event) => setFactor(event.target.value)} placeholder="Factor" />
            ) : null}
            <input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Motivo de la hipótesis" />
            <button type="button" disabled={busy || !startAt || !endAt || !reason.trim()} onClick={() => void addException()}>
              Agregar excepción
            </button>
            <button className="primary-button" type="button" disabled={busy} onClick={() => void evaluate()}>
              Evaluar
            </button>
          </div>
        ) : null}

        {comparison ? (
          <div className="whatif-comparison">
            <article><span>Excepciones</span><strong>{comparison.exception_count}</strong></article>
            <article><span>Cambios temporales</span><strong>{comparison.timing_changed_count}</strong></article>
            <article><span>Cambios de recurso</span><strong>{comparison.resource_changed_count}</strong></article>
            <article><span>Δ makespan</span><strong>{Math.round(Number(comparison.makespan_delta_seconds) / 60)} min</strong></article>
          </div>
        ) : null}

        {selected && canEdit && ["DRAFT", "EVALUATED"].includes(selected.status) ? (
          <div className="form-actions">
            {selected.status === "EVALUATED" ? (
              <button className="primary-button" type="button" disabled={busy} onClick={() => void applyScenario()}>
                Aplicar y publicar
              </button>
            ) : null}
            <button type="button" disabled={busy} onClick={() => void discardScenario()}>
              Descartar
            </button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
