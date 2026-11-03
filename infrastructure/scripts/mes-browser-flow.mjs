/** G5.8: real DOM actions for the nominal MES execution lifecycle. */
export async function runNominalBrowserFlow({evaluate, type, poll, fixture}) {
  const root = "/api/v1/mes";
  const opPath = id => root + "/operations/" + id;
  async function readOperation(id) {
    const result = await evaluate('(async () => { const r = await fetch(' + JSON.stringify(opPath(id)) + '); return {code:r.status,data:await r.json()}; })()');
    if (result.code !== 200) throw new Error("MES operation read failed: " + result.code);
    return result.data;
  }
  async function expectState(id, state) {
    return poll(async () => {
      const result = await readOperation(id);
      return result.status === state ? result : null;
    }, "MES operation did not reach " + state);
  }
  async function click(label) {
    const expression = 'Array.from(document.querySelectorAll(".mes-capture-panel button")).find(b=>b.textContent.includes(' + JSON.stringify(label) + '))';
    await poll(async () => evaluate('Boolean(' + expression + ')'), "Missing MES button: " + label);
    await evaluate(expression + ".click()");
  }
  async function select(id) {
    const index = id === fixture.source_operation_id ? 0 : 1;
    await poll(async () => evaluate('document.querySelectorAll(".mes-operation-row").length === 2'), "MES rows unavailable");
    await evaluate('document.querySelectorAll(".mes-operation-row")[' + index + '].click()');
    await poll(async () => evaluate('Boolean(document.querySelector(".mes-capture-panel h3"))'), "MES operation detail missing");
  }
  async function fill(selector, value) {
    await poll(async () => evaluate('Boolean(document.querySelector(' + JSON.stringify(selector) + '))'), "MES input missing");
    await type(selector, value);
  }

  await select(fixture.source_operation_id);
  const resourceSelector = 'select[aria-label="Recurso real"]';
  await poll(async()=>evaluate('document.querySelectorAll('+JSON.stringify(resourceSelector+' option')+').length > 1'),"Descriptive resource selector was not populated");
  const choice = await evaluate('(()=>{const select=document.querySelector('+JSON.stringify(resourceSelector)+');const option=Array.from(select.options).find(item=>item.value==='+JSON.stringify(fixture.actual_resource_id)+');if(!option||!option.textContent.includes(" · "))return false;select.value=option.value;select.dispatchEvent(new Event("change",{bubbles:true}));return true})()');
  if (!choice) throw new Error("Canonical actual resource code/name not available");
  await fill(".mes-form input", "CAPACITY_DEVIATION");
  await click("Iniciar operación");
  const started = await expectState(fixture.source_operation_id, "RUNNING");
  if(started.actual_resource_id!==fixture.actual_resource_id || started.resource_deviation_reason!=="CAPACITY_DEVIATION") {
    throw new Error("Descriptive resource selection did not persist the canonical resource and reason");
  }
  console.log("MES resource selector PASSED: real code/name option captured as UUID");

  await fill('.mes-form input[placeholder="Código de causa"]', "PROCESS_CHECK");
  await click("Pausar operación");
  await expectState(fixture.source_operation_id, "PAUSED");

  await click("Reanudar operación");
  await expectState(fixture.source_operation_id, "RUNNING");

  // The React control must fail closed when quantity is blank.
  await click("Finalizar y registrar cantidad");
  await poll(async()=>evaluate('Boolean(document.querySelector(".inline-error[role=alert]"))'),"Blank quantity was not rejected by UI");
  await expectState(fixture.source_operation_id, "RUNNING");
  await fill('.mes-form input[placeholder="Cantidad real"]', "9.5");
  await click("Finalizar y registrar cantidad");
  const complete = await expectState(fixture.source_operation_id, "COMPLETED");
  if (Number(complete.produced_quantity) !== 9.5 || !complete.actual_finish) {
    throw new Error("First operation did not persist explicit quantity and finish");
  }

  await select(fixture.successor_operation_id);
  await click("Iniciar operación");
  await poll(async () => evaluate('Boolean(document.querySelector(".inline-error[role=alert]"))'), "MES did not reject missing predecessor WIP");
  await expectState(fixture.successor_operation_id, "PENDING");

  console.log("MES nominal browser phase PASSED: start/pause/resume/complete and blocked successor");
  return {readOperation, expectState, click, select, fill};
}
