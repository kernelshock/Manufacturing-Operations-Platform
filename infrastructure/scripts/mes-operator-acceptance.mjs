/** G5.8: negative quantity, replay, conflict and actual actor evidence using browser session. */
export async function verifyOperatorAcceptance({evaluate, poll, fixture, operatorUser}) {
  const path = "/api/v1/mes/operations/" + fixture.source_operation_id;
  async function request(url,method="GET",body) {
    const options={method,credentials:"include",headers:{"Content-Type":"application/json"}};
    if(body!==undefined) options.body=JSON.stringify(body);
    return evaluate('(async()=>{const r=await fetch('+JSON.stringify(url)+','+
      JSON.stringify(options)+'); return {status:r.status,data:await r.json()}})()');
  }
  const completed = await request(path);
  if (completed.status!==200 || completed.data.status!=="COMPLETED" ||
      completed.data.completed_by!==operatorUser.user_id) {
    throw new Error("Completed operation not attributed to the assigned MES operator");
  }
  const event = await request(path+"/events");
  if(event.status!==200 || !event.data.some(x=>x.event_type==="COMPLETE" &&
       x.actor_user_id===operatorUser.user_id && Number(x.produced_quantity)===9.5)) {
    throw new Error("Operator completion event missing or mismatched");
  }
  for(const quantity of ["", "-2", "0", "not-a-number"]) {
    const result=await request(path+"/complete","POST",{produced_quantity:quantity});
    if(result.status!==422) throw new Error("Invalid quantity "+quantity+" accepted: "+result.status);
  }
  const replay=await request(path+"/complete","POST",{produced_quantity:"9.5"});
  if(replay.status!==200 || replay.data.idempotent_replay!==true) throw new Error("Completion idempotency failed");
  const conflict=await request(path+"/complete","POST",{produced_quantity:"8.5"});
  if(conflict.status!==409) throw new Error("Conflicting completed quantity not rejected");
  console.log("MES OPERATOR NEGATIVE ACCEPTANCE PASSED: invalid quantity 422, replay 200, conflict 409");
  console.log("MES OPERATOR ACTOR EVENT PASSED: recorded completion actor matches operator");
}
export async function verifyOperatorAuditAsAdmin({evaluate, fixture, operatorUser}) {
  const expression='(async()=>{const r=await fetch('+
    JSON.stringify("/api/v1/audit/events?action=mes.operation.complete&actor_user_id="+operatorUser.user_id+"&limit=100")+
    ');return {status:r.status,data:await r.json()}})()';
  const response=await evaluate(expression);
  if(response.status!==200 ||
    !response.data.some(item=>item.actor_user_id===operatorUser.user_id &&
      item.object_id===fixture.source_operation_id &&
      item.actor_username===operatorUser.username &&
      item.action==="mes.operation.complete" && item.outcome==="success")) {
    throw new Error("Auditable operator completion missing from immutable audit API");
  }
  console.log("MES OPERATOR AUDIT PASSED: admin-verified actor attribution and operation ID");
}
