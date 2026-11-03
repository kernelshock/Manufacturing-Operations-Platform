/** Actual Chrome/React/FastAPI/PostgreSQL browser smoke. Runs inside runtime-smoke.sh. */
import { spawn } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const origin = process.env.MOP_BROWSER_ORIGIN ?? "http://127.0.0.1:18080";
const username = process.env.MOP_ADMIN_USERNAME ?? "smoke-admin";
const password = process.env.MOP_BOOTSTRAP_ADMIN_PASSWORD;
if (!password) throw new Error("MOP_BOOTSTRAP_ADMIN_PASSWORD missing");
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
  console.log("MES browser smoke PASSED:", JSON.stringify(state));
} finally {
  ws?.close();
  chrome.kill("SIGTERM");
  await rm(dir, {recursive:true, force:true});
}
