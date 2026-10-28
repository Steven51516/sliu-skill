// research-gui front end: projects, maps as DAGs, tickets, read-only file trees (Mac and server), Start team.
"use strict";

const S = {
  projects: [], unregistered: [], data: null, dataSig: "", route: {},
  showClosed: false, scope: "map", viewer: null, trees: {}, dagView: null, job: null,
};
const POLL_MS = 5000;
const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const STATUS_CLASS = (s) => "st-" + (["open", "claimed", "running", "held", "resolved", "parked", "superseded", "closed",
  "paused", "working", "idle", "done", "blocked", "unknown"].includes(s) ? s : "other");
const ACTIVE = new Set(["claimed", "running"]);

async function get(path, params = {}) {
  const r = await fetch(path + "?" + new URLSearchParams(params));
  const j = await r.json().catch(() => ({ error: `HTTP ${r.status}` }));
  if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
  return j;
}
async function post(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "X-RG": "1" }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({ error: `HTTP ${r.status}` }));
  if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
  return j;
}
function toast(msg, ms = 3500) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), ms);
}
const fmtSize = (n) => n == null ? "" : n < 1024 ? `${n} B` : n < 1 << 20 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(1)} MB`;
const pill = (s, text) => `<span class="pill ${STATUS_CLASS(s)}${s === "working" ? " pulse" : ""}">${esc(text ?? s)}</span>`;

// ---------- routing: #/<project>[/map/<folder>[/<tab>[/<ticket folder>]]] ----------

function parseRoute() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
  return { project: parts[0] || null, map: parts[1] === "map" ? parts[2] : null, tab: parts[3] || "dag", ticket: parts[4] || null };
}
function go(r) {
  const parts = [r.project];
  if (r.map) parts.push("map", r.map, r.tab || "dag", ...(r.ticket ? [r.ticket] : []));
  location.hash = "#/" + parts.map(encodeURIComponent).join("/");
}
window.addEventListener("hashchange", () => route());

async function route() {
  const prev = S.route;
  S.route = parseRoute();
  if (!S.route.project && S.projects.length) return go({ project: S.projects[0].name });
  if (S.route.project !== prev.project) { S.data = null; S.dataSig = ""; S.trees = {}; S.viewer = null; S.dagView = null; }
  if (S.route.map !== prev.map) { S.trees = {}; S.viewer = null; S.dagView = null; }
  renderSide();
  if (!S.data && S.route.project) await loadProject();
  render();
}

// ---------- data ----------

async function loadProjects() {
  try {
    const j = await get("/api/projects");
    S.projects = j.projects; S.unregistered = j.unregistered; S.config = j.config;
  } catch (e) { S.sideError = e.message; }
  renderSide();
}
async function loadProject() {
  if (!S.route.project) return;
  try {
    const d = await get("/api/project", { name: S.route.project });
    const sig = JSON.stringify(d);
    if (sig === S.dataSig) return false;
    const mapsSig = JSON.stringify(d.maps), oldMapsSig = S.data && JSON.stringify(S.data.maps);
    S.data = d; S.dataSig = sig; S.err = null;
    return mapsSig !== oldMapsSig ? "maps" : "live";
  } catch (e) { S.err = e.message; S.data = null; return "maps"; }
}
async function poll() {
  await loadProjects();
  const changed = await loadProject();
  if (!changed) return;
  if (!S.route.map) render();
  else if (changed === "maps" && S.route.tab === "dag") renderMapPage(true);
  else renderMapHead();
}

// ---------- sidebar ----------

function renderSide() {
  $("#projects").innerHTML = S.projects.map((p) => `
    <a href="#/${encodeURIComponent(p.name)}" class="${p.name === S.route.project ? "on" : ""}">
      <span class="name">${esc(p.name)}</span>
      ${p.ok === false ? `<span class="badge waiting" title="${esc(p.error)}">!</span>` : ""}
      ${p.waiting ? `<span class="badge waiting" title="waiting on you">${p.waiting}</span>` : ""}
      ${p.working ? `<span class="badge working" title="agents working">${p.working}</span>` : ""}
      ${p.agents && !p.working ? `<span class="badge" title="agents live">${p.agents}</span>` : ""}
    </a>`).join("") || `<div class="empty" style="padding:12px 16px">No projects in<br><code>${esc(S.config || "projects.toml")}</code></div>`;
  $("#unregistered").innerHTML = S.unregistered.length ? `<div>Not registered yet:</div>` + S.unregistered.map((u) => `
    <div class="row"><span class="mono">${esc(u.name)}</span><button class="small" data-add="${esc(u.name)}" data-path="${esc(u.path)}">Add</button></div>`).join("") : "";
  $("#unregistered").querySelectorAll("[data-add]").forEach((b) => b.onclick = async () => {
    try { await post("/api/add-project", { name: b.dataset.add, path: b.dataset.path }); toast(`Added ${b.dataset.add}: set its server in projects.toml`); loadProjects(); }
    catch (e) { toast(e.message); }
  });
  const d = S.data;
  $("#side-foot").innerHTML = (d && d.dry_run ? `<div class="dry">dry run: Start sends nothing</div>` : "")
    + (d && d.herdr_error ? `<div class="err">herdr: ${esc(d.herdr_error)}</div>` : "")
    + (S.sideError ? `<div class="err">${esc(S.sideError)}</div>` : "")
    + `<div>refreshes every ${POLL_MS / 1000} s</div>`;
}

// ---------- project page ----------

function render() {
  if (!S.route.project) { $("#main").innerHTML = `<div class="empty">Pick a project.</div>`; return; }
  if (S.err) { $("#main").innerHTML = `<div class="page"><div class="err">${esc(S.err)}</div></div>`; return; }
  if (!S.data) { $("#main").innerHTML = `<div class="empty">Loading…</div>`; return; }
  if (S.route.map) return renderMapPage(false);
  renderProject();
}

function renderProject() {
  const d = S.data, open = d.maps.filter((m) => m.status !== "closed"), closed = d.maps.filter((m) => m.status === "closed");
  $("#main").innerHTML = `<div class="page">
    <div class="head"><h1>${esc(d.name)}</h1><span class="grow"></span>
      <button data-vs="local" data-path="" data-dir="1">VS Code · Mac</button>
      ${d.server ? `<button data-vs="server" data-path="" data-dir="1">VS Code · ${esc(d.server)}</button>` : ""}
      <button class="primary" id="startteam">Start team</button></div>
    <div class="sub mono">${esc(d.path)}${d.server ? ` · ${esc(d.server)}:${esc(d.server_root)}` : " · no server set"}</div>

    <h2>Waiting on you (${d.waiting.length})</h2>
    <div class="card list">${d.waiting.map(waitingRow).join("") || `<div class="muted">Nothing.</div>`}</div>

    <h2>Agents (${d.agents.length})</h2>
    <div class="card">${d.herdr_error ? `<div class="err">herdr: ${esc(d.herdr_error)}</div>` : d.agents.length ? agentTable(d.agents) : `<div class="muted">No herdr agent is working in this folder.</div>`}</div>

    <h2>Open maps (${open.length})</h2>
    <div class="grid">${open.map(mapCard).join("") || `<div class="muted">No open map.</div>`}</div>

    <h2>Milestones (${closed.length})</h2>
    <div class="card">${closed.map((m) => `<div class="milestone"><a data-map="${esc(m.folder)}"><b>${esc(m.id)}</b> ${esc(m.title)}</a>
      <span class="muted"> · ${esc(m.updated || "")}</span><div class="outcome">${esc(m.outcome || "(no outcome recorded)")}</div></div>`).join("") || `<div class="muted">None yet.</div>`}</div>

    ${d.problems.length ? `<h2>Tracker warnings</h2><div class="card"><details><summary>${d.problems.length} warnings from <code>research-status --check</code></summary>
      <ul>${d.problems.map((p) => `<li class="mono">${esc(p)}</li>`).join("")}</ul></details></div>` : ""}
  </div>`;
  wireCommon($("#main"));
  $("#startteam").onclick = () => startFlow(null);
}

function waitingRow(w) {
  if (w.kind === "agent") return `<div class="item">${pill("blocked", "agent")}<span class="grow">${esc(w.text)}</span>
    <button class="small" data-focus="${esc(w.pane)}">Focus in herdr</button></div>`;
  const link = w.kind === "ticket" ? `<a data-map="${esc(w.map_folder)}" data-ticket="${esc(w.path.split("/").slice(-2, -1)[0])}">${esc(w.id)}</a>` : `<a data-map="${esc(w.map_folder)}">${esc(w.map)}</a>`;
  return `<div class="item">${pill("waiting", w.kind === "ticket" ? "ticket" : "map")}<span class="grow">${link} ${esc(w.text)}</span></div>`;
}

function agentTable(agents) {
  return `<table><tr><th>Role</th><th>Tab</th><th>Status</th><th>Doing</th><th></th></tr>${agents.map((a) => `<tr>
    <td>${esc(a.role || a.agent)}${a.map && a.map !== "-" ? `<div class="muted mono" style="font-size:11px">${esc(a.map)}</div>` : ""}</td>
    <td class="mono">${esc(a.tab_label || "")}<div class="muted" style="font-size:11px">${esc(a.workspace_label)} · ${esc(a.pane)}</div></td>
    <td>${pill(a.status)}</td><td>${esc(a.title || "")}</td>
    <td><button class="small" data-focus="${esc(a.pane)}">Focus in herdr</button></td></tr>`).join("")}</table>`;
}

const BAR_ORDER = [["resolved", "--s-resolved"], ["running", "--s-active"], ["claimed", "--s-active"], ["held", "--s-held"],
  ["open", "--s-open"], ["parked", "--s-parked"], ["superseded", "--s-parked"]];
function mapCard(m) {
  const total = m.tickets.length || 1;
  const bar = BAR_ORDER.map(([s, c]) => m.counts[s] ? `<span style="width:${100 * m.counts[s] / total}%;background:var(${c})" title="${m.counts[s]} ${s}"></span>` : "").join("");
  const live = ["open", "claimed"].includes(m.status);
  const why = m.status === "paused" ? (m.status_text || "").replace(/^paused\s*/, "") : "";
  return `<div class="card mapcard" data-map="${esc(m.folder)}">
    <div class="head"><span class="title">${esc(m.id)} · ${esc(m.title)}</span></div>
    <div>${pill(m.status)} ${m.driven ? pill("working", "driver live") : ""} <span class="muted">${esc(why)}</span></div>
    <div class="dest">${esc(m.destination)}</div>
    <div class="foot"><div class="bar">${bar}</div><span class="muted" style="font-size:12px">${m.tickets.length} tickets</span>
      ${live && !m.driven ? `<button class="small" data-startdriver="${esc(m.folder)}">Start driver</button>` : ""}</div>
  </div>`;
}

function wireCommon(root) {
  root.querySelectorAll("[data-map]").forEach((el) => el.onclick = (e) => {
    if (e.target.closest("button")) return;
    e.preventDefault();
    go({ project: S.route.project, map: el.dataset.map, tab: "dag", ticket: el.dataset.ticket || null });
  });
  root.querySelectorAll("[data-focus]").forEach((b) => b.onclick = async (e) => {
    e.stopPropagation();
    try { await post("/api/focus", { pane: b.dataset.focus }); toast("Focused in herdr"); } catch (err) { toast(err.message); }
  });
  root.querySelectorAll("[data-vs]").forEach((b) => b.onclick = (e) => { e.stopPropagation(); vscode(b.dataset.vs, b.dataset.path, !!b.dataset.dir); });
  root.querySelectorAll("[data-startdriver]").forEach((b) => b.onclick = (e) => { e.stopPropagation(); startFlow(b.dataset.startdriver); });
}

async function vscode(side, path, dir) {
  try { const r = await post("/api/vscode", { project: S.route.project, side, path, dir }); toast("Opened: " + r.cmd); }
  catch (e) { toast(e.message, 6000); }
}

// ---------- Start team / Start driver ----------

async function startFlow(mapFolder) {
  const m = $("#modal");
  m.hidden = false;
  m.innerHTML = `<div class="dlg">Planning…</div>`;
  m.onclick = (e) => { if (e.target === m) m.hidden = true; };
  let plan;
  try { plan = await get("/api/plan", { project: S.route.project, ...(mapFolder ? { map: mapFolder } : {}) }); }
  catch (e) { m.innerHTML = `<div class="dlg"><div class="err">${esc(e.message)}</div><div class="actions"><button id="mclose">Close</button></div></div>`; $("#mclose").onclick = () => m.hidden = true; return; }
  const ws = plan.workspace.id ? `herdr workspace <b>${esc(plan.workspace.label)}</b> (${esc(plan.workspace.id)})` : `a new herdr workspace <b>${esc(plan.workspace.label)}</b>`;
  m.innerHTML = `<div class="dlg">
    <h1 style="font-size:17px;margin:0 0 8px">${mapFolder ? "Start driver" : "Start team"}: ${esc(S.route.project)}</h1>
    ${plan.dry_run ? `<div class="note">Dry run: nothing will be sent to herdr.</div>` : ""}
    <div>${plan.steps.length ? `In ${ws}, one tab each:` : "Nothing to start."}</div>
    <ul>${plan.steps.map((s) => `<li><b>${esc(s.label)}</b>: claude as <code>${esc(s.name)}</code>, then <code>${esc(s.prompt)}</code>
      ${Object.keys(s.env).length ? `<span class="muted">env ${esc(Object.entries(s.env).map(([k, v]) => `${k}=${v}`).join(" "))}</span>` : ""}</li>`).join("")}</ul>
    ${plan.notes.length ? `<ul class="muted">${plan.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}
    <details><summary>herdr commands</summary><pre>${esc(plan.commands.join("\n"))}</pre></details>
    <pre id="joblog" hidden></pre>
    <div class="actions"><span style="flex:1"></span><button id="mclose">Close</button>
      ${plan.steps.length ? `<button class="primary" id="mgo">${plan.dry_run ? "Dry run" : "Start"}</button>` : ""}</div></div>`;
  $("#mclose").onclick = () => m.hidden = true;
  if ($("#mgo")) $("#mgo").onclick = async () => {
    $("#mgo").disabled = true;
    const log = $("#joblog");
    log.hidden = false;
    try {
      const { job } = await post("/api/start", { project: S.route.project, map: mapFolder });
      for (;;) {
        const j = await get("/api/job", { id: job });
        log.textContent = j.log.join("\n") || "…";
        if (j.done) { log.textContent += j.ok ? "\n\ndone" : "\n\nstopped (see above)"; break; }
        await new Promise((r) => setTimeout(r, 1000));
      }
      poll();
    } catch (e) { log.textContent = e.message; }
  };
}

// ---------- map page ----------

const curMap = () => S.data && S.data.maps.find((m) => m.folder === S.route.map);

function renderMapPage(dagOnly) {
  const m = curMap();
  if (!m) { $("#main").innerHTML = `<div class="page"><div class="err">No map ${esc(S.route.map)} in ${esc(S.route.project)}.</div></div>`; return; }
  if (dagOnly && $("#dag")) { drawDag(m, true); if (S.route.ticket) renderTicketPanel(m); renderMapHead(); return; }
  const tab = S.route.tab;
  $("#main").innerHTML = `<div class="page wide">
    <div id="maphead"></div>
    <div class="tabs">${[["dag", "DAG"], ["map", "Map"], ["files", "Files"]].map(([k, l]) =>
      `<a class="${tab === k ? "on" : ""}" data-tab="${k}">${l}</a>`).join("")}<span class="grow"></span></div>
    <div class="tabbody" id="tabbody"></div></div>`;
  $("#main").querySelectorAll("[data-tab]").forEach((a) => a.onclick = () => go({ ...S.route, tab: a.dataset.tab }));
  renderMapHead();
  if (tab === "dag") {
    $("#tabbody").innerHTML = `<div class="dagwrap" id="dag"></div><div class="panel" id="tpanel" hidden></div>`;
    renderTicketPanel(m);   // first, so the graph is fitted to the width the panel leaves
    drawDag(m, !!S.dagView);
  } else if (tab === "map") {
    $("#tabbody").innerHTML = `<div class="viewer" id="mapdoc"><div class="muted">Loading…</div></div>`;
    showDoc($("#mapdoc"), "local", m.path, { bare: true });
  } else {
    renderFiles(m);
  }
}

function renderMapHead() {
  const m = curMap(), el = $("#maphead");
  if (!m || !el) return;
  const live = ["open", "claimed"].includes(m.status);
  el.innerHTML = `<div class="crumbs"><a href="#/${encodeURIComponent(S.route.project)}">${esc(S.route.project)}</a> / ${esc(m.id)}</div>
    <div class="head"><h1>${esc(m.id)} · ${esc(m.title)}</h1>${pill(m.status, m.status_text && m.status !== "open" ? m.status_text : m.status)}
      ${m.driven ? pill("working", "driver live") : ""}<span class="grow"></span>
      ${live && !m.driven ? `<button class="small primary" data-startdriver="${esc(m.folder)}">Start driver</button>` : ""}</div>
    <div class="sub">${esc(m.status === "closed" ? "Outcome: " + (m.outcome || "") : m.destination)}</div>`;
  wireCommon(el);
}

// ---------- DAG ----------

const NODE_W = 230, NODE_H = 58;
function dagModel(m) {
  const g = new dagre.graphlib.Graph({ multigraph: true });
  g.setGraph({ rankdir: "LR", nodesep: 16, ranksep: 46, marginx: 30, marginy: 30 });
  g.setDefaultEdgeLabel(() => ({}));
  const shown = m.tickets.filter((t) => S.showClosed || !["parked", "superseded"].includes(t.status));
  const ids = new Set(shown.map((t) => t.id));
  const all = new Map(S.data.maps.flatMap((mm) => mm.tickets.map((t) => [t.id, { t, map: mm }])));
  shown.forEach((t) => g.setNode(t.id, { width: NODE_W, height: NODE_H, kind: "ticket", t }));
  const hasOut = new Set();
  shown.forEach((t) => t.blocked_by.forEach((b) => {
    if (!ids.has(b)) {
      const other = all.get(b);
      if (other && other.map.folder === m.folder && !S.showClosed) return;   // a hidden parked/superseded blocker
      g.setNode(b, { width: NODE_W, height: 44, kind: "ext", ref: b, other });
    }
    g.setEdge(b, t.id, { cls: "" });
    hasOut.add(b);
  }));
  if (S.showClosed) shown.forEach((t) => {
    if (t.status === "superseded" && t.superseded_by && ids.has(t.superseded_by)) { g.setEdge(t.id, t.superseded_by, { cls: "dashed" }); hasOut.add(t.id); }
  });
  g.setNode("__dest", { width: 250, height: 70, kind: "dest" });
  shown.filter((t) => !hasOut.has(t.id) && !["parked", "superseded"].includes(t.status)).forEach((t) => g.setEdge(t.id, "__dest", { cls: "dashed" }));
  m.fog.forEach((f, i) => { g.setNode("__fog" + i, { width: 200, height: 44, kind: "fog", text: f }); g.setEdge("__fog" + i, "__dest", { cls: "dashed" }); });
  dagre.layout(g);
  return g;
}

function nodeHtml(n, m) {
  if (n.kind === "dest") return `<div class="box"><div class="nid">Destination</div><div class="ttl" title="${esc(m.destination)}">${esc(m.destination)}</div></div>`;
  if (n.kind === "fog") return `<div class="box" title="Not yet specified: ${esc(n.text)}"><div class="ttl">${esc(n.text)}</div></div>`;
  if (n.kind === "ext") return `<div class="box"><div class="nid">${esc(n.ref)} <span class="t">${n.other ? "in " + esc(n.other.map.id) : "unknown ticket"}</span></div>
    <div class="ttl">${esc(n.other ? n.other.t.title : "")}</div></div>`;
  const t = n.t, ready = t.frontier;   // the tracker's frontier: open, unblocked, unclaimed, map not paused
  const color = { open: "--s-open", claimed: "--s-active", running: "--s-active", held: "--s-held", resolved: "--s-resolved" }[t.status] || "--s-parked";
  return `<div class="box" style="border-left-color:var(${color})" title="${esc(t.title)}">
    <div class="nid">${esc(t.id)} <span class="t">${esc(t.type || "")}</span><span style="flex:1"></span>
      <span class="${STATUS_CLASS(t.status)}${ACTIVE.has(t.status) ? " pulse" : ""}" style="font-weight:500">${esc(t.waiting ? "needs you" : ready ? "ready" : t.status === "open" ? (t.unblocked ? "open" : "blocked") : t.status)}</span></div>
    <div class="ttl">${esc(t.title)}</div></div>`;
}

function drawDag(m, keepView) {
  const wrap = $("#dag");
  const g = dagModel(m);
  const gw = g.graph().width || 400, gh = g.graph().height || 300;
  const edges = g.edges().map((e) => {
    const pts = g.edge(e).points, cls = g.edge(e).cls;
    let d = `M${pts[0].x},${pts[0].y}`;
    for (let i = 1; i < pts.length - 1; i++) {
      const mx = (pts[i].x + pts[i + 1].x) / 2, my = (pts[i].y + pts[i + 1].y) / 2;
      d += ` Q${pts[i].x},${pts[i].y} ${i === pts.length - 2 ? pts[i + 1].x : mx},${i === pts.length - 2 ? pts[i + 1].y : my}`;
    }
    if (pts.length === 2) d += ` L${pts[1].x},${pts[1].y}`;
    return `<path class="edge ${cls}" d="${d}" marker-end="url(#arrow)"/>`;
  }).join("");
  const nodes = g.nodes().map((id) => {
    const n = g.node(id);
    const cls = n.kind === "ticket" ? [n.t.status, n.t.waiting ? "waiting" : "", n.t.folder === S.route.ticket ? "sel" : ""].join(" ") : n.kind;
    return `<g class="node ${cls}" data-id="${esc(id)}" transform="translate(${n.x - n.width / 2},${n.y - n.height / 2})">
      <foreignObject width="${n.width}" height="${n.height}">${nodeHtml(n, m)}</foreignObject></g>`;
  }).join("");
  const nClosed = m.tickets.filter((t) => ["parked", "superseded"].includes(t.status)).length;
  wrap.innerHTML = `<svg id="dagsvg"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="var(--muted)"/></marker></defs><g id="vp">${edges}${nodes}</g></svg>
    <div class="dagtools"><button class="small" id="fit">Fit</button>
      <label><input type="checkbox" id="showclosed" ${S.showClosed ? "checked" : ""}> parked / superseded (${nClosed})</label>
      <span class="muted">${m.tickets.length} tickets · ${m.fog.length} fog</span></div>
    <div class="legend"><span><i style="background:var(--s-open)"></i>open</span><span><i style="background:var(--s-active)"></i>claimed / running</span>
      <span><i style="background:var(--s-held)"></i>held</span><span><i style="background:var(--s-resolved)"></i>resolved</span>
      <span><i style="background:var(--s-parked)"></i>parked / superseded</span><span><i style="border:2px solid var(--s-waiting)"></i>needs you</span>
      <span><i style="border:1px dashed var(--muted)"></i>fog (not yet specified)</span></div>`;
  const svg = $("#dagsvg"), vp = $("#vp");
  const fit = () => {
    // whole graph when it fits at a readable size; else readable and anchored top-left (scroll or drag to see the rest)
    const W = wrap.clientWidth, H = wrap.clientHeight, k = Math.max(0.6, Math.min(1.1, W / gw, (H - 80) / gh));
    S.dagView = { k, x: Math.max(10, (W - gw * k) / 2), y: Math.max(44, (H - gh * k) / 2) };
    apply();
  };
  const apply = () => vp.setAttribute("transform", `translate(${S.dagView.x},${S.dagView.y}) scale(${S.dagView.k})`);
  if (keepView && S.dagView) apply(); else fit();
  $("#fit").onclick = fit;
  $("#showclosed").onchange = (e) => { S.showClosed = e.target.checked; drawDag(m, false); };
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    const r = svg.getBoundingClientRect(), px = e.clientX - r.left, py = e.clientY - r.top, v = S.dagView;
    if (!e.ctrlKey && !e.metaKey) { v.x -= e.deltaX; v.y -= e.deltaY; return apply(); }   // scroll pans; pinch or ⌘-scroll zooms
    const f = Math.exp(-e.deltaY * 0.01), k = Math.max(0.15, Math.min(3, v.k * f));
    v.x = px - (px - v.x) * (k / v.k); v.y = py - (py - v.y) * (k / v.k); v.k = k;
    apply();
  }, { passive: false });
  let drag = null;
  svg.onpointerdown = (e) => { if (e.target.closest(".node")) return; drag = { x: e.clientX, y: e.clientY, vx: S.dagView.x, vy: S.dagView.y }; svg.classList.add("drag"); svg.setPointerCapture(e.pointerId); };
  svg.onpointermove = (e) => { if (!drag) return; S.dagView.x = drag.vx + e.clientX - drag.x; S.dagView.y = drag.vy + e.clientY - drag.y; apply(); };
  svg.onpointerup = () => { drag = null; svg.classList.remove("drag"); };
  svg.querySelectorAll(".node").forEach((el) => el.onclick = () => {
    const n = g.node(el.dataset.id);
    if (n.kind === "ticket") go({ ...S.route, tab: "dag", ticket: n.t.folder });
    else if (n.kind === "ext" && n.other) go({ project: S.route.project, map: n.other.map.folder, tab: "dag", ticket: n.other.t.folder });
    else if (n.kind === "dest" || n.kind === "fog") go({ ...S.route, tab: "map", ticket: null });
  });
}

// ---------- ticket panel ----------

function renderTicketPanel(m) {
  const panel = $("#tpanel");
  if (!panel) return;
  const t = m.tickets.find((x) => x.folder === S.route.ticket);
  if (!t) { panel.hidden = true; return; }
  panel.hidden = false;
  if (panel.dataset.ticket === t.path && panel.dataset.status === t.status_text) return;
  panel.dataset.ticket = t.path; panel.dataset.status = t.status_text;
  const d = S.data, dir = t.path.replace(/\/ticket\.md$/, "");
  panel.innerHTML = `<button class="small close" id="tclose">✕</button>
    <div class="nid muted mono">${esc(t.id)} · ${esc(t.type || "")}</div>
    <div class="actions">
      <button class="small" id="tfiles">Files</button>
      <button class="small" data-vs="local" data-path="${esc(dir)}" data-dir="1">VS Code · Mac</button>
      ${d.server ? `<button class="small" data-vs="server" data-path="${esc(serverMapDir(m) + "/tickets/" + t.folder)}" data-dir="1">VS Code · ${esc(d.server)}</button>` : ""}
    </div><div id="tdoc"><div class="muted">Loading…</div></div>`;
  $("#tclose").onclick = () => go({ ...S.route, ticket: null });
  $("#tfiles").onclick = () => { S.filesFocus = "tickets/" + t.folder; go({ ...S.route, tab: "files" }); };
  wireCommon(panel);
  showDoc($("#tdoc"), "local", t.path, { bare: true });
}

const serverMapDir = (m) => `${S.data.server_maps}/${m.folder}`;
const localMapDir = (m) => m.path.replace(/\/(map|track)\.md$/, "");

// ---------- files ----------

function treeRoots(m) {
  const d = S.data, roots = [];
  if (S.scope === "map") {
    roots.push({ key: "L", side: "local", root: localMapDir(m), label: "Records · Mac", sub: localMapDir(m) });
    if (d.server) {
      roots.push({ key: "R", side: "server", root: serverMapDir(m), label: `Code · ${d.server}`, sub: serverMapDir(m) });
      d.shared.forEach((s, i) => roots.push({ key: "S" + i, side: "server", root: s, label: `Shared · ${d.server}`, sub: s }));
    }
  } else {
    roots.push({ key: "L", side: "local", root: "", label: "Project · Mac", sub: d.path });
    if (d.server) roots.push({ key: "R", side: "server", root: "", label: `Project · ${d.server}`, sub: d.server_root });
  }
  return roots;
}

function renderFiles(m) {
  $("#tabbody").innerHTML = `<div class="files"><div class="trees" id="trees"></div><div class="viewer" id="viewer"></div></div>`;
  const roots = treeRoots(m);
  $("#trees").innerHTML = `<div class="scope">Show
      <button class="small ${S.scope === "map" ? "primary" : ""}" data-scope="map">this map</button>
      <button class="small ${S.scope === "project" ? "primary" : ""}" data-scope="project">whole project</button></div>`
    + (S.data.server ? "" : `<div class="terr">No server set for this project in projects.toml.</div>`)
    + roots.map((r) => `<div class="tree" id="tree-${r.key}"></div>`).join("");
  $("#trees").querySelectorAll("[data-scope]").forEach((b) => b.onclick = () => { S.scope = b.dataset.scope; S.trees = {}; renderFiles(m); });
  roots.forEach((r) => {
    const key = `${S.scope}:${r.key}`;
    if (!S.trees[key]) S.trees[key] = { ...r, nodes: { [r.root]: { open: true } } };
    const tr = S.trees[key];
    drawTree(tr);
    loadDir(tr, r.root, false);
  });
  if (S.filesFocus && S.scope === "map") {
    const f = S.filesFocus;
    S.filesFocus = null;
    roots.filter((r) => r.key === "L" || r.key === "R").forEach((r) => expandTo(S.trees[`${S.scope}:${r.key}`], `${r.root}/${f}`));
  }
  renderViewer();
}

async function loadDir(tr, path, fresh) {
  const n = tr.nodes[path] || (tr.nodes[path] = {});
  if (n.entries && !fresh) return drawTree(tr);
  n.loading = true; drawTree(tr);
  try {
    const j = await get("/api/tree", { project: S.route.project, side: tr.side, path, ...(fresh ? { fresh: 1 } : {}) });
    n.entries = j.entries.sort((a, b) => (b.dir - a.dir) || a.name.localeCompare(b.name)); n.error = null;
  } catch (e) { n.error = e.message; n.entries = null; }
  n.loading = false;
  drawTree(tr);
}

async function expandTo(tr, path) {
  const parts = path.split("/").filter(Boolean);
  let cur = tr.root;
  const rootParts = tr.root.split("/").filter(Boolean).length;
  for (const p of parts.slice(rootParts)) {
    await loadDir(tr, cur, false);
    cur = cur ? `${cur}/${p}` : p;
    (tr.nodes[cur] = tr.nodes[cur] || {}).open = true;
  }
  await loadDir(tr, cur, false);
  const ticket = tr.side === "local" ? `${cur}/ticket.md` : null;
  if (ticket && tr.nodes[cur].entries?.some((e) => e.name === "ticket.md")) openFile(tr.side, ticket);
}

function drawTree(tr) {
  const el = $(`#tree-${tr.key}`);
  if (!el) return;
  const rows = [];
  const walk = (path, depth) => {
    const n = tr.nodes[path] || {};
    if (n.loading && !n.entries) rows.push(`<div class="terr muted" style="padding-left:${24 + depth * 14}px">loading…</div>`);
    if (n.error) rows.push(`<div class="terr" style="padding-left:${24 + depth * 14}px">${esc(n.error)}</div>`);
    (n.entries || []).forEach((e) => {
      const p = path ? `${path}/${e.name}` : e.name, sub = tr.nodes[p], on = S.viewer && S.viewer.side === tr.side && S.viewer.path === p;
      rows.push(`<div class="trow ${on ? "on" : ""}" style="padding-left:${8 + depth * 14}px" data-p="${esc(p)}" data-dir="${e.dir ? 1 : ""}">
        <span class="caret">${e.dir ? (sub && sub.open ? "▾" : "▸") : ""}</span><span class="nm">${esc(e.name)}</span>
        <span class="sz">${e.dir ? "" : fmtSize(e.size)}</span><button class="small vs" title="Open in VS Code">⧉</button></div>`);
      if (e.dir && sub && sub.open) walk(p, depth + 1);
    });
  };
  walk(tr.root, 0);
  el.innerHTML = `<h3>${esc(tr.label)}<span class="grow mono" title="${esc(tr.sub)}">${esc(tr.sub)}</span>
    ${tr.side === "server" ? `<button class="small" data-refresh="1" title="Fetch again from the server">↻</button>` : ""}</h3>` + rows.join("");
  el.querySelectorAll(".trow").forEach((r) => r.onclick = (e) => {
    const p = r.dataset.p, isDir = !!r.dataset.dir;
    if (e.target.classList.contains("vs")) return vscode(tr.side, p, isDir);
    if (isDir) {
      const n = tr.nodes[p] || (tr.nodes[p] = {});
      n.open = !n.open;
      if (n.open) loadDir(tr, p, false); else drawTree(tr);
    } else openFile(tr.side, p);
  });
  const rb = el.querySelector("[data-refresh]");
  if (rb) rb.onclick = () => Object.keys(tr.nodes).filter((p) => tr.nodes[p].open || p === tr.root).forEach((p) => loadDir(tr, p, true));
}

function openFile(side, path) {
  S.viewer = { side, path };
  Object.values(S.trees).forEach(drawTree);
  renderViewer();
}

function renderViewer(fresh = false, mode = "") {
  const el = $("#viewer");
  if (!el) return;
  if (!S.viewer) { el.innerHTML = `<div class="muted" style="padding:20px">Pick a file on the left. Folders load when you open them; server files are read-only and cached until ↻.</div>`; return; }
  showDoc(el, S.viewer.side, S.viewer.path, { fresh, mode });
}

// ---------- rendering one file ----------

const LANG = { py: "python", sh: "bash", bash: "bash", zsh: "bash", js: "javascript", ts: "typescript", json: "json", jsonl: "json",
  yaml: "yaml", yml: "yaml", toml: "ini", cfg: "ini", ini: "ini", md: "markdown", c: "c", h: "c", cpp: "cpp", cu: "cpp",
  rs: "rust", go: "go", r: "r", sql: "sql", txt: "plaintext", html: "xml", xml: "xml", css: "css", slurm: "bash", sbatch: "bash" };

async function showDoc(el, side, path, opt = {}) {
  const name = path.split("/").pop();
  const head = opt.bare ? "" : `<div class="vhead"><span class="path mono" title="${esc(path)}">${esc(side === "local" ? "Mac" : S.data.server)} · ${esc(path)}</span>
    <span class="muted" id="vsize"></span><button class="small" id="vref">↻</button>
    <button class="small" id="vvs">VS Code</button></div>`;
  el.innerHTML = head + `<div class="muted">Loading…</div>`;
  if (!opt.bare) {
    $("#vref", el).onclick = () => showDoc(el, side, path, { ...opt, fresh: true });
    $("#vvs", el).onclick = () => vscode(side, path, false);
  }
  let f;
  try { f = await get("/api/file", { project: S.route.project, side, path, ...(opt.fresh ? { fresh: 1 } : {}), ...(opt.mode ? { mode: opt.mode } : {}) }); }
  catch (e) { el.innerHTML = head + `<div class="err">${esc(e.message)}</div>`; return; }
  if (!opt.bare && $("#vsize", el)) $("#vsize", el).textContent = fmtSize(f.size);
  const body = document.createElement("div");
  if (f.kind === "image") body.innerHTML = `<img src="data:${esc(f.mime)};base64,${f.data}" alt="${esc(name)}">`;
  else if (f.kind === "binary") body.innerHTML = `<div class="muted">Binary file, ${fmtSize(f.size)}.</div>`;
  else if (f.kind === "too-big") body.innerHTML = `<div class="muted">Image too large to show (${fmtSize(f.size)}).</div>`;
  else if (f.kind === "markdown") renderMarkdown(body, f.text, side, path);
  else if (f.kind === "csv") renderCsv(body, f.text, name.endsWith(".tsv") ? "\t" : ",");
  else {
    let text = f.text, lang = LANG[name.split(".").pop().toLowerCase()] || (f.kind === "log" ? "plaintext" : null);
    if (f.kind === "json" && name.endsWith(".json")) { try { text = JSON.stringify(JSON.parse(text), null, 2); } catch (_) { /* keep as is */ } }
    const code = document.createElement("code");
    code.textContent = text;
    if (lang && hljs.getLanguage(lang)) { code.className = "language-" + lang; if (text.length < 400000) hljs.highlightElement(code); }
    const pre = document.createElement("pre");
    pre.className = "code";
    pre.appendChild(code);
    body.appendChild(pre);
  }
  if (f.truncated) {
    const note = document.createElement("div");
    note.className = "note";
    note.innerHTML = f.tail ? `Showing the last lines only. <a>Load the whole file</a>` : `Large file: showing its beginning and end.`;
    if (f.tail) $("a", note).onclick = () => showDoc(el, side, path, { ...opt, mode: "full" });
    body.prepend(note);
  }
  el.innerHTML = head;
  if (!opt.bare) {
    $("#vref", el).onclick = () => showDoc(el, side, path, { ...opt, fresh: true });
    $("#vvs", el).onclick = () => vscode(side, path, false);
    $("#vsize", el).textContent = fmtSize(f.size);
  }
  el.appendChild(body);
}

function renderMarkdown(el, text, side, path) {
  let fm = "";
  const m = text.match(/^---\n([\s\S]*?)\n---\n?/);
  if (m) {
    text = text.slice(m[0].length);
    fm = `<table class="fm">${m[1].split("\n").filter((l) => /^[\w-]+:/.test(l)).map((l) => {
      const i = l.indexOf(":"), v = l.slice(i + 1).trim();
      return `<tr><td>${esc(l.slice(0, i))}</td><td>${esc(v.replace(/^"(.*)"$/, "$1"))}</td></tr>`;
    }).join("")}</table>`;
  }
  el.className = "md";
  // GFM strikes through ~single~ tildes; research notes use ~ for "about", so only ~~ strikes (code left alone)
  text = text.split(/(```[\s\S]*?```|`[^`\n]*`)/).map((seg, i) => i % 2 ? seg : seg.replace(/(^|[^~\\])~(?=[^~]|$)/g, "$1\\~")).join("");
  el.innerHTML = fm + DOMPurify.sanitize(marked.parse(text, { gfm: true }));
  el.querySelectorAll("pre code").forEach((c) => { if (c.textContent.length < 200000) hljs.highlightElement(c); });
  const dir = path.split("/").slice(0, -1).join("/");
  el.querySelectorAll("a[href]").forEach((a) => {
    const href = a.getAttribute("href");
    if (/^[a-z]+:/i.test(href) || href.startsWith("#")) { if (/^https?:/i.test(href)) a.target = "_blank"; return; }
    a.onclick = (e) => {
      e.preventDefault();
      const target = resolvePath(dir, href.split("#")[0]);
      const t = S.route.map && curMap()?.tickets.find((x) => x.path === target || x.path === target + "/ticket.md");
      if (t && side === "local") return go({ ...S.route, tab: "dag", ticket: t.folder });
      if (S.route.tab === "files") return openFile(side, target);
      S.viewer = { side, path: target };
      go({ ...S.route, tab: "files" });
    };
  });
}

function resolvePath(dir, rel) {
  const out = dir ? dir.split("/") : [];
  rel.split("/").forEach((p) => { if (p === "..") out.pop(); else if (p && p !== ".") out.push(p); });
  return out.join("/");
}

function parseCsv(text, sep) {
  const rows = [];
  let row = [], cell = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; } else cell += c; }
    else if (c === '"') q = true;
    else if (c === sep) { row.push(cell); cell = ""; }
    else if (c === "\n") { row.push(cell); rows.push(row); row = []; cell = ""; if (rows.length > 5000) break; }
    else if (c !== "\r") cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows;
}

function renderCsv(el, text, sep) {
  const rows = parseCsv(text, sep);
  if (!rows.length) { el.innerHTML = `<div class="muted">Empty.</div>`; return; }
  const head = rows[0];
  let body = rows.slice(1), sortCol = -1, asc = true;
  const draw = () => {
    el.innerHTML = `<div class="muted" style="font-size:12px">${body.length.toLocaleString()} rows${body.length > 2000 ? ", first 2,000 shown" : ""} · click a header to sort</div>
      <table class="csv"><tr>${head.map((h, i) => `<th data-i="${i}">${esc(h)}${i === sortCol ? (asc ? " ▲" : " ▼") : ""}</th>`).join("")}</tr>
      ${body.slice(0, 2000).map((r) => `<tr>${r.map((c) => `<td class="mono">${esc(c)}</td>`).join("")}</tr>`).join("")}</table>`;
    el.querySelectorAll("th").forEach((th) => th.onclick = () => {
      const i = +th.dataset.i;
      asc = sortCol === i ? !asc : true; sortCol = i;
      body = [...body].sort((a, b) => {
        const x = a[i] ?? "", y = b[i] ?? "", nx = parseFloat(x), ny = parseFloat(y);
        const c = !isNaN(nx) && !isNaN(ny) ? nx - ny : x.localeCompare(y);
        return asc ? c : -c;
      });
      draw();
    });
  };
  draw();
}

// ---------- start ----------

(async function init() {
  await loadProjects();
  await route();
  setInterval(poll, POLL_MS);
})();
