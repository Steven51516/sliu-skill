// A map: its DAG of tickets (blocked_by edges, destination, fog), the ticket panel with skill actions, the map document,
// and its files.
import { S, $, esc, icon, pill, go, goMap, hooks, popMenu, toast, store } from "./core.js";
import { renderFiles, showDoc, filesState, vscode, serverMapDir, localMapDir, openFile } from "./files.js";

const M = { showClosed: false, view: null };
export const curMap = () => S.data && S.data.maps.find((m) => m.folder === S.route.map);
export function resetMap() { M.view = null; }

export function renderMap(full) {
  const m = curMap(), host = $("#view");
  if (!m) { host.innerHTML = `<div class="empty big">No map ${esc(S.route.map)} in ${esc(S.route.project)}.</div>`; return; }
  const tab = S.route.tab;
  if (!full && $("#map-root") && $("#map-root").dataset.map === m.folder && $("#map-root").dataset.tab === tab) {
    renderHead(m);
    if (tab === "dag") { drawDag(m, true); renderTicket(m); }
    return;
  }
  host.innerHTML = `<div class="page full" id="map-root" data-map="${esc(m.folder)}" data-tab="${tab}"><div class="mhead" id="mhead"></div><div class="tabbody" id="tabbody"></div></div>`;
  renderHead(m);
  const body = $("#tabbody");
  if (tab === "dag") {
    body.innerHTML = `<div class="dagwrap" id="dag"></div><div class="panel" id="tpanel" hidden></div>`;
    renderTicket(m);
    drawDag(m, !!M.view);
  } else if (tab === "doc") {
    body.innerHTML = `<div class="viewer" id="mapdoc" style="padding:0"></div>`;
    showDoc($("#mapdoc"), "local", m.path, { onLink: (p, side) => linkTo(p, side) });
  } else renderFiles(body, m);
}

function linkTo(path, side) {
  const t = side === "local" && curMap()?.tickets.find((x) => x.path === path || x.path === path + "/ticket.md");
  if (t) return goMap(S.route.project, S.route.map, t.folder);
  filesState.viewer = { side, path };
  go({ ...S.route, tab: "files", ticket: null });
}

function renderHead(m) {
  const el = $("#mhead");
  if (!el) return;
  const live = ["open", "claimed"].includes(m.status);
  const tab = S.route.tab;
  const n = m.tickets.length, done = m.counts.resolved || 0, running = (m.counts.running || 0) + (m.counts.claimed || 0);
  const ready = m.tickets.filter((t) => t.frontier).length, waiting = m.tickets.filter((t) => t.waiting).length;
  el.innerHTML = `<div class="ph"><div class="grow"><h1>${esc(m.title)}</h1>
      <div class="sub"><span class="mono">${esc(m.id)}</span> · ${pill(m.driven ? "working" : m.status, m.driven ? "driver live" : m.status)}
        ${m.status === "paused" ? `<span class="muted">${esc((m.status_text || "").replace(/^paused\s*/, ""))}</span>` : ""}
        · ${done}/${n} resolved${running ? ` · ${running} running` : ""}${ready ? ` · ${ready} ready` : ""}${waiting ? ` · <span class="err">${waiting} need you</span>` : ""}</div>
      <div style="margin-top:6px;color:var(--ink-2);font-size:12.5px;max-width:980px">${esc(m.status === "closed" ? "Outcome: " + (m.outcome || "") : m.destination)}</div></div>
    <div class="actions">
      ${live && !m.driven ? `<button class="btn primary" id="mh-driver">${icon("play")} Start driver</button>` : ""}
      <button class="btn" id="mh-ticket">${icon("plus")} Add ticket</button>
      <button class="btn" id="mh-ask">${icon("chat")} Ask the desk</button>
      <button class="btn icon" id="mh-more" title="More">${icon("more")}</button></div></div>
    <div class="tabs">${[["dag", "Graph"], ["doc", "Map"], ["files", "Files"]].map(([k, l]) => `<a class="${tab === k ? "on" : ""}" data-tab="${k}">${l}</a>`).join("")}</div>`;
  el.querySelectorAll("[data-tab]").forEach((a) => a.onclick = () => go({ ...S.route, tab: a.dataset.tab }));
  if ($("#mh-driver")) $("#mh-driver").onclick = () => hooks.startTeam(S.route.project, m.folder);
  $("#mh-ticket").onclick = () => addTicket(m);
  $("#mh-ask").onclick = () => askDesk(`About map ${m.id} (${m.path}): `);
  $("#mh-more").onclick = (e) => popMenu(e.currentTarget, [
    { label: "Re-chart this map", icon: "map", run: () => hooks.newSession(S.route.project, "rechart", { map: localMapDir(m) }) },
    { label: "Run one research-drive pass", icon: "bolt", run: () => hooks.newSession(S.route.project, "drive", { map: localMapDir(m) }) },
    "-",
    m.status === "paused" ? { label: "Resume (tell the desk)", icon: "play", run: () => askDesk(`resume ${m.id}`) }
      : { label: "Pause (tell the desk)", icon: "stop", run: () => askDesk(`pause ${m.id}: `) },
    "-",
    { label: "Open map.md in VS Code", icon: "ext", run: () => vscode("local", m.path, false) },
    ...(S.data.server ? [{ label: `Terminal at its code on ${S.data.server}`, icon: "server", run: () => hooks.openTerminal({ kind: "ssh", project: S.route.project, path: serverMapDir(m), label: `ssh ${S.data.server}:${m.id}` }) }] : []),
  ], { right: true });
}

export function askDesk(text) {
  const desk = hooks.deskPane(S.route.project);
  if (!desk) return toast("No desk is running in this project: Start team first (or ask any session from the chat)", "err", 5000);
  hooks.openChat(desk, { text });
}

async function addTicket(m) {
  const desk = hooks.deskPane(S.route.project);
  if (desk) return hooks.openChat(desk, { text: `new (map ${m.id}): ` });
  hooks.newSession(S.route.project, "tickets", { map: localMapDir(m) });
}

// ---------- DAG ----------

const NODE_W = 236, NODE_H = 60;
function model(m) {
  const g = new dagre.graphlib.Graph({ multigraph: true });
  g.setGraph({ rankdir: "LR", nodesep: 14, ranksep: 54, marginx: 40, marginy: 40 });
  g.setDefaultEdgeLabel(() => ({}));
  const shown = m.tickets.filter((t) => M.showClosed || !["parked", "superseded"].includes(t.status));
  const ids = new Set(shown.map((t) => t.id));
  const all = new Map(S.data.maps.flatMap((mm) => mm.tickets.map((t) => [t.id, { t, map: mm }])));
  shown.forEach((t) => g.setNode(t.id, { width: NODE_W, height: NODE_H, kind: "ticket", t }));
  const hasOut = new Set();
  shown.forEach((t) => t.blocked_by.forEach((b) => {
    if (!ids.has(b)) {
      const other = all.get(b);
      if (other && other.map.folder === m.folder) return;      // a hidden parked/superseded blocker
      g.setNode(b, { width: NODE_W, height: 46, kind: "ext", ref: b, other });
    }
    g.setEdge(b, t.id, { cls: "" });
    hasOut.add(b);
  }));
  if (M.showClosed) shown.forEach((t) => {
    if (t.status === "superseded" && t.superseded_by && ids.has(t.superseded_by)) { g.setEdge(t.id, t.superseded_by, { cls: "dashed" }); hasOut.add(t.id); }
  });
  g.setNode("__dest", { width: 260, height: 74, kind: "dest" });
  shown.filter((t) => !hasOut.has(t.id) && !["parked", "superseded"].includes(t.status)).forEach((t) => g.setEdge(t.id, "__dest", { cls: "dashed" }));
  m.fog.forEach((f, i) => { g.setNode("__fog" + i, { width: 210, height: 44, kind: "fog", text: f }); g.setEdge("__fog" + i, "__dest", { cls: "dashed" }); });
  dagre.layout(g);
  return g;
}

const STRIPE = { open: "--c-open", claimed: "--c-work", running: "--c-work", held: "--c-held", resolved: "--c-ok" };
function nodeHtml(n, m) {
  if (n.kind === "dest") return `<div class="box"><div class="nid" style="font-family:var(--font)">◎ Destination</div><div class="ttl" title="${esc(m.destination)}">${esc(m.destination)}</div></div>`;
  if (n.kind === "fog") return `<div class="box" title="Not yet specified: ${esc(n.text)}"><div class="ttl">${esc(n.text)}</div></div>`;
  if (n.kind === "ext") return `<div class="box"><div class="nid">${esc(n.ref)} <span class="t">${n.other ? "in " + esc(n.other.map.id) : "unknown ticket"}</span></div>
    <div class="ttl">${esc(n.other ? n.other.t.title : "")}</div></div>`;
  const t = n.t;
  const word = t.waiting ? "needs you" : t.frontier ? "ready" : t.status === "open" ? (t.unblocked ? "open" : "blocked") : t.status;
  const cls = t.waiting ? "s-blocked" : t.frontier ? "s-open" : "s-" + t.status;
  return `<div class="box" style="--stripe:var(${STRIPE[t.status] || "--c-dim"})" title="${esc(t.title)}">
    <div class="nid">${esc(t.id)} <span class="t">${esc(t.type || "")}</span><span class="st ${cls}" style="background:none">${esc(word)}</span></div>
    <div class="ttl">${esc(t.title)}</div></div>`;
}

function drawDag(m, keepView) {
  const wrap = $("#dag");
  if (!wrap) return;
  const g = model(m);
  const gw = g.graph().width || 400, gh = g.graph().height || 300;
  const edges = g.edges().map((e) => {
    const pts = g.edge(e).points, cls = g.edge(e).cls;
    let d = `M${pts[0].x},${pts[0].y}`;
    for (let i = 1; i < pts.length - 1; i++) {
      const last = i === pts.length - 2, nx = last ? pts[i + 1].x : (pts[i].x + pts[i + 1].x) / 2, ny = last ? pts[i + 1].y : (pts[i].y + pts[i + 1].y) / 2;
      d += ` Q${pts[i].x},${pts[i].y} ${nx},${ny}`;
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
      <path d="M0,0 L10,5 L0,10 z" fill="var(--line-2)"/></marker></defs><g id="vp">${edges}${nodes}</g></svg>
    <div class="floatbar" style="top:12px;left:12px"><button class="btn ghost sm" id="fit">Fit</button>
      ${nClosed ? `<label><input type="checkbox" id="showclosed" ${M.showClosed ? "checked" : ""}> parked / superseded (${nClosed})</label>` : ""}
      <span class="muted">${m.tickets.length} tickets · ${m.fog.length} in fog</span></div>
    <div class="floatbar legend"><span><i style="background:var(--c-open)"></i>open</span><span><i style="background:var(--c-work)"></i>running</span>
      <span><i style="background:var(--c-held)"></i>held</span><span><i style="background:var(--c-ok)"></i>resolved</span>
      <span><i style="border:2px solid var(--c-alert)"></i>needs you</span><span><i style="border:1px dashed var(--muted)"></i>fog</span></div>`;
  const svg = $("#dagsvg"), vp = $("#vp");
  const apply = () => vp.setAttribute("transform", `translate(${M.view.x},${M.view.y}) scale(${M.view.k})`);
  const fit = () => {
    const W = wrap.clientWidth, H = wrap.clientHeight, k = Math.max(0.6, Math.min(1.1, W / gw, (H - 90) / gh));
    M.view = { k, x: Math.max(10, (W - gw * k) / 2), y: Math.max(48, (H - gh * k) / 2) };
    apply();
  };
  if (keepView && M.view) apply(); else fit();
  $("#fit").onclick = fit;
  if ($("#showclosed")) $("#showclosed").onchange = (e) => { M.showClosed = e.target.checked; drawDag(m, false); };
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    const r = svg.getBoundingClientRect(), px = e.clientX - r.left, py = e.clientY - r.top, v = M.view;
    if (!e.ctrlKey && !e.metaKey) { v.x -= e.deltaX; v.y -= e.deltaY; return apply(); }    // scroll pans; pinch or ⌘-scroll zooms
    const k = Math.max(0.15, Math.min(3, v.k * Math.exp(-e.deltaY * 0.01)));
    v.x = px - (px - v.x) * (k / v.k); v.y = py - (py - v.y) * (k / v.k); v.k = k;
    apply();
  }, { passive: false });
  let drag = null;
  svg.onpointerdown = (e) => { if (e.target.closest(".node")) return; drag = { x: e.clientX, y: e.clientY, vx: M.view.x, vy: M.view.y }; svg.classList.add("drag"); svg.setPointerCapture(e.pointerId); };
  svg.onpointermove = (e) => { if (!drag) return; M.view.x = drag.vx + e.clientX - drag.x; M.view.y = drag.vy + e.clientY - drag.y; apply(); };
  svg.onpointerup = () => { drag = null; svg.classList.remove("drag"); };
  svg.querySelectorAll(".node").forEach((el) => el.onclick = () => {
    const n = g.node(el.dataset.id);
    if (n.kind === "ticket") goMap(S.route.project, m.folder, n.t.folder === S.route.ticket ? null : n.t.folder);
    else if (n.kind === "ext" && n.other) goMap(S.route.project, n.other.map.folder, n.other.t.folder);
    else go({ ...S.route, tab: "doc", ticket: null });
  });
}

// ---------- ticket panel ----------

function renderTicket(m) {
  const panel = $("#tpanel");
  if (!panel) return;
  const t = m.tickets.find((x) => x.folder === S.route.ticket);
  if (!t) { panel.hidden = true; panel.dataset.key = ""; return; }
  panel.hidden = false;
  const key = t.path + "|" + t.status_text;
  if (panel.dataset.key === key) return;
  panel.dataset.key = key;
  const dir = t.path.replace(/\/ticket\.md$/, ""), sdir = `${serverMapDir(m)}/tickets/${t.folder}`;
  const open = !["resolved", "parked", "superseded"].includes(t.status);
  panel.innerHTML = `<div class="panel-head"><div class="row1"><span class="mid">${esc(t.id)}</span>${pill(t.waiting ? "waiting" : t.status, t.waiting ? "needs you" : t.status)}
      <span class="pill plain">${esc(t.type || "")}</span><span class="grow"></span><button class="btn ghost sm icon" id="tp-close" title="Close">${icon("x")}</button></div>
    <h3>${esc(t.title)}</h3>
    <div class="actions">
      ${open && t.type !== "grilling" ? `<button class="btn sm primary" id="tp-work">${icon("play")} Work on it</button>` : ""}
      ${t.waiting ? `<button class="btn sm primary" id="tp-answer">${icon("chat")} Answer with the desk</button>` : ""}
      ${t.status === "resolved" ? `<button class="btn sm" id="tp-review">${icon("check")} Review</button>` : ""}
      <button class="btn sm" id="tp-ask">${icon("chat")} Ask the desk</button>
      <button class="btn sm" id="tp-files">${icon("folder")} Files</button>
      <button class="btn sm icon" id="tp-more" title="More">${icon("more")}</button></div></div>
    <div class="panel-body" id="tdoc"><div class="spin"></div></div>`;
  $("#tp-close").onclick = () => goMap(S.route.project, m.folder, null);
  if ($("#tp-work")) $("#tp-work").onclick = () => hooks.newSession(S.route.project, "work", { ticket: dir });
  if ($("#tp-answer")) $("#tp-answer").onclick = () => askDesk(`${t.id} (${t.path}): `);
  if ($("#tp-review")) $("#tp-review").onclick = () => hooks.newSession(S.route.project, "review", { ticket: dir });
  $("#tp-ask").onclick = () => askDesk(`About ${t.id} (${t.path}): `);
  $("#tp-files").onclick = () => { filesState.focus = "tickets/" + t.folder; filesState.scope = "map"; go({ ...S.route, tab: "files" }); };
  $("#tp-more").onclick = (e) => popMenu(e.currentTarget, [
    { header: "Tell the desk (you edit before sending)" },
    t.status === "held" ? { label: "Release", icon: "play", run: () => askDesk(`release ${t.id}`) } : { label: "Hold", icon: "stop", run: () => askDesk(`hold ${t.id}: `) },
    { label: "Reopen…", icon: "refresh", run: () => askDesk(`reopen ${t.id}: `) },
    "-",
    { label: "Work on it in a new session", icon: "play", run: () => hooks.newSession(S.route.project, "work", { ticket: dir }) },
    { label: "Review in a new session", icon: "check", run: () => hooks.newSession(S.route.project, "review", { ticket: dir }) },
    "-",
    { label: "Open in VS Code (Mac)", icon: "ext", run: () => vscode("local", dir, true) },
    ...(S.data.server ? [{ label: `Open its code in VS Code (${S.data.server})`, icon: "ext", run: () => vscode("server", sdir, true) },
      { label: `Terminal in its code folder on ${S.data.server}`, icon: "server", run: () => hooks.openTerminal({ kind: "ssh", project: S.route.project, path: sdir, label: `ssh ${S.data.server}:${t.id}` }) }] : []),
    { label: "Copy ticket path", icon: "doc", run: () => navigator.clipboard.writeText(t.path).then(() => toast("Copied")) },
  ], { right: true });
  showDoc($("#tdoc"), "local", t.path, { bare: true, skipKeys: ["id", "title", "type", "status", "legacy", "superseded_by"], onLink: (p, side) => linkTo(p, side) });
}

export { openFile, store };
