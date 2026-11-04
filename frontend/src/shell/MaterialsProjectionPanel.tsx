import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../api/client";
import "./MaterialsProjectionPanel.css";
import { exactDecimalText as fmt, nonzeroDecimal as nonzero, csvField as csv } from "./materialsProjectionFormatting";

type Plant = { id: string; code: string; name: string };
type Plan = { id: string; plan_number: string; status: string };
type Location = {
  location_id: string; warehouse_code: string; location_code: string;
  location_name: string; on_hand: string | null; held: string;
  unallocated: string | null; state: "KNOWN" | "UNKNOWN";
};
type MaterialRow = {
  article_id: string; article_code: string; article_description: string;
  uom_code: string; theoretical_plan_quantity: string;
  actual_net_measured_consumption: string; theoretical_minus_measured: string;
  physical_on_hand: string | null; reserved_all_plans: string;
  reserved_this_plan: string; unallocated_physical: string | null;
  provisional_gross_gap: string | null; stock_state: "KNOWN" | "UNKNOWN";
  location_breakdown: Location[]; distinct_taquillas: number;
  source_path_count: number; bom_revision_ids: string[]; warnings: string[];
};
type Projection = {
  plan_id: string; plan_number: string; plan_status: string;
  plant_id: string; plant_code: string; effective_at: string;
  generated_at: string; source_taquillas: number;
  excluded_cancelled_taquillas: string[];
  material_count: number; unknown_stock_materials: number;
  indicative_gap_materials: number; items: MaterialRow[]; warnings: string[];
};
type ProcurementRow = {
  article_id: string; verified_order_lines: number;
  verified_receipt_events: number; verified_claims: number;
  verified_escalations: number; latest_verified_event_at: string | null;
  original_promise_dates: string[]; revised_promise_dates: string[];
};
type Procurement = {
  data_scope: "VERIFIED_MANUAL_SAMPLES_ONLY";
  no_verified_records_means: "UNKNOWN_NOT_ZERO";
  items: ProcurementRow[];
};
type Filter = "all" | "gap" | "unknown";
const base = "/api/v1/materials/projection";
const dateToday = () => {
  const now = new Date();
  return [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0")].join("-");
};
const forBOM = (day: string) => `${day}T12:00:00Z`;
const msg = (e: unknown) => e instanceof Error ? e.message : "No fue posible consultar los materiales.";
const dateLabel = (s: string) => new Date(s).toLocaleDateString("es-AR");
export function MaterialsProjectionPanel({
  contextPlantId, canReadProcurement,
}: { contextPlantId?: string | null; canReadProcurement: boolean }) {
  const [plants, setPlants] = useState<Plant[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [plantId, setPlantId] = useState(contextPlantId ?? "");
  const [planId, setPlanId] = useState("");
  const [effectiveDate, setEffectiveDate] = useState(dateToday);
  const [refresh, setRefresh] = useState(0);
  const [data, setData] = useState<Projection | null>(null);
  const [procurement, setProcurement] = useState<Procurement | null>(null);
  const [procurementError, setProcurementError] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [opened, setOpened] = useState("");

  useEffect(() => {
    let current = true;
    Promise.all([
      apiFetch<Plant[]>(base + "/plants?limit=500"),
      apiFetch<Plan[]>(base + "/plans?limit=500"),
    ]).then(([sites, jobs]) => {
      if (!current) return;
      setPlants(sites); setPlans(jobs);
      setPlantId(old => sites.some(p => p.id === old) ? old : (sites[0]?.id ?? ""));
      setPlanId(old => jobs.some(p => p.id === old) ? old : (jobs[0]?.id ?? ""));
    }).catch(e => { if (current) setError(msg(e)); });
    return () => { current = false; };
  }, []);

  useEffect(() => {
    if (contextPlantId && plants.some(p => p.id === contextPlantId)) setPlantId(contextPlantId);
  }, [contextPlantId, plants]);

  useEffect(() => {
    if (!plantId || !planId || !effectiveDate) {
      setData(null); setProcurement(null);
      return;
    }
    let current = true;
    const parameters = new URLSearchParams({
      plant_id: plantId, effective_at: forBOM(effectiveDate),
    });
    const procurementParameters = new URLSearchParams({ effective_at: forBOM(effectiveDate) });
    setLoading(true); setError(""); setData(null); setProcurement(null); setProcurementError("");
    void apiFetch<Projection>(base + "/plans/" + encodeURIComponent(planId) + "?" + parameters.toString())
      .then(result => { if (current) setData(result); })
      .catch(e => { if (current) setError(msg(e)); })
      .finally(() => { if (current) setLoading(false); });
    if (canReadProcurement) {
      void apiFetch<Procurement>(base + "/plans/" + encodeURIComponent(planId) +
        "/procurement?" + procurementParameters.toString())
        .then(result => { if (current) setProcurement(result); })
        .catch(e => { if (current) setProcurementError(msg(e)); });
    }
    return () => { current = false; };
  }, [plantId, planId, effectiveDate, refresh, canReadProcurement]);

  const rows = useMemo(() => (data?.items ?? []).filter(row => {
    const matching = (row.article_code + " " + row.article_description).toLowerCase()
      .includes(search.trim().toLowerCase());
    if (!matching) return false;
    if (filter === "unknown") return row.stock_state === "UNKNOWN";
    if (filter === "gap") return nonzero(row.provisional_gross_gap);
    return true;
  }), [data, search, filter]);
  const evidenceByArticle = useMemo(() =>
    new Map(procurement?.items.map(item => [item.article_id, item]) ?? []), [procurement]);

  const exportCSV = () => {
    if (!data) return;
    const lines = [
      ["Artículo", "Descripción", "Ud", "BOM teórica", "Consumo real neto",
       "Stock físico", "Reservas totales", "Reservado plan", "No asignado",
       "Brecha bruta indicativa", "Estado stock"].map(csv).join(","),
      ...rows.map(r => [
        r.article_code, r.article_description, r.uom_code, r.theoretical_plan_quantity,
        r.actual_net_measured_consumption, r.physical_on_hand, r.reserved_all_plans,
        r.reserved_this_plan, r.unallocated_physical, r.provisional_gross_gap, r.stock_state,
      ].map(csv).join(",")),
    ];
    const blob = new Blob(["\uFEFF", lines.join("\r\n")], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = "MOP-Materiales-" + data.plan_number.replace(/[^a-zA-Z0-9_-]/g, "_") + ".csv";
    document.body.append(link); link.click(); link.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="g67">
      <header className="g67-hero">
        <p className="eyebrow">G6.7 · Inteligencia de materiales</p>
        <h2>Abastecimiento y disponibilidad física</h2>
        <p>Demanda BOM, inventario por ubicación, reservas y consumo MES. Los faltantes son indicativos; no implican stock liberado por Calidad ni órdenes de compra.</p>
      </header>
      <div className="g67-toolbar">
        <label>Planta
          <select value={plantId} onChange={e => setPlantId(e.target.value)} disabled={!plants.length}>
            {plants.map(p => <option key={p.id} value={p.id}>{p.code} · {p.name}</option>)}
          </select>
        </label>
        <label>Plan
          <select value={planId} onChange={e => setPlanId(e.target.value)} disabled={!plans.length}>
            {plans.map(p => <option key={p.id} value={p.id}>{p.plan_number} · {p.status}</option>)}
          </select>
        </label>
        <label>Vigencia de BOM
          <input type="date" value={effectiveDate} onChange={e => setEffectiveDate(e.target.value)} />
        </label>
        <button type="button" onClick={() => setRefresh(v => v + 1)} disabled={loading || !plantId || !planId}>
          Actualizar
        </button>
      </div>
      {loading && <p role="status">Consultando BOM y registros de planta…</p>}
      {error && <p role="alert" className="g67-warning">{error}</p>}
      {!plants.length && !error && <p>Sin plantas habilitadas para consultar.</p>}
      {!plans.length && !error && <p>Sin planes disponibles.</p>}

      {data && (
        <>
          <div className="g67-stats">
            <article><span>Materiales BOM</span><strong>{data.material_count}</strong><small>{data.source_taquillas} taquillas incluidas</small></article>
            <article><span>Stock desconocido</span><strong>{data.unknown_stock_materials}</strong><small>No equivale a cero</small></article>
            <article><span>Brecha indicativa</span><strong>{data.indicative_gap_materials}</strong><small>Artículos con diferencia, no ATP</small></article>
            <article><span>Taquillas canceladas</span><strong>{data.excluded_cancelled_taquillas.length}</strong><small>Excluidas de la demanda BOM</small></article>
          </div>
          <div className="g67-caption">
            <strong>{data.plan_number} · Planta {data.plant_code}</strong>
            <span>Consulta al {dateLabel(data.effective_at)} · {dateLabel(data.generated_at)}</span>
            <span>El consumo MES ya está descontado del stock físico. No se vuelve a restar.</span>
          </div>
          <div className="g67-toolbar g67-print-controls">
            <label>Buscar artículo
              <input value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Código o descripción" />
            </label>
            <label>Mostrar
              <select value={filter} onChange={e => setFilter(e.target.value as Filter)}>
                <option value="all">Todos</option>
                <option value="gap">Con brecha indicativa</option>
                <option value="unknown">Stock desconocido</option>
              </select>
            </label>
            <button type="button" onClick={exportCSV}>Exportar CSV</button>
            <button type="button" onClick={() => window.print()}>Imprimir informe</button>
          </div>
          <div className="g67-scroll">
            <table>
              <thead>
                <tr>
                  <th>Artículo / unidad</th>
                  <th>BOM teórica</th>
                  <th>Consumo MES</th>
                  <th>Físico</th>
                  <th>Reservado total</th>
                  <th>Reservado plan</th>
                  <th>No asignado</th>
                  <th>Brecha indicativa</th>
                  <th>Detalle</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(row => (
                  <tr key={row.article_id}>
                    <td><strong>{row.article_code}</strong><small>{row.article_description}</small><small>Unidad: {row.uom_code}</small></td>
                    <td>{fmt(row.theoretical_plan_quantity)}</td>
                    <td>{fmt(row.actual_net_measured_consumption)}</td>
                    <td>{fmt(row.physical_on_hand)}</td>
                    <td>{fmt(row.reserved_all_plans)}</td>
                    <td>{fmt(row.reserved_this_plan)}</td>
                    <td>{fmt(row.unallocated_physical)}</td>
                    <td><span className={row.stock_state === "UNKNOWN" ? "g67-status unknown" :
                      nonzero(row.provisional_gross_gap) ? "g67-status gap" : "g67-status ok"}>
                      {fmt(row.provisional_gross_gap)}
                    </span></td>
                    <td><button type="button" aria-expanded={opened === row.article_id}
                      onClick={() => setOpened(opened === row.article_id ? "" : row.article_id)}>
                      {opened === row.article_id ? "Ocultar" : "Ver"}
                    </button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!rows.length && <p>No hay artículos que coincidan con los filtros.</p>}
          </div>
          {rows.filter(row => row.article_id === opened).map(row => (
            <section className="g67-detail" key={row.article_id}>
              <h3>{row.article_code} · Detalle por ubicación</h3>
              <p>{row.source_path_count} rutas de componentes BOM y {row.distinct_taquillas} taquillas de origen.</p>
              <table>
                <thead><tr><th>Depósito</th><th>Ubicación</th><th>Físico</th><th>Reserva</th><th>Sin asignar</th><th>Estado</th></tr></thead>
                <tbody>{row.location_breakdown.map(loc => (
                  <tr key={loc.location_id}>
                    <td>{loc.warehouse_code}</td><td>{loc.location_code} · {loc.location_name}</td>
                    <td>{fmt(loc.on_hand)}</td><td>{fmt(loc.held)}</td>
                    <td>{fmt(loc.unallocated)}</td><td>{loc.state === "KNOWN" ? "Registrado" : "Desconocido"}</td>
                  </tr>
                ))}</tbody>
              </table>
              <p>Consumo real neto: {fmt(row.actual_net_measured_consumption)} {row.uom_code}. Diferencia aritmética BOM–consumo: {fmt(row.theoretical_minus_measured)}; no es un indicador de eficiencia sin conciliar el avance de la producción.</p>
              <p>Revisiones BOM: {row.bom_revision_ids.join(", ")}</p>
              {canReadProcurement && (
                <div className="g67-evidence">
                  <h4>Prolowin · evidencia verificada (muestra parcial)</h4>
                  {evidenceByArticle.has(row.article_id) && (
                    <>
                      {(() => {
                        const e = evidenceByArticle.get(row.article_id)!;
                        const hasAny = e.verified_order_lines + e.verified_receipt_events +
                          e.verified_claims + e.verified_escalations > 0;
                        return hasAny ? (
                          <p>OC documentadas: {e.verified_order_lines} · Recepciones: {e.verified_receipt_events} · Reclamos: {e.verified_claims} · Alertas de continuidad: {e.verified_escalations}. Última evidencia: {e.latest_verified_event_at ? dateLabel(e.latest_verified_event_at) : "Desconocida"}.</p>
                        ) : <p>Sin evidencia verificada capturada. No significa que no existan pedidos o entregas en Prolowin.</p>;
                      })()}
                    </>
                  )}
                  {procurementError && <p className="g67-warning">{procurementError}</p>}
                  {!procurement && !procurementError && <p>Consultando evidencia de Compras…</p>}
                </div>
              )}
            </section>
          ))}
          <footer className="g67-footnote">
            <strong>Alcance del informe.</strong> Las cantidades corresponden a unidades distintas y no deben totalizarse entre artículos. Si alguna ubicación de la planta carece de apertura, el stock del artículo es desconocido. Las brechas comparan demanda bruta del plan con reservas de sus taquillas y stock físico no asignado; no ajustan automáticamente producción ya ejecutada, fechas ni calidad. La evidencia Prolowin es manual, parcial y no se incorpora al inventario.
          </footer>
        </>
      )}
    </section>
  );
}
