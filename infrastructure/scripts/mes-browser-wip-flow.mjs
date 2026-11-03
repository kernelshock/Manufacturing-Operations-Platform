/** Advanced MES WIP/rework operations through the same authenticated browser session.
 * Advanced transfers, receipts, case creation and repair steps are driven through React controls.
 */
export async function runWipReworkBrowserFlow({evaluate, type, poll, fixture, operator}) {
  const base = "/api/v1/mes";
  async function request(path, method = "GET", body) {
    const js = '(async () => { const r = await fetch(' + JSON.stringify(path) +
      ', { method:' + JSON.stringify(method) +
      ', credentials:"include", headers:{"Content-Type":"application/json"}' +
      (body === undefined ? '' : ', body:' + JSON.stringify(JSON.stringify(body))) +
      ' }); return {status:r.status, data:await r.json()}; })()';
    return evaluate(js);
  }
  async function ok(path, method, body, expected = 200) {
    const response = await request(path, method, body);
    if (response.status !== expected) {
      throw new Error(path + " returned HTTP " + response.status + ": " + JSON.stringify(response.data));
    }
    return response.data;
  }

  const before = await ok(base + "/dispatches/" + fixture.dispatch_id);
  if (before.schedule_fingerprint !== fixture.schedule_fingerprint) throw new Error("APS publication fingerprint changed before WIP");

  // Drive all advanced actions using the real React interface; use GET only for assertions.
  const ui = ".mes-advanced-panel";
  async function setInput(selector, value) {
    await poll(async()=>evaluate('Boolean(document.querySelector('+JSON.stringify(selector)+'))'),"Advanced input missing: "+selector);
    await evaluate('document.querySelector('+JSON.stringify(selector)+').focus();document.querySelector('+JSON.stringify(selector)+').select()');
    await type(selector,value);
  }
  async function setOption(selector, value) {
    const found = await poll(async()=>evaluate('(()=>{const el=document.querySelector('+JSON.stringify(selector)+');return Boolean(el&&Array.from(el.options).some(option=>option.value==='+JSON.stringify(value)+'))})()'),"Option unavailable: "+selector);
    if(!found) throw new Error("Option missing");
    await evaluate('(()=>{const el=document.querySelector('+JSON.stringify(selector)+');el.value='+JSON.stringify(value)+';el.dispatchEvent(new Event("change",{bubbles:true}))})()');
  }
  async function press(label) {
    const expr='Array.from(document.querySelectorAll('+JSON.stringify(ui+' button')+')).find(b=>b.textContent.trim()==='+JSON.stringify(label)+'&&!b.disabled)';
    await poll(async()=>evaluate('Boolean('+expr+')'),"Advanced action disabled/missing: "+label);
    await evaluate(expr+'.click()');
  }
  await operator.select(fixture.source_operation_id);
  const caseCode = "RW-" + fixture.dispatch_code;
  await setInput(ui+' input[placeholder="Código de retrabajo"]',caseCode);
  await setInput(ui+' input[placeholder="Código de causa"]',"QUALITY_REPAIR");
  await setInput(ui+' input[placeholder="Cantidad retrabajo"]',"1.5");
  await press("Crear caso");
  const created = await poll(async()=>{
    const response = await ok(base+"/rework/dispatches/"+fixture.dispatch_id+"/cases");
    return response.find(item=>item.case_code===caseCode)??null;
  },"Rework case was not created through UI");
  const caseId = created.id;
  await setOption(ui+' select[aria-label="Caso de retrabajo"]',caseId);

  // Define the entire repair route before starting execution (G5.5 governance).
  const routeIds = [
    fixture.routing_operation_2_id,fixture.routing_operation_id,fixture.routing_operation_2_id
  ];
  for(let i=0;i<routeIds.length;i++) {
    await setOption(ui+' select[aria-label="Proceso de reparación"]',routeIds[i]);
    await setOption(ui+' select[aria-label="Recurso de reparación"]',fixture.resource_id);
    await press("Agregar paso de reparación");
    await poll(async()=>{
      const result=await ok(base+"/rework/cases/"+caseId+"/steps");
      return result.length===i+1;
    },"Repair step not saved through UI");
  }
  console.log("MES rework route UI PASSED: three governed steps added before execution");

  await setInput(ui+' input[placeholder="Cantidad a transferir"]',"8.0");
  await press("Transferir WIP");
  const transfers = await poll(async()=>{
    const rows=await ok(base+"/operations/"+fixture.source_operation_id+"/handoffs");
    return rows.filter(item=>item.to_execution_operation_id===fixture.successor_operation_id).length>0?rows:null;
  },"WIP transfer was not recorded from UI");
  const transfer=transfers.find(item=>item.to_execution_operation_id===fixture.successor_operation_id);
  await press("Recibir WIP");
  await poll(async()=>{
    const rows=await ok(base+"/operations/"+fixture.source_operation_id+"/handoffs");
    return rows.some(item=>item.id===transfer.id&&item.status==="RECEIVED");
  },"WIP receipt was not recorded through UI");
  console.log("MES WIP controls PASSED: transfer 8 and receive from React interface");

  for(let i=0;i<routeIds.length;i++) {
    await press("Iniciar reparación");
    await poll(async()=>{
      const rows=await ok(base+"/rework/cases/"+caseId+"/steps");
      return rows[i]?.status==="RUNNING";
    },"Repair step did not start through UI");
    await setInput(ui+' input[aria-label="Cantidad de reparación"]',"1.5");
    await press("Finalizar reparación");
    await poll(async()=>{
      const rows=await ok(base+"/rework/cases/"+caseId+"/steps");
      return rows[i]?.status==="COMPLETED" && Number(rows[i]?.produced_quantity)===1.5;
    },"Repair step was not completed through UI");
  }
  await press("Devolver retrabajo al flujo");
  const returned = await poll(async()=>{
    const result=await ok(base+"/rework/cases/"+caseId);
    return result.status==="RETURNED"?{case:result}:null;
  },"Rework return not saved through UI");
  console.log("MES rework controls PASSED: all repair steps executed and case returned via UI");
  await operator.select(fixture.successor_operation_id);

  // Nominal successor must be started and finished through React UI controls.
  await operator.click("Iniciar operación");
  await operator.expectState(fixture.successor_operation_id, "RUNNING");
  await operator.fill('.mes-form input[placeholder="Cantidad real"]', "9.5");
  await operator.click("Finalizar y registrar cantidad");
  const second = await operator.expectState(fixture.successor_operation_id, "COMPLETED");
  if (Number(second.produced_quantity) !== 9.5) throw new Error("Successor actual quantity mismatch");

  const feedback = await ok(base + "/feedback/dispatches/" + fixture.dispatch_id);
  const after = await ok(base + "/dispatches/" + fixture.dispatch_id);
  const trace = await ok(base + "/operations/" + fixture.source_operation_id + "/wip-trace");
  if (feedback.completed_count !== 2 || feedback.open_rework_count !== 0 ||
      after.schedule_fingerprint !== before.schedule_fingerprint ||
      feedback.schedule_fingerprint !== before.schedule_fingerprint) {
    throw new Error("Execution feedback or APS fingerprint invariant failed");
  }
  if (Number(trace.outgoing_transferred_quantity) !== 8 ||
      Number(trace.rework_allocated_quantity) !== 1.5) {
    throw new Error("WIP allocation does not reconcile");
  }
  console.log("MES browser E2E PASSED: " + JSON.stringify({
    dispatch: fixture.dispatch_code,
    completed: feedback.completed_count,
    transferred: trace.outgoing_transferred_quantity,
    reworkReturned: returned.case.status,
    fingerprintUnchanged: true
  }));
}
