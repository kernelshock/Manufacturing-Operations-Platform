/** Actual Chrome/React/FastAPI/PostgreSQL browser smoke. Runs inside runtime-smoke.sh. */
import { spawn } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runNominalBrowserFlow } from "./mes-browser-flow.mjs";
import { runWipReworkBrowserFlow } from "./mes-browser-wip-flow.mjs";
import { verifyOperatorAcceptance, verifyOperatorAuditAsAdmin } from "./mes-operator-acceptance.mjs";

const origin = process.env.MOP_BROWSER_ORIGIN ?? "http://127.0.0.1:18080";
const accountsPath = process.env.MOP_MES_RBAC_USERS_JSON;
if (!accountsPath || !process.env.MOP_RBAC_TEST_PASSWORD || !process.env.MOP_BOOTSTRAP_ADMIN_PASSWORD) {
  throw new Error("Operator identity, password or admin audit credentials missing");
}
const accounts = JSON.parse(await readFile(accountsPath, "utf8"));
const username = accounts.operator.username;
const password = process.env.MOP_RBAC_TEST_PASSWORD;
if (!process.env.MOP_MES_FIXTURE_JSON) throw new Error("MES fixture manifest missing");
const fixture = JSON.parse(await readFile(process.env.MOP_MES_FIXTURE_JSON, "utf8"));
const dir = await mkdtemp(join(tmpdir(), "mop-chrome-"));
const chrome = spawn(process.env.MOP_CHROME_BINARY ?? "google-chrome", [
  "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
  "--no-first-run", "--remote-debugging-port=0", "--user-data-dir=" + dir, "about:blank",
], { stdio: "ignore" });
let ws;
let nextId = 0;
const waiting = new Map();
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function poll(fn, error, timeout = 30000) {
  const until = Date.now() + timeout;
  while (Date.now() < until) {
    try { const value = await fn(); if (value) return value; }
    catch { /* application or browser still starting */ }
    await sleep(200);
  }
  throw new Error(error);
}
function command(method, params = {}) {
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => { waiting.delete(id); reject(new Error("CDP timeout: " + method)); }, 15000);
    waiting.set(id, {resolve, reject, timeout});
    ws.send(JSON.stringify({id, method, params}));
  });
}
async function evaluate(expression) {
  const reply = await command("Runtime.evaluate", {expression, returnByValue:true, awaitPromise:true});
  if (reply.exceptionDetails) throw new Error("Browser evaluation failed");
  return reply.result?.value;
}
async function type(selector, value) {
  const expr = "document.querySelector(" + JSON.stringify(selector) + ")";
  if (!await evaluate("Boolean(" + expr + ")")) throw new Error("Missing input: " + selector);
  await evaluate(expr + ".focus()");
  await command("Input.insertText", {text:value});
}
try {
  const port = await poll(async () => {
    const value = (await readFile(join(dir, "DevToolsActivePort"), "utf8")).split("\n")[0];
    return Number(value) > 0 ? Number(value) : null;
  }, "Chrome did not start");
  const target = await poll(async () => {
    const response = await fetch("http://127.0.0.1:" + port + "/json/list");
    return (await response.json()).find(item => item.type === "page");
  }, "Chrome page target missing");
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, {once:true});
    ws.addEventListener("error", reject, {once:true});
  });
  ws.addEventListener("message", event => {
    const packet = JSON.parse(event.data);
    if (packet.id && waiting.has(packet.id)) {
      const pending = waiting.get(packet.id);
      waiting.delete(packet.id);
      clearTimeout(pending.timeout);
      packet.error ? pending.reject(new Error(packet.error.message)) : pending.resolve(packet.result);
    }
  });
  await command("Page.enable");
  await command("Runtime.enable");
  await command("Page.navigate", {url:origin});
  await poll(async () => await evaluate('Boolean(document.querySelector("input[autocomplete=username]"))'), "Login UI did not render");
  await type("input[autocomplete=username]", username);
  await type("input[autocomplete=current-password]", password);
  await evaluate("document.querySelector('form').requestSubmit()");
  await poll(async () => await evaluate('Boolean(document.querySelector("nav[aria-label=\'Módulos principales\']"))'), "Authentication failed or app shell missing");
  const nav = await evaluate('Array.from(document.querySelectorAll("nav button")).map(item=>item.textContent)');
  if (!nav.some(item => item.includes("MES / Planta"))) throw new Error("MES navigation missing");
  await evaluate('Array.from(document.querySelectorAll("nav button")).find(item=>item.textContent.includes("MES / Planta")).click()');
  await poll(async () => await evaluate('document.body.textContent.includes("Seguimiento real de producción")'), "MES screen did not render");
  await poll(async () => await evaluate('document.body.textContent.includes("Sin despachos disponibles") || Boolean(document.querySelector(".mes-operation-row"))'), "MES dispatch state missing");
  const state = await evaluate('({selector:Boolean(document.querySelector("#mes-dispatch")), empty:document.body.textContent.includes("Sin despachos disponibles"), rows:document.querySelectorAll(".mes-operation-row").length})');
  if (!state.selector || (!state.empty && state.rows === 0)) throw new Error("Invalid MES screen state");
  if (state.empty || state.rows !== 2) throw new Error("Two-operation RELEASED dispatch is required for G5.8");
  const dispatchId = await evaluate('document.querySelector("#mes-dispatch").value');
  if (dispatchId !== fixture.dispatch_id) throw new Error("Wrong active MES dispatch");
  const operator = await runNominalBrowserFlow({evaluate, type, poll, fixture});
  await runWipReworkBrowserFlow({evaluate, type, poll, fixture, operator});
  await verifyOperatorAcceptance({evaluate, poll, fixture, operatorUser:accounts.operator});
  const logout = await evaluate('(async()=>{const r=await fetch("/api/v1/auth/logout",{method:"POST"});return r.status})()');
  if (logout !== 204) throw new Error("Operator logout failed");
  await command("Page.navigate", {url:origin});
  await poll(async()=>evaluate('Boolean(document.querySelector("input[autocomplete=username]"))'),"Admin audit login missing");
  await type("input[autocomplete=username]",process.env.MOP_ADMIN_USERNAME ?? "smoke-admin");
  await type("input[autocomplete=current-password]",process.env.MOP_BOOTSTRAP_ADMIN_PASSWORD);
  await evaluate('document.querySelector("form").requestSubmit()');
  await poll(async()=>evaluate('Boolean(document.querySelector("nav"))'),"Admin audit authentication failed");
  await verifyOperatorAuditAsAdmin({evaluate,fixture,operatorUser:accounts.operator});
} finally {
  ws?.close();
  chrome.kill("SIGTERM");
  // Chrome may still be writing its profile after the parent is signalled.
  await Promise.race([
    new Promise(resolve => chrome.once("exit", resolve)),
    sleep(2000)
  ]);
  await rm(dir, {recursive:true, force:true, maxRetries:15, retryDelay:200});
}
