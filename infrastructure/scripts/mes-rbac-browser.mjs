/** G5.8 role-specific browser/UI + server API enforcement against live CI runtime. */
import { spawn } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const origin = process.env.MOP_BROWSER_ORIGIN ?? "http://127.0.0.1:18080";
const password = process.env.MOP_RBAC_TEST_PASSWORD;
if (!password || !process.env.MOP_MES_RBAC_USERS_JSON || !process.env.MOP_MES_FIXTURE_JSON) {
  throw new Error("Missing isolated RBAC test credentials or fixture manifest");
}
const users = JSON.parse(await readFile(process.env.MOP_MES_RBAC_USERS_JSON, "utf8"));
const fixture = JSON.parse(await readFile(process.env.MOP_MES_FIXTURE_JSON, "utf8"));
const dir = await mkdtemp(join(tmpdir(), "mop-rbac-chrome-"));
const chrome = spawn(process.env.MOP_CHROME_BINARY ?? "google-chrome", [
  "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
  "--no-first-run", "--remote-debugging-port=0", "--user-data-dir=" + dir, "about:blank",
], {stdio:"ignore"});
let ws;
let next = 0;
const waiting = new Map();
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function poll(callback, description, timeout = 30000) {
  const limit = Date.now() + timeout;
  while (Date.now() < limit) {
    try { const value = await callback(); if (value) return value; }
    catch { /* Navigation or async data still settling */ }
    await sleep(150);
  }
  throw new Error(description);
}
function command(method, params = {}) {
  const id = ++next;
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => { waiting.delete(id); reject(new Error("CDP timeout: " + method)); }, 15000);
    waiting.set(id, {resolve, reject, timeout});
    ws.send(JSON.stringify({id, method, params}));
  });
}
async function evaluate(expression) {
  const response = await command("Runtime.evaluate", {expression, returnByValue:true, awaitPromise:true});
  if (response.exceptionDetails) throw new Error("Browser script error: " + JSON.stringify(response.exceptionDetails.exception?.description));
  return response.result?.value;
}
async function navigate() {
  await command("Page.navigate", {url:origin});
}
async function api(path, method="GET", body) {
  const init = {method, credentials:"include", headers:{"Content-Type":"application/json"}};
  if (body !== undefined) init.body = JSON.stringify(body);
  const expression = '(async () => {const r=await fetch(' + JSON.stringify(path) +
    ',' + JSON.stringify(init) + '); return {status:r.status};})()';
  return (await evaluate(expression)).status;
}
async function check(expected, path, method="GET", body) {
  const actual = await api(path, method, body);
  if (actual !== expected) {
    throw new Error(method + " " + path + " expected " + expected + " got " + actual);
  }
}
async function input(selector, value) {
  await poll(() => evaluate('Boolean(document.querySelector(' + JSON.stringify(selector) + '))'), "Login input missing");
  await evaluate('document.querySelector(' + JSON.stringify(selector) + ').focus()');
  await command("Input.insertText", {text:value});
}
async function login(username, loginPassword) {
  await navigate();
  await poll(() => evaluate('Boolean(document.querySelector("input[autocomplete=username]"))'), "Login page missing");
  await input('input[autocomplete=username]', username);
  await input('input[autocomplete=current-password]', loginPassword);
  await evaluate('document.querySelector("form").requestSubmit()');
  await poll(() => evaluate('Boolean(document.querySelector("nav"))'), "Authentication did not render shell");
}
async function logout() {
  await check(204, "/api/v1/auth/logout", "POST");
}
async function inspectUI({mesVisible, captureVisible}) {
  const nav = await evaluate('Array.from(document.querySelectorAll("nav button")).map(e=>e.textContent)');
  const hasMes = nav.some(value=>value.includes("MES / Planta"));
  if (hasMes !== mesVisible) throw new Error("MES navigation visibility inconsistent with permissions");
  if (!mesVisible) return;
  await evaluate('Array.from(document.querySelectorAll("nav button")).find(e=>e.textContent.includes("MES / Planta")).click()');
  await poll(() => evaluate('document.querySelectorAll(".mes-operation-row").length === 2'), "Two MES operations not rendered");
  const hasCapture = await evaluate('Array.from(document.querySelectorAll(".mes-capture-panel button")).some(e=>e.textContent.includes("Iniciar operación"))');
  if (hasCapture !== captureVisible) throw new Error("MES capture control visibility mismatched");
}

try {
  const port = await poll(async () => {
    const first = (await readFile(join(dir,"DevToolsActivePort"),"utf8")).split("\n")[0];
    return Number(first) > 0 ? Number(first) : null;
  }, "RBAC Chrome failed to start");
  const target = await poll(async () => {
    const response = await fetch("http://127.0.0.1:" + port + "/json/list");
    return (await response.json()).find(item => item.type === "page");
  }, "Chrome target unavailable");
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{
    ws.addEventListener("open",resolve,{once:true});
    ws.addEventListener("error",reject,{once:true});
  });
  ws.addEventListener("message", event => {
    const value = JSON.parse(event.data);
    if (value.id && waiting.has(value.id)) {
      const pending = waiting.get(value.id);
      waiting.delete(value.id);
      clearTimeout(pending.timeout);
      value.error ? pending.reject(new Error(value.error.message)) : pending.resolve(value.result);
    }
  });
  await command("Page.enable");
  await command("Runtime.enable");
  await navigate();
  await poll(() => evaluate('Boolean(document.querySelector("input[autocomplete=username]"))'), "Anonymous login page missing");

  const read = "/api/v1/mes/dispatches/" + fixture.dispatch_id + "/operations";
  const change = "/api/v1/mes/operations/00000000-0000-4000-8000-000000000001/start";
  await check(401, read);
  await check(401, change, "POST", {});
  console.log("MES RBAC anonymous PASS: HTTP 401");

  await login(users.unprivileged.username,password);
  await check(403, read);
  await check(403, "/api/v1/mes/resources");
  await check(403, change, "POST", {});
  await inspectUI({mesVisible:false,captureVisible:false});
  console.log("MES RBAC unprivileged PASS: hidden + HTTP 403");
  await logout();

  await login(users.viewer.username,password);
  await check(200, "/api/v1/mes/resources");
  await check(200, read);
  await check(403, change, "POST", {});
  await check(403, "/api/v1/iam/users");
  await inspectUI({mesVisible:true,captureVisible:false});
  console.log("MES RBAC viewer PASS: read 200, mutations 403, no action controls");
  await logout();

  await login(users.operator.username,password);
  await check(200, "/api/v1/mes/resources");
  await check(403, "/api/v1/core/resources");
  await check(200, read);
  await check(404, change, "POST", {});
  await check(403, "/api/v1/iam/users");
  await inspectUI({mesVisible:true,captureVisible:true});
  console.log("MES RBAC operator PASS: mes.read+edit, no admin, write reaches service");
  await logout();

  // Bootstrap admin has access to all three domains.
  await login(process.env.MOP_ADMIN_USERNAME ?? "smoke-admin", process.env.MOP_BOOTSTRAP_ADMIN_PASSWORD);
  await check(200, read);
  await check(404, change, "POST", {});
  await check(200, "/api/v1/iam/users");
  await inspectUI({mesVisible:true,captureVisible:true});
  console.log("MES RBAC admin PASS: MES + administrative API and UI controls");
  console.log("MES RBAC ACCEPTANCE PASSED: anonymous, unprivileged, viewer, operator, admin");
} finally {
  ws?.close();
  chrome.kill("SIGTERM");
  await Promise.race([new Promise(resolve=>chrome.once("exit",resolve)),sleep(2000)]);
  await rm(dir,{recursive:true,force:true,maxRetries:15,retryDelay:200});
}
