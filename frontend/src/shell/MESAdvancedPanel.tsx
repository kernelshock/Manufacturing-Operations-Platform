import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../api/client";

type Operation = {
  id: string; dispatch_id: string; product_line_id: string; operation_code: string;
  operation_description: string; routing_operation_id?: string; routing_sequence_no: number;
  status: string; produced_quantity: string | null;
};
type Resource = { id: string; code: string; name: string; work_center_id: string };
type Handoff = { id: string; from_execution_operation_id: string; to_execution_operation_id: string; quantity: string; status: string };
type Trace = {
  successor_operation_id: string | null; predecessor_operation_id: string | null;
  produced_quantity: string | null; outgoing_transferred_quantity: string;
  incoming_received_quantity: string; rework_allocated_quantity: string;
  available_to_transfer: string | null;
};
type ReworkCase = {
  id: string; case_code: string; source_execution_operation_id: string;
  return_execution_operation_id: string; status: string; quantity: string; reason_code: string;
};
type ReworkStep = {
  id: string; case_id: string; sequence_no: number; operation_code: string;
  routing_operation_id: string; resource_id: string; status: string; produced_quantity: string | null;
};

const base = "/api/v1/mes";
const positive = (s: string) => /^\d+(?:\.\d{1,8})?$/.test(s) && Number(s) > 0;

export function successorCandidates(operations: Operation[], selected: Operation | null) {
  if (!selected) return [];
  return operations.filter(op => op.dispatch_id === selected.dispatch_id &&
    op.product_line_id === selected.product_line_id && op.id !== selected.id &&
    op.routing_sequence_no > selected.routing_sequence_no)
    .sort((a,b) => a.routing_sequence_no - b.routing_sequence_no);
}

export function MESAdvancedPanel({dispatchId,operations,selectedId,canEdit,resources,refresh,onChanged}: {
  dispatchId: string; operations: Operation[]; selectedId: string; canEdit: boolean;
  resources: Resource[]; refresh: number; onChanged: () => void;
}) {
  const selected = operations.find(op => op.id === selectedId && op.dispatch_id === dispatchId) ?? null;
  const successors = useMemo(() => successorCandidates(operations, selected),[operations,selected]);
  const [trace,setTrace] = useState<Trace | null>(null);
  const [handoffs,setHandoffs] = useState<Handoff[]>([]);
  const [cases,setCases] = useState<ReworkCase[]>([]);
  const [caseSteps,setCaseSteps] = useState<ReworkStep[]>([]);
  const [caseId,setCaseId] = useState("");
  const [targetId,setTargetId] = useState("");
  const [amount,setAmount] = useState("");
  const [reason,setReason] = useState("");
  const [caseCode,setCaseCode] = useState("");
  const [routingId,setRoutingId] = useState("");
  const [stepResourceId,setStepResourceId] = useState("");
  const [stepAmount,setStepAmount] = useState("");
  const [busy,setBusy] = useState(false);
  const [message,setMessage] = useState("");
  const [error,setError] = useState("");
  const [localRefresh,setLocalRefresh] = useState(0);
  const currentCase = cases.find(item => item.id === caseId) ?? null;
  const eligibleRoutes = operations.filter(op => selected && op.dispatch_id === dispatchId &&
    op.product_line_id === selected.product_line_id && op.routing_operation_id);
  const target = successors.find(op => op.id === targetId) ?? successors[0] ?? null;
  const selectedCaseSteps = caseSteps.filter(step => step.case_id === caseId).sort((a,b)=>a.sequence_no-b.sequence_no);

  useEffect(() => {
    setTrace(null);setHandoffs([]);setCases([]);setCaseSteps([]);
    setCaseId("");setTargetId("");setAmount("");setReason("");setCaseCode("");
    setRoutingId("");setStepResourceId("");setStepAmount("");setError("");setMessage("");
  },[dispatchId,selectedId]);

  useEffect(() => {
    if(!selected || !dispatchId) return;
    let live = true;
    Promise.all([
      apiFetch<Trace>(`${base}/operations/${selected.id}/wip-trace`),
      apiFetch<Handoff[]>(`${base}/operations/${selected.id}/handoffs`),
      apiFetch<ReworkCase[]>(`${base}/rework/dispatches/${dispatchId}/cases`)
    ]).then(([t,h,c])=>{if(live){setTrace(t);setHandoffs(h);setCases(c);
      setCaseId(old=>c.some(item=>item.id===old)?old:(c[0]?.id??""));}})
      .catch(e=>{if(live)setError(e instanceof Error?e.message:"No se pudo consultar WIP y retrabajos.");});
    return ()=>{live=false;};
  },[dispatchId,selectedId,selected?.status,refresh,localRefresh]);

  useEffect(() => {
    if(!caseId) {setCaseSteps([]);return;}
    let live=true;
    apiFetch<ReworkStep[]>(`${base}/rework/cases/${caseId}/steps`)
      .then(rows=>{if(live)setCaseSteps(rows);})
      .catch(e=>{if(live)setError(e instanceof Error?e.message:"No se pudieron consultar los pasos.");});
    return ()=>{live=false;};
  },[caseId,refresh,localRefresh]);

  async function act(path:string,payload:Record<string,string>={}) {
    if(!canEdit || !selected || selected.dispatch_id!==dispatchId) return;
    setBusy(true);setError("");setMessage("");
    try {
      await apiFetch<unknown>(path,{method:"POST",body:JSON.stringify(payload)});
      setMessage("Registro confirmado por MES.");setLocalRefresh(v=>v+1);onChanged();
    } catch(e) {setError(e instanceof Error?e.message:"Operación rechazada por MES.");}
    finally {setBusy(false);}
  }

  if(!selected) return null;
  return (
    <section className="content-section mes-advanced-panel" aria-label="WIP y retrabajo">
      <div className="section-heading"><div><p className="eyebrow">Ejecución gobernada</p>
        <h2>Transferencia WIP y retrabajo</h2></div></div>
      <p className="muted">Operación {selected.operation_code}. Los movimientos y reparaciones conservan la trazabilidad del despacho, sin alterar el routing maestro ni el programa APS.</p>
      {error ? <p className="inline-error" role="alert">{error}</p> : null}
      {message ? <p className="status-pill success" role="status">{message}</p> : null}
      <div className="mes-facts">
        <div><dt>Producidas</dt><dd>{trace?.produced_quantity ?? "No registrado"}</dd></div>
        <div><dt>Disponible para transferir</dt><dd>{trace?.available_to_transfer ?? "Sin evidencia"}</dd></div>
        <div><dt>WIP recibido</dt><dd>{trace?.incoming_received_quantity ?? "0"}</dd></div>
        <div><dt>Asignado a retrabajo</dt><dd>{trace?.rework_allocated_quantity ?? "0"}</dd></div>
      </div>
      <div className="mes-form">
        <h3>Transferir al proceso siguiente</h3>
        <label>Operación destino
          <select aria-label="Destino WIP" value={target?.id??""} onChange={e=>setTargetId(e.target.value)}>
            {successors.length===0?<option value="">Sin sucesor disponible</option>:successors.map(op=><option key={op.id} value={op.id}>{op.routing_sequence_no}. {op.operation_code} · {op.operation_description}</option>)}
          </select>
        </label>
        <label>Cantidad WIP
          <input aria-label="Cantidad WIP" inputMode="decimal" placeholder="Cantidad a transferir" value={amount} onChange={e=>setAmount(e.target.value.replace(",","."))}/>
        </label>
        <button type="button" disabled={!canEdit||busy||selected.status!=="COMPLETED"||!target||!positive(amount)}
          onClick={()=>target&&void act(`${base}/operations/${selected.id}/handoffs/transfer`,{to_execution_operation_id:target.id,quantity:amount})}>
          Transferir WIP
        </button>
        <h3>Recepción de WIP</h3>
        {handoffs.length===0?<p className="muted">No hay movimientos vinculados a esta operación.</p>:handoffs.map(h=>(
          <div className="mes-handoff-row" key={h.id}>
            <span>{h.quantity} · {h.status} · {operations.find(op=>op.id===h.to_execution_operation_id)?.operation_code??h.to_execution_operation_id.slice(0,8)}</span>
            {h.status==="TRANSFERRED" && <button type="button" disabled={!canEdit||busy}
              onClick={()=>void act(`${base}/handoffs/${h.id}/receive`)}>Recibir WIP</button>}
          </div>
        ))}
      </div>
      <div className="mes-form">
        <h3>Crear caso de retrabajo</h3>
        <label>Destino de retorno
          <select aria-label="Retorno retrabajo" value={target?.id??""} onChange={e=>setTargetId(e.target.value)}>
            {successors.length===0?<option value="">Sin sucesor</option>:successors.map(op=><option key={op.id} value={op.id}>{op.operation_code} · {op.operation_description}</option>)}
          </select>
        </label>
        <label>Código de caso<input value={caseCode} onChange={e=>setCaseCode(e.target.value)} placeholder="Código de retrabajo" /></label>
        <label>Motivo<input value={reason} onChange={e=>setReason(e.target.value)} placeholder="Código de causa" /></label>
        <label>Cantidad afectada<input inputMode="decimal" value={amount} onChange={e=>setAmount(e.target.value.replace(",","."))} placeholder="Cantidad retrabajo"/></label>
        <button type="button" disabled={!canEdit||busy||selected.status!=="COMPLETED"||!target||!caseCode.trim()||!reason.trim()||!positive(amount)}
          onClick={()=>target&&void act(`${base}/rework/cases`,{
            source_execution_operation_id:selected.id,return_execution_operation_id:target.id,
            case_code:caseCode.trim(),reason_code:reason.trim(),quantity:amount
          })}>Crear caso</button>
        <h3>Casos del despacho</h3>
        <label>Seleccionar caso
          <select aria-label="Caso de retrabajo" value={caseId} onChange={e=>setCaseId(e.target.value)}>
            {cases.length===0?<option value="">Sin casos</option>:cases.map(item=><option key={item.id} value={item.id}>{item.case_code} · {item.status} · {item.quantity}</option>)}
          </select>
        </label>
        {currentCase && <>
          <p className="muted">Estado: {currentCase.status}. Cantidad: {currentCase.quantity}. Motivo: {currentCase.reason_code}.</p>
          <h3>Ruta de reparación</h3>
          <label>Proceso
            <select aria-label="Proceso de reparación" value={routingId} onChange={e=>setRoutingId(e.target.value)}>
              <option value="">Seleccionar operación de routing</option>
              {eligibleRoutes.map(op=><option key={op.id} value={op.routing_operation_id}>{op.operation_code} · {op.operation_description}</option>)}
            </select>
          </label>
          <label>Recurso
            <select aria-label="Recurso de reparación" value={stepResourceId} onChange={e=>setStepResourceId(e.target.value)}>
              <option value="">Seleccionar recurso</option>
              {resources.map(res=><option key={res.id} value={res.id}>{res.code} · {res.name}</option>)}
            </select>
          </label>
          <button type="button" disabled={!canEdit||busy||!routingId||!stepResourceId||currentCase.status!=="OPEN"}
            onClick={()=>void act(`${base}/rework/cases/${caseId}/steps`,{routing_operation_id:routingId,resource_id:stepResourceId})}>
            Agregar paso de reparación
          </button>
          {selectedCaseSteps.map(step=><div className="mes-handoff-row" key={step.id}>
            <span>{step.sequence_no}. {step.operation_code} · {step.status} · {step.produced_quantity??"—"}</span>
            {step.status==="PENDING" && <button type="button" disabled={!canEdit||busy}
              onClick={()=>void act(`${base}/rework/steps/${step.id}/start`)}>Iniciar reparación</button>}
            {step.status==="RUNNING" && <>
              <label>Cantidad de salida<input aria-label="Cantidad de reparación" value={stepAmount} onChange={e=>setStepAmount(e.target.value.replace(",","."))} placeholder="Cantidad real"/></label>
              <button type="button" disabled={!canEdit||busy||!positive(stepAmount)}
                onClick={()=>void act(`${base}/rework/steps/${step.id}/complete`,{produced_quantity:stepAmount})}>
                Finalizar reparación</button>
            </>}
          </div>)}
          <button type="button" disabled={!canEdit||busy||currentCase.status==="RETURNED"||selectedCaseSteps.length===0||selectedCaseSteps.some(step=>step.status!=="COMPLETED")}
            onClick={()=>void act(`${base}/rework/cases/${caseId}/return`)}>
            Devolver retrabajo al flujo
          </button>
        </>}
      </div>
      {!canEdit?<p className="muted">Consulta de trazabilidad: para registrar movimientos se requiere permiso mes.edit y despacho liberado.</p>:null}
    </section>
  );
}
