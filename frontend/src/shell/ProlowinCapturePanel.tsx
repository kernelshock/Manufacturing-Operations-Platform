import { useCallback, useEffect, useState, type FormEvent } from "react";
import { apiFetch } from "../api/client";

const base = "/api/v1/prolowin/procurement";
type Capture = { id: string; source_type: string; source_reference: string; source_sha256: string | null };
type Evidence = {
  id: string; kind: string; po_number: string; line_number: number; supplier_code: string;
  article_code: string; quantity: string | null; source_reference: string; capture_id: string;
  review_status: string; entered_by: string;
};
type Summary = {
  ordered_quantity: string; delivered_quantity: string; accepted_quantity: string | null;
  outstanding_delivered_quantity: string; claim_count: number;
  original_promise_date: string; latest_revised_promise_date: string | null;
  production_risk_escalations: number; partial_receipt_count: number;
  physical_inventory_effect: "NONE";
};
type Kind = "ORDER" | "RECEIPT" | "RESCHEDULE" | "CLAIM" | "ESCALATION";
type FormData = {
  kind: Kind; po_number: string; line_number: string; supplier_code: string;
  article_code: string; uom_code: string; quantity: string; accepted_quantity: string;
  event_date: string; original_promise_date: string; revised_promise_date: string;
  reason: string; source_reference: string; continuity_safe: boolean;
};
const init: FormData = {
  kind: "ORDER", po_number: "", line_number: "1", supplier_code: "",
  article_code: "", uom_code: "", quantity: "", accepted_quantity: "",
  event_date: "", original_promise_date: "", revised_promise_date: "",
  reason: "", source_reference: "", continuity_safe: false,
};
const asIso = (date: string) => date ? new Date(date).toISOString() : null;
const eText = (error: unknown) => error instanceof Error ? error.message : "Error de operación";
const fields: { key: keyof FormData; title: string; hint?: string }[] = [
  { key: "po_number", title: "Orden de compra" },
  { key: "line_number", title: "Renglón" },
  { key: "supplier_code", title: "Código proveedor (Prolowin / G2)" },
  { key: "article_code", title: "Código artículo" },
  { key: "uom_code", title: "Unidad canónica" },
  { key: "source_reference", title: "Referencia de pantalla, remito o reclamo" },
];

export function ProlowinCapturePanel({ canCapture, canVerify }: {
  canCapture: boolean; canVerify: boolean;
}) {
  const [captureRef, setCaptureRef] = useState("");
  const [capture, setCapture] = useState<Capture | null>(null);
  const [captureKind, setCaptureKind] = useState<"MANUAL" | "WEEKLY_SNAPSHOT">("MANUAL");
  const [reviewSource, setReviewSource] = useState<Capture | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState<FormData>(init);
  const [items, setItems] = useState<Evidence[]>([]);
  const [selectedReview, setSelectedReview] = useState("");
  const [reviewNote, setReviewNote] = useState("");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [summaryPo, setSummaryPo] = useState("");
  const [summaryLine, setSummaryLine] = useState("1");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(() => {
    void apiFetch<Evidence[]>(base + "/events").then(setItems).catch(e => setError(eText(e)));
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    if (!selectedReview) { setReviewSource(null); return; }
    const record = items.find(item => item.id === selectedReview);
    if (!record) { setReviewSource(null); return; }
    let active = true;
    void apiFetch<Capture>(base + "/captures/" + encodeURIComponent(record.capture_id))
      .then(source => { if (active) setReviewSource(source); })
      .catch(e => { if (active) setError(eText(e)); });
    return () => { active = false; };
  }, [selectedReview, items]);

  const submit = async (action: () => Promise<void>) => {
    setBusy(true); setError(""); setFeedback("");
    try { await action(); refresh(); }
    catch (e) { setError(eText(e)); }
    finally { setBusy(false); }
  };

  const createCapture = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void submit(async () => {
      if (!captureRef.trim()) throw new Error("Indicá referencia de la fuente.");
      const item = file
        ? await apiFetch<Capture>(base + "/captures/screenshots", {
            method: "POST", headers: { "content-type": file.type, "x-evidence-label": captureRef },
            body: file,
          })
        : await apiFetch<Capture>(base + "/captures/manual", {
            method: "POST", body: JSON.stringify({
              source_type: captureKind, source_reference: captureRef,
            }),
          });
      setCapture(item);
      setFeedback("Evidencia registrada. Transcribí los datos tal como aparecen en Prolowin.");
    });
  };

  const transcribe = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void submit(async () => {
      if (!capture) throw new Error("Primero registrá la pantalla o la fuente manual.");
      if (!form.event_date) throw new Error("La fecha del evento es obligatoria.");
      const eventKey = [form.po_number,form.line_number,form.kind,form.source_reference].join(":");
      const payload = {
        capture_id: capture.id, source_event_key: eventKey,
        kind: form.kind, po_number: form.po_number, line_number: Number(form.line_number),
        supplier_code: form.supplier_code, article_code: form.article_code,
        uom_code: form.uom_code, source_reference: form.source_reference,
        event_date: asIso(form.event_date),
        quantity: form.quantity || null, accepted_quantity: form.accepted_quantity || null,
        original_promise_date: asIso(form.original_promise_date),
        revised_promise_date: asIso(form.revised_promise_date),
        reason: form.reason || null,
        continuity_safe: form.kind === "RESCHEDULE" ? form.continuity_safe : null,
      };
      await apiFetch<Evidence>(base + "/events", {
        method: "POST", body: JSON.stringify(payload),
      });
      setFeedback("Transcripción pendiente de revisión independiente; no afecta al inventario.");
      setForm(previous => ({ ...previous, source_reference: "", quantity: "", accepted_quantity: "", reason: "" }));
    });
  };

  const review = (decision: "VERIFIED" | "REJECTED") => {
    void submit(async () => {
      if (!selectedReview) throw new Error("Seleccioná un registro pendiente.");
      if (reviewNote.trim().length < 4) throw new Error("Especificá motivo y verificación.");
      await apiFetch(base + "/events/" + encodeURIComponent(selectedReview) + "/review", {
        method: "POST", body: JSON.stringify({ decision, note: reviewNote }),
      });
      setFeedback(decision === "VERIFIED" ? "Registro verificado por control independiente." : "Registro rechazado sin afectar Compras ni stock.");
      setSelectedReview(""); setReviewNote("");
    });
  };

  const loadSummary = () => {
    void submit(async () => {
      const params = new URLSearchParams({ as_of: new Date().toISOString() });
      const result = await apiFetch<Summary>(
        base + "/orders/" + encodeURIComponent(summaryPo) +
        "/lines/" + encodeURIComponent(summaryLine) + "?" + params.toString()
      );
      setSummary(result);
    });
  };

  const update = (key: keyof FormData, value: string | boolean) => {
    setForm(current => ({ ...current, [key]: value }));
  };

  return (
    <section className="content-section" aria-label="Evidencia de Compras Prolowin">
      <div className="section-heading">
        <div>
          <p className="eyebrow">G6.6 · Prolowin legado</p>
          <h2>Captura y conciliación asistida</h2>
          <p>Sin conexión API: pantalla original o transcripción manual, con validación por otra persona. Sin movimientos de stock ni órdenes de compra automáticas.</p>
        </div>
      </div>
      {error && <p className="inline-error" role="alert">{error}</p>}
      {feedback && <p role="status">{feedback}</p>}

      {canCapture && (
        <>
          <form onSubmit={createCapture} className="content-section">
            <h3>1. Registrar fuente</h3>
            <label>Referencia de pantalla, pedido o registro
              <input required maxLength={150} value={captureRef}
                onChange={e => setCaptureRef(e.target.value)}
                placeholder="PO 26-145 · Renglón 3 · Captura Prolowin"/>
            </label>
            <label>Fuente cuando no hay imagen
              <select value={captureKind} onChange={e => setCaptureKind(e.target.value as "MANUAL" | "WEEKLY_SNAPSHOT")}>
                <option value="MANUAL">Transcripción desde pantalla de Prolowin</option>
                <option value="WEEKLY_SNAPSHOT">Registro semanal Excel (solo apoyo, no verificable solo)</option>
              </select>
            </label>
            <label>Captura PNG/JPEG (opcional, hasta 4 MiB)
              <input type="file" accept="image/png,image/jpeg"
                onChange={e => setFile(e.target.files?.[0] ?? null)} />
            </label>
            <button type="submit" disabled={busy}>Registrar fuente</button>
            {capture && <p>Fuente activa: {capture.source_type} · {capture.source_reference} · ID {capture.id} {capture.source_type === "SCREENSHOT" && <a href={base + "/captures/" + encodeURIComponent(capture.id) + "/image"}>Ver captura adjunta</a>}</p>}
          </form>

          <form onSubmit={transcribe} className="content-section">
            <h3>2. Transcribir movimiento de Compras</h3>
            <label>Clase de evidencia
              <select value={form.kind} onChange={e => update("kind", e.target.value)}>
                <option value="ORDER">Orden original</option>
                <option value="RECEIPT">Recepción / entrega parcial</option>
                <option value="RESCHEDULE">Reprogramación aceptada sin riesgo productivo</option>
                <option value="CLAIM">Reclamo a proveedor</option>
                <option value="ESCALATION">Alerta / evaluación de proveedor alternativo</option>
              </select>
            </label>
            <div className="metric-grid">
              {fields.map(({ key, title }) => (
                <label key={key}>{title}
                  <input required value={String(form[key])}
                    onChange={e => update(key, e.target.value)} />
                </label>
              ))}
              <label>Fecha del evento
                <input required type="datetime-local" value={form.event_date}
                  onChange={e => update("event_date", e.target.value)} />
              </label>
              {(form.kind === "ORDER" || form.kind === "RECEIPT") && (
                <label>{form.kind === "ORDER" ? "Cantidad pedida" : "Cantidad entregada"}
                  <input required placeholder="0.00000000" inputMode="decimal" value={form.quantity}
                    onChange={e => update("quantity", e.target.value)} />
                </label>
              )}
              {form.kind === "RECEIPT" && (
                <label>Cantidad aceptada por Calidad (si se conoce)
                  <input placeholder="Desconocida" value={form.accepted_quantity}
                    onChange={e => update("accepted_quantity", e.target.value)} />
                </label>
              )}
              {form.kind === "ORDER" && (
                <label>Fecha prometida originalmente
                  <input required type="datetime-local" value={form.original_promise_date}
                    onChange={e => update("original_promise_date", e.target.value)} />
                </label>
              )}
              {form.kind === "RESCHEDULE" && (
                <label>Nueva fecha prometida
                  <input required type="datetime-local" value={form.revised_promise_date}
                    onChange={e => update("revised_promise_date", e.target.value)} />
                </label>
              )}
            </div>
            {(form.kind === "RESCHEDULE" || form.kind === "CLAIM" || form.kind === "ESCALATION") && (
              <label>Motivo / respaldo
                <textarea required value={form.reason} onChange={e => update("reason", e.target.value)} />
              </label>
            )}
            {form.kind === "RESCHEDULE" && (
              <label><input type="checkbox" checked={form.continuity_safe}
                onChange={e => update("continuity_safe", e.target.checked)} />
                Confirmo que PCP evaluó la continuidad y no existe riesgo para la producción
              </label>
            )}
            <button type="submit" disabled={busy || !capture}>Guardar transcripción pendiente</button>
          </form>
        </>
      )}

      <section className="content-section">
        <h3>3. Revisión y seguimiento</h3>
        <p>Solo registros verificados alimentan el resumen. El revisor debe ser distinto del cargador.</p>
        <button type="button" onClick={refresh}>Actualizar evidencia</button>
        <table>
          <thead><tr><th>OC / línea</th><th>Tipo</th><th>Referencia</th><th>Estado</th><th>Fuente</th></tr></thead>
          <tbody>
            {items.map(item => (
              <tr key={item.id}>
                <td>{item.po_number} / {item.line_number}</td>
                <td>{item.kind}</td><td>{item.source_reference}</td><td>{item.review_status}</td>
                <td>{item.capture_id.slice(0, 8)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {canVerify && (
          <div>
            <label>Registro pendiente de verificar
              <select value={selectedReview} onChange={e => setSelectedReview(e.target.value)}>
                <option value="">Seleccionar</option>
                {items.filter(item => item.review_status === "PENDING").map(item => (
                  <option key={item.id} value={item.id}>{item.po_number} / {item.kind} / {item.source_reference}</option>
                ))}
              </select>
            </label>
            {reviewSource && <p>Origen: {reviewSource.source_type} · {reviewSource.source_reference} {reviewSource.source_type === "SCREENSHOT" ? <a href={base + "/captures/" + encodeURIComponent(reviewSource.id) + "/image"} target="_blank" rel="noreferrer">Examinar imagen de origen</a> : <span>(transcripción sin imagen)</span>}</p>}
            <label>Nota de revisión
              <textarea value={reviewNote} onChange={e => setReviewNote(e.target.value)} />
            </label>
            <button type="button" disabled={busy || !selectedReview} onClick={() => review("VERIFIED")}>Verificar contra Prolowin</button>
            <button type="button" disabled={busy || !selectedReview} onClick={() => review("REJECTED")}>Rechazar transcripción</button>
          </div>
        )}
      </section>
      <section className="content-section">
        <h3>4. Historial de pedido verificado</h3>
        <label>Orden de compra
          <input value={summaryPo} onChange={e => setSummaryPo(e.target.value)} />
        </label>
        <label>Renglón
          <input value={summaryLine} onChange={e => setSummaryLine(e.target.value)} />
        </label>
        <button type="button" onClick={loadSummary} disabled={!summaryPo.trim() || busy}>Consultar</button>
        {summary && (
          <div className="metric-grid">
            <p>Pedido: <strong>{summary.ordered_quantity}</strong></p>
            <p>Entregado: <strong>{summary.delivered_quantity}</strong></p>
            <p>Aceptado: <strong>{summary.accepted_quantity ?? "Sin evidencia"}</strong></p>
            <p>Pendiente de entrega: <strong>{summary.outstanding_delivered_quantity}</strong></p>
            <p>Recepciones: <strong>{summary.partial_receipt_count}</strong></p>
            <p>Reclamos: <strong>{summary.claim_count}</strong></p>
            <p>Alertas de continuidad: <strong>{summary.production_risk_escalations}</strong></p>
            <p>Compromiso original: <strong>{summary.original_promise_date}</strong></p>
            <p>Última promesa revisada: <strong>{summary.latest_revised_promise_date ?? "Sin cambio"}</strong></p>
          </div>
        )}
      </section>
    </section>
  );
}
