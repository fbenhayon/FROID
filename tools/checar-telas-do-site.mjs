// Mede o froid-site em celular (390px) e em desktop (1280px e 1366px) no
// Chrome headless, pagina por pagina: rolagem horizontal, elementos que
// passam da borda da tela e fileira do header quebrando em duas linhas.
// Tambem grava uma captura de cada pagina no celular, para conferencia visual.
//
// Existe porque "funciona em tela pequena" nao se afirma lendo CSS: em
// 04/09/2026 o submenu de secoes, escondido por visibility, continuava no
// layout e a pagina rolava ate 614px numa tela de 400px. Isto mede.
//
// Uso (Git Bash ou PowerShell, da raiz do repositorio):
//     node tools/checar-telas-do-site.mjs [dir-das-capturas] [pagina.html ...]
// Sem argumentos: todas as paginas pt-BR de froid-site/, capturas em
// .codex-tmp/telas/. Chrome em C:/Program Files/Google/Chrome; outro caminho
// vai em FROID_CHROME. Sai com codigo 1 se alguma medicao acusar problema.
import { spawn } from "node:child_process";
import { mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SITE = join(REPO, "froid-site");
const CHROME = process.env.FROID_CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const [shotsArg, ...so] = process.argv.slice(2);
const shots = resolve(shotsArg || join(REPO, ".codex-tmp", "telas"));
mkdirSync(shots, { recursive: true });
const paginas = (so.length ? so : readdirSync(SITE).filter(f => f.endsWith(".html"))).sort();
const PORT = 9333;

const chrome = spawn(CHROME, [
  "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  "--allow-file-access-from-files", `--remote-debugging-port=${PORT}`, "about:blank",
], { stdio: "ignore" });

async function esperar(url, tentativas = 60) {
  for (let i = 0; i < tentativas; i++) {
    try { const r = await fetch(url); if (r.ok) return await r.json(); } catch {}
    await new Promise(r => setTimeout(r, 250));
  }
  throw new Error("chrome nao respondeu em " + url);
}

const versao = await esperar(`http://127.0.0.1:${PORT}/json/version`);
const ws = new WebSocket(versao.webSocketDebuggerUrl);
await new Promise((ok, err) => { ws.onopen = ok; ws.onerror = err; });

let id = 0;
const pendentes = new Map();
const eventos = [];
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pendentes.has(msg.id)) { pendentes.get(msg.id)(msg); pendentes.delete(msg.id); }
  else if (msg.method) eventos.push(msg);
};
function send(method, params = {}, sessionId) {
  return new Promise((ok) => { const i = ++id; pendentes.set(i, ok); ws.send(JSON.stringify({ id: i, method, params, sessionId })); });
}
async function esperarEvento(nome, sessionId, ms = 15000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    const k = eventos.findIndex(e => e.method === nome && e.sessionId === sessionId);
    if (k >= 0) { eventos.splice(k, 1); return; }
    await new Promise(r => setTimeout(r, 50));
  }
  throw new Error("sem evento " + nome);
}

const { targetId } = (await send("Target.createTarget", { url: "about:blank" })).result;
const { sessionId } = (await send("Target.attachToTarget", { targetId, flatten: true })).result;
await send("Page.enable", {}, sessionId);
await send("Runtime.enable", {}, sessionId);

// Roda dentro da pagina. Mede o que importa e nada mais.
const MEDIR = `(() => {
  const iw = window.innerWidth;
  const sw = document.documentElement.scrollWidth;
  const fora = [];
  for (const el of document.querySelectorAll("body *")) {
    const r = el.getBoundingClientRect();
    // Tabela larga dentro de contenor com rolagem propria (overflow-x auto) e o
    // comportamento desejado: so a tabela rola, a pagina nao.
    let contido = false;
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if (ox === "auto" || ox === "scroll" || ox === "hidden") { contido = true; break; }
    }
    if (!contido && r.width > 0 && r.right > iw + 1 && getComputedStyle(el).visibility !== "hidden") {
      fora.push(el.tagName.toLowerCase() + (typeof el.className === "string" && el.className ? "." + el.className.trim().split(/\\s+/).join(".") : "") + " right=" + Math.round(r.right));
      if (fora.length >= 6) break;
    }
  }
  const links = [...document.querySelectorAll(".nav-links > .nav-familia > .nav-menu > .nav-familia-rotulo, .nav-links > .nav-familia > a")];
  const tops = links.map(a => Math.round(a.getBoundingClientRect().top));
  const header = document.querySelector(".site-header");
  return { iw, sw, overflow: sw > iw, fora, linhasDoMenu: new Set(tops).size,
           alturaHeader: header ? Math.round(header.getBoundingClientRect().height) : null,
           altura: document.documentElement.scrollHeight };
})()`;

const VIEWS = [
  { nome: "celular", w: 390, h: 844, mobile: true, dpr: 2 },
  { nome: "desk1280", w: 1280, h: 800, mobile: false, dpr: 1 },
  { nome: "desk1366", w: 1366, h: 768, mobile: false, dpr: 1 },
];

const resultados = [];
for (const pagina of paginas) {
  for (const v of VIEWS) {
    await send("Emulation.setDeviceMetricsOverride", { width: v.w, height: v.h, deviceScaleFactor: v.dpr, mobile: v.mobile }, sessionId);
    await send("Page.navigate", { url: pathToFileURL(join(SITE, pagina)).href }, sessionId);
    await esperarEvento("Page.loadEventFired", sessionId);
    await new Promise(r => setTimeout(r, 300));
    const med = (await send("Runtime.evaluate", { expression: MEDIR, returnByValue: true }, sessionId)).result.result.value;
    resultados.push({ pagina, view: v.nome, ...med });
    if (v.nome === "celular") {
      const shot = (await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true,
        clip: { x: 0, y: 0, width: v.w, height: Math.min(med.altura, 6000), scale: 1 } }, sessionId)).result;
      writeFileSync(join(shots, pagina.replace(".html", "") + "-celular.png"), Buffer.from(shot.data, "base64"));
    }
  }
}

let problemas = 0;
for (const r of resultados) {
  const flags = [];
  if (r.overflow) flags.push(`ROLAGEM HORIZONTAL sw=${r.sw} > iw=${r.iw}`);
  if (r.fora.length) flags.push("fora da borda: " + r.fora.join("; "));
  if (r.view !== "celular" && r.linhasDoMenu > 1) flags.push(`menu em ${r.linhasDoMenu} linhas`);
  if (flags.length) { problemas++; console.log(`[!] ${r.pagina} ${r.view}: ${flags.join(" | ")}`); }
  else console.log(`ok  ${r.pagina} ${r.view} (header ${r.alturaHeader}px, menu ${r.linhasDoMenu} linha)`);
}
console.log(`\n${resultados.length} medicoes, ${problemas} com problema; capturas em ${shots}`);
ws.close();
chrome.kill();
process.exit(problemas ? 1 : 0);
