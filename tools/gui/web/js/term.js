// Bottom dock of terminals (xterm.js over the backend's /ws/term): attach to an agent's herdr pane, a shell in the
// project, or ssh into the project's server. Terminals survive page changes; closing a tab detaches (agents keep running).
import { S, $, esc, icon, hooks, popMenu, allAgents, agentLabel, toast, token } from "./core.js";

const T = { tabs: [], active: null, open: false, seq: 0 };

function cssVar(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
function theme() {
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  return { background: cssVar("--sunken"), foreground: cssVar("--ink"), cursor: cssVar("--accent"), selectionBackground: dark ? "#3a4a80" : "#c9d4ff",
    black: dark ? "#2a2a2e" : "#3a3a3c" };
}

export function openTerminal(spec) {
  const key = JSON.stringify([spec.kind, spec.pane, spec.project, spec.path, spec.host, spec.session]);
  let t = T.tabs.find((x) => x.key === key && x.alive);
  if (!t) t = create(spec, key);
  show(true);
  activate(t.id);
}

function create(spec, key) {
  const id = ++T.seq;
  const label = spec.label || (spec.kind === "attach" ? agentLabel(allAgents().find((a) => a.pane === spec.pane)) : spec.kind === "ssh" ? `ssh ${spec.server || ""}` : `shell · ${spec.project}`);
  const el = document.createElement("div");
  el.className = "term";
  el.hidden = true;
  $("#dock .terms").appendChild(el);
  const term = new window.Terminal({ fontFamily: 'ui-monospace, "SF Mono", Menlo, monospace', fontSize: 12.5, lineHeight: 1.15, cursorBlink: true,
    allowProposedApi: true, theme: theme(), scrollback: 5000, macOptionIsMeta: true });
  const fit = new window.FitAddon.FitAddon();
  term.loadAddon(fit);
  term.loadAddon(new window.WebLinksAddon.WebLinksAddon((e, uri) => window.open(uri, "_blank")));
  term.open(el);
  const t = { id, key, spec, label, el, term, fit, ws: null, alive: true };
  T.tabs.push(t);
  connect(t);
  term.onData((d) => t.ws && t.ws.readyState === 1 && t.ws.send(JSON.stringify({ t: "in", d })));
  term.onResize(({ cols, rows }) => t.ws && t.ws.readyState === 1 && t.ws.send(JSON.stringify({ t: "resize", cols, rows })));
  new ResizeObserver(() => { if (!el.hidden && el.offsetWidth) try { fit.fit(); } catch (_) { /* not laid out yet */ } }).observe(el);
  return t;
}

async function connect(t) {
  const tok = await token();
  const q = new URLSearchParams(Object.fromEntries(Object.entries({ kind: t.spec.kind, pane: t.spec.pane, project: t.spec.project, path: t.spec.path,
    host: t.spec.host, session: t.spec.session, token: tok }).filter(([, v]) => v)));
  const ws = new WebSocket(`ws://${location.host}/ws/term?${q}`);
  ws.binaryType = "arraybuffer";
  t.ws = ws; t.alive = true;
  t.el.querySelector(".term-msg")?.remove();
  ws.onopen = () => { try { t.fit.fit(); } catch (_) { /* hidden */ } ws.send(JSON.stringify({ t: "resize", cols: t.term.cols, rows: t.term.rows })); if (t.id === T.active) t.term.focus(); };
  ws.onmessage = (e) => t.term.write(typeof e.data === "string" ? e.data : new Uint8Array(e.data));
  ws.onclose = () => {
    t.alive = false;
    const m = document.createElement("div");
    m.className = "term-msg";
    m.innerHTML = `${t.spec.kind === "attach" ? "Detached" : "Ended"} · <a>reconnect</a>`;
    m.querySelector("a").onclick = async () => { t.term.reset(); await token(true); connect(t); };
    t.el.appendChild(m);
    renderTabs();
  };
  renderTabs();
}

function activate(id) {
  T.active = id;
  T.tabs.forEach((t) => { t.el.hidden = t.id !== id; });
  const t = T.tabs.find((x) => x.id === id);
  if (t) setTimeout(() => { try { t.fit.fit(); } catch (_) { /* hidden */ } t.term.focus(); }, 20);
  renderTabs();
}

function closeTab(id) {
  const i = T.tabs.findIndex((x) => x.id === id);
  if (i < 0) return;
  const t = T.tabs[i];
  try { t.ws && t.ws.close(); } catch (_) { /* closed */ }
  t.term.dispose(); t.el.remove();
  T.tabs.splice(i, 1);
  if (!T.tabs.length) return show(false);
  if (T.active === id) activate(T.tabs[Math.max(0, i - 1)].id);
  else renderTabs();
}

function renderTabs() {
  const bar = $("#dock .dock-tabs");
  if (!bar) return;
  bar.innerHTML = T.tabs.map((t) => `<div class="dtab ${t.id === T.active ? "on" : ""}" data-id="${t.id}">${icon(t.spec.kind === "ssh" ? "server" : t.spec.kind === "attach" ? "chat" : "term")}
      <span>${esc(t.label)}</span>${t.alive ? "" : `<span class="muted">(ended)</span>`}<span class="x" data-x="${t.id}">✕</span></div>`).join("")
    + `<button class="btn ghost sm icon" id="dk-add" title="New terminal">${icon("plus")}</button><span class="grow"></span>
       <button class="btn ghost sm icon" id="dk-hide" title="Hide (⌃\`)">${icon("x")}</button>`;
  bar.querySelectorAll(".dtab").forEach((d) => d.onclick = (e) => { if (e.target.dataset.x) closeTab(+e.target.dataset.x); else activate(+d.dataset.id); });
  $("#dk-add").onclick = (e) => newMenu(e.currentTarget);
  $("#dk-hide").onclick = () => show(false);
}

export function newMenu(anchor) {
  const p = S.data && S.route.project ? S.data : null;
  const items = [];
  if (p) {
    items.push({ label: `Shell in ${p.name}`, icon: "term", run: () => openTerminal({ kind: "shell", project: p.name }) });
    if (p.server) items.push({ label: `SSH to ${p.server}`, hint: p.server_root, icon: "server", run: () => openTerminal({ kind: "ssh", project: p.name, server: p.server, label: `ssh ${p.server}` }) });
  }
  const agents = allAgents().filter((a) => !p || a.project === p.name);
  if (agents.length) items.push({ header: "Attach to an agent" }, ...agents.map((a) => ({ label: agentLabel(a), hint: a.tab_label, icon: "chat", run: () => openTerminal({ kind: "attach", pane: a.pane, label: agentLabel(a) }) })));
  if (!items.length) return toast("Open a project first");
  popMenu(anchor, items);
}

export function typeIntoTerminal(el, text) {
  // a file dropped on a terminal: its path goes to the pty as typed input, as in Terminal
  const t = T.tabs.find((x) => x.el === el) || T.tabs.find((x) => x.id === T.active);
  if (!t || !t.ws || t.ws.readyState !== 1) return false;
  t.ws.send(JSON.stringify({ t: "in", d: text }));
  t.term.focus();
  return true;
}

export function show(on) {
  T.open = on;
  $("#dock").hidden = !on;
  $("#dock-resize").hidden = !on;
  if (on && !T.tabs.length) { renderTabs(); }
  if (on) { const t = T.tabs.find((x) => x.id === T.active); if (t) setTimeout(() => { try { t.fit.fit(); } catch (_) { /* hidden */ } t.term.focus(); }, 30); }
}
export function toggleDock() {
  if (T.open) return show(false);
  if (!T.tabs.length) {
    const p = S.route.project;
    if (p) return openTerminal({ kind: "shell", project: p });
    return toast("Open a project first");
  }
  show(true);
}

export function initDock() {
  $("#dock").innerHTML = `<div class="dock-tabs"></div><div class="terms"></div>`;
  const bar = $("#dock-resize"), root = document.documentElement;
  const h = +localStorage.getItem("rd.dockh");
  if (h) root.style.setProperty("--dock-h", h + "px");
  bar.onpointerdown = (e) => {
    bar.setPointerCapture(e.pointerId);
    const bottom = $("#center").getBoundingClientRect().bottom;
    bar.onpointermove = (ev) => root.style.setProperty("--dock-h", Math.max(120, Math.min(window.innerHeight - 160, bottom - ev.clientY)) + "px");
    bar.onpointerup = () => { bar.onpointermove = null; try { localStorage.setItem("rd.dockh", parseInt(getComputedStyle(root).getPropertyValue("--dock-h"))); } catch (_) { /* ignore */ } };
  };
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => T.tabs.forEach((t) => { t.term.options.theme = theme(); }));
  hooks.openTerminal = openTerminal;
}
