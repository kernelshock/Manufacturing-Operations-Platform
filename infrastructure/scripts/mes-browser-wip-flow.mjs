/** Advanced MES WIP/rework operations through the same authenticated browser session.
 * G5.7 has no WIP/rework buttons; the operator actions stay DOM-driven.
 */
export async function runWipReworkBrowserFlow({evaluate, fixture, operator}) {
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

  const created = await ok(base + "/rework/cases", "POST", {
    source_execution_operation_id: fixture.source_operation_id,
    return_execution_operation_id: fixture.successor_operation_id,
    case_code: "RW-" + fixture.dispatch_code,
    reason_code: "QUALITY_REPAIR",
    quantity: "1.5"
  });
  const caseId = created.case.id;
  const transfer = await ok(base + "/operations/" + fixture.source_operation_id + "/handoffs/transfer", "POST", {
    to_execution_operation_id: fixture.successor_operation_id,
    quantity: "8.0"
  });
  await ok(base + "/handoffs/" + transfer.handoff.id + "/receive", "POST", {});

  for (const routing of [
    fixture.routing_operation_2_id,
    fixture.routing_operation_id,
    fixture.routing_operation_2_id
  ]) {
    const step = await ok(base + "/rework/cases/" + caseId + "/steps", "POST", {
      routing_operation_id: routing,
      resource_id: fixture.resource_id
    });
    await ok(base + "/rework/steps/" + step.id + "/start", "POST", {});
    await ok(base + "/rework/steps/" + step.id + "/complete", "POST", {produced_quantity:"1.5"});
  }
  const returned = await ok(base + "/rework/cases/" + caseId + "/return", "POST", {});
  if (returned.case.status !== "RETURNED") throw new Error("Rework case has not returned");

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
