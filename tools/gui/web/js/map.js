// A map: its DAG of tickets (blocked_by edges, destination, fog), the ticket panel with skill actions, the map document,
// and its files.
import { S, $, esc, icon, pill, go, goMap, hooks, popMenu, toast, store, safeCls, agentLabel, AGENT_WORD } from "./core.js";
const workersOf = (m) => (S.data?.agents || []).filter((a) => a.role === "worker" && a.map_folder === m.folder);
const workerFor = (t) => (S.data?.agents || []).find((a) => a.role === "worker" && a.ticket === t.id);
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
    if (tab === "doc" && $("#map-root").dataset.mtime !== String(m.mtime)) {     // the map changed on disk: reread it
      $("#map-root").dataset.mtime = m.mtime;
      const doc = $("#mapdoc"), top = doc.scrollTop;
      showDoc(doc, "local", m.path, { quiet: true, onLink: (p, side) => linkTo(p, side) }).then(() => { doc.scrollTop = top; });
    }
    return;
  }
  host.innerHTML = `<div class="page full" id="map-root" data-map="${esc(m.folder)}" data-tab="${esc(tab)}" data-mtime="${esc(m.mtime)}"><div class="mhead" id="mhead"></div><div class="tabbody" id="tabbody"></div></div>`;
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
      <div style="margin-top:6px;color:var(--ink-2);font-size:12.5px;max-width:980px">${esc(m.status === "closed" ? "Outcome: " + (m.outcome || "") : m.destination)}</div>
      ${workersOf(m).length ? `<div class="actions" style="margin-top:8px"><span class="muted" style="font-size:12px">Workers</span>${workersOf(m).map((w) =>
        `<button class="btn sm" data-wpane="${esc(w.pane)}" title="${esc(w.ticket_title || "")} · ${esc(AGENT_WORD[w.status] || w.status)}"><span class="dot ${safeCls(w.status)}"></span>${esc(w.ticket)}</button>`).join("")}</div>` : ""}</div>
    <div class="actions">
      ${live && !m.driven ? `<button class="btn primary" id="mh-driver">${icon("play")} Start driver</button>` : ""}
      ${m.driver ? `<button class="btn primary" id="mh-driverchat" title="The driver owns this map: plan, re-chart and add questions with it">${icon("chat")} Talk to driver</button>` : ""}
      <button class="btn" id="mh-ticket">${icon("plus")} Add ticket</button>
      <button class="btn" id="mh-ask">${icon("chat")} ${esc(hooks.askLabel(S.route.project))}</button>
      <button class="btn icon" id="mh-more" title="More">${icon("more")}</button></div></div>
    <div class="tabs">${[["dag", "Graph"], ["doc", "Map"], ["files", "Files"]].map(([k, l]) => `<a class="${tab === k ? "on" : ""}" data-tab="${k}">${l}</a>`).join("")}</div>`;
  el.querySelectorAll("[data-tab]").forEach((a) => a.onclick = () => go({ ...S.route, tab: a.dataset.tab }));
  el.querySelectorAll("[data-wpane]").forEach((b) => b.onclick = () => hooks.openChat(b.dataset.wpane));
  if ($("#mh-driver")) $("#mh-driver").onclick = () => hooks.startTeam(S.route.project, m.folder);
  $("#mh-ticket").onclick = () => addTicket(m);
  if ($("#mh-driverchat")) $("#mh-driverchat").onclick = () => hooks.openChat(m.driver);
  $("#mh-ask").onclick = () => askDesk(`About map ${m.id} (${m.path}): `);
  $("#mh-more").onclick = (e) => popMenu(e.currentTarget, [
    { label: "Re-chart this map", icon: "map", run: () => m.driver ? hooks.openChat(m.driver, { text: "Re-chart this map: " })
      : hooks.newSession(S.route.project, "rechart", { map: localMapDir(m) }) },
    { label: "Run one research-drive pass", icon: "bolt", run: () => hooks.newSession(S.route.project, "drive", { map: localMapDir(m) }) },
    "-",
    m.status === "paused" ? { label: "Resume (tell the desk)", icon: "play", run: () => askDesk(`resume ${m.id}`) }
      : { label: hooks.deskPane(S.route.project) ? "Pause (tell the desk)" : "Pause…", icon: "stop", run: () => askDesk(`pause ${m.id}: `) },
    "-",
    { label: "Open map.md in VS Code", icon: "ext", run: () => vscode("local", m.path, false) },
    ...(S.data.server ? [{ label: `Terminal at its code on ${S.data.server}`, icon: "server", run: () => hooks.openTerminal({ kind: "ssh", project: S.route.project, path: serverMapDir(m), label: `ssh ${S.data.server}:${m.id}` }) }] : []),
  ], { right: true });
}

export function askDesk(text) { hooks.askProject(S.route.project, text); }

async function addTicket(m) {
  if (m.driver) return hooks.openChat(m.driver, { text: "New question for this map: " });   // the driver owns the map
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
  const t = n.t, w = workerFor(t);
  const word = w ? (w.status === "blocked" ? "worker needs you" : `worker ${AGENT_WORD[w.status] || w.status}`)
    : t.waiting ? "needs you" : t.frontier ? "ready" : t.status === "open" ? (t.unblocked ? "open" : "blocked") : t.status;
  const cls = w ? "s-" + safeCls(w.status === "blocked" ? "blocked" : "working") : t.waiting ? "s-blocked" : t.frontier ? "s-open" : "s-" + safeCls(t.status);
  return `<div class="box" style="--stripe:var(${STRIPE[t.status] || "--c-dim"})" title="${esc(t.title + (t.verdict ? "\n\nVerdict: " + t.verdict : ""))}">
    <div class="nid">${esc(t.id)} <span class="t">${esc(t.type || "")}</span><span class="st ${cls}" style="background:none">${esc(word)}</span></div>
    <div class="ttl">${esc(t.title)}</div></div>`;
}

function drawDag(m, keepView) {
  const wrap = $("#dag");
  if (!wrap) return;
  const g = model(m);
  const gw = g.graph().width || 400, gh = g.graph().height || 300;
  const selId0 = (m.tickets.find((t) => t.folder === S.route.ticket) || {}).id;
  const selId = selId0 && g.hasNode(selId0) ? selId0 : null;            // a hidden (parked) ticket has no node
  const near = new Set(selId ? [selId, ...g.predecessors(selId) || [], ...g.successors(selId) || []] : []);
  const edges = g.edges().map((e) => {
    const pts = g.edge(e).points, cls = g.edge(e).cls + (selId && (e.v === selId || e.w === selId) ? " near" : "");
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
    const cls = (n.kind === "ticket" ? [safeCls(n.t.status), n.t.waiting ? "waiting" : "", n.t.folder === S.route.ticket ? "sel" : ""].join(" ") : n.kind)
      + (selId && near.has(id) ? " near" : "");
    return `<g class="node ${cls}" data-id="${esc(id)}" transform="translate(${n.x - n.width / 2},${n.y - n.height / 2})">
      <foreignObject width="${n.width}" height="${n.height}">${nodeHtml(n, m)}</foreignObject></g>`;
  }).join("");
  const nClosed = m.tickets.filter((t) => ["parked", "superseded"].includes(t.status)).length;
  wrap.classList.toggle("focus", !!selId);
  wrap.innerHTML = `<svg id="dagsvg"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="var(--line-2)"/></marker></defs><g id="vp">${edges}${nodes}</g></svg>
    <div class="floatbar" style="top:12px;left:12px"><button class="btn ghost sm icon" id="zout" title="Zoom out">−</button>
      <button class="btn ghost sm icon" id="zin" title="Zoom in">+</button><button class="btn ghost sm" id="fit" title="Show the whole map">Fit</button>
      ${nClosed ? `<label><input type="checkbox" id="showclosed" ${M.showClosed ? "checked" : ""}> parked / superseded (${nClosed})</label>` : ""}
      <span class="muted">${m.tickets.length} tickets · ${m.fog.length} in fog</span></div>
    <div class="floatbar legend"><span><i style="background:var(--c-open)"></i>open</span><span><i style="background:var(--c-work)"></i>running</span>
      <span><i style="background:var(--c-held)"></i>held</span><span><i style="background:var(--c-ok)"></i>resolved</span>
      <span><i style="border:2px solid var(--c-alert)"></i>needs you</span><span><i style="border:1px dashed var(--muted)"></i>fog</span></div>`;
  const svg = $("#dagsvg"), vp = $("#vp");
  const apply = () => vp.setAttribute("transform", `translate(${M.view.x},${M.view.y}) scale(${M.view.k})`);
  const fit = (whole = false) => {
    // first view: the whole map if it stays readable, else readable from the top-left; Fit: the whole map, however small
    const W = wrap.clientWidth, H = wrap.clientHeight, all = Math.min(1.1, W / gw, (H - 90) / gh);
    const k = whole ? Math.max(0.15, all) : Math.max(0.6, all);
    M.view = { k, x: Math.max(10, (W - gw * k) / 2), y: Math.max(48, (H - gh * k) / 2) };
    apply();
  };
  if (keepView && M.view) apply(); else fit();
  $("#fit").onclick = () => fit(true);
  const zoom = (f) => { const W = wrap.clientWidth / 2, H = wrap.clientHeight / 2, v = M.view, k = Math.max(0.15, Math.min(3, v.k * f));
    v.x = W - (W - v.x) * (k / v.k); v.y = H - (H - v.y) * (k / v.k); v.k = k; apply(); };
  $("#zin").onclick = () => zoom(1.25);
  $("#zout").onclick = () => zoom(0.8);
  if (selId && M.lastSel !== selId) {                    // a newly selected ticket comes into view
    const n = g.node(selId), v = M.view, W = wrap.clientWidth, H = wrap.clientHeight;
    const sx = v.x + n.x * v.k, sy = v.y + n.y * v.k;
    if (sx < 40 || sx > W - 40 || sy < 60 || sy > H - 40) { v.x = W / 2 - n.x * v.k; v.y = H / 2 - n.y * v.k; apply(); }
  }
  M.lastSel = selId;
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

// ---------- jobs (free text in a ticket's jobs field, e.g. "tmux:T1-01 on pro5000-4, log logs/run.log") ----------

export function parseJob(text) {
  const session = (text.match(/tmux:([\w.:-]+)/) || [])[1];
  const host = (text.match(/\bon ([A-Za-z][\w.-]*)/) || [])[1];
  const logs = [...text.matchAll(/(?:^|[\s,(])((?:[\w.-]+\/)*[\w.-]+\.(?:log|out|err|txt))\b/g)].map((m) => m[1]).filter((p) => !p.includes("{"));
  return { session, host, logs, done: /^\s*(done|finished|killed|stopped)\b/i.test(text) };
}

function jobRow(text, i) {
  const j = parseJob(text);
  return `<div class="row" style="align-items:flex-start;flex-wrap:wrap"><div class="grow" style="min-width:220px"><div class="t2 mono" style="white-space:normal;color:var(--ink-2)">${esc(text)}</div></div>
    <div class="actions">${j.session && j.host ? `<button class="btn sm" data-peek="${i}" title="Read-only snapshot of the tmux pane">${icon("eye")} Peek</button>
      <button class="btn sm" data-attach="${i}" title="Attach to the tmux session in a terminal">${icon("term")} Attach</button>` : ""}
    ${j.logs.slice(0, 3).map((l) => `<button class="btn sm" data-log="${esc(l)}" title="Open on ${esc(S.data.server || "the server")}">${icon("file")} ${esc(l.split("/").pop())}</button>`).join("")}</div></div>`;
}

// ---------- ticket panel ----------

function renderTicket(m) {
  const panel = $("#tpanel");
  if (!panel) return;
  const t = m.tickets.find((x) => x.folder === S.route.ticket);
  if (!t) { panel.hidden = true; panel.dataset.key = ""; return; }
  panel.hidden = false;
  const wk = workerFor(t);
  // redraw when anything shown changes: the file (answer, assets, verdict), jobs, or the worker's state
  const key = [t.path, t.status_text, t.mtime, t.jobs.join(";"), wk ? wk.pane + wk.status + wk.title + (wk.codex || []).length : ""].join("|");
  if (panel.dataset.key === key) return;
  const keepTop = panel.dataset.path === t.path ? panel.scrollTop : 0;    // same ticket redrawn: stay where you were
  panel.dataset.key = key;
  panel.dataset.path = t.path;
  const dir = t.path.replace(/\/ticket\.md$/, ""), sdir = `${serverMapDir(m)}/tickets/${t.folder}`;
  const open = !["resolved", "parked", "superseded"].includes(t.status);
  panel.innerHTML = `<div class="panel-head"><div class="row1"><span class="mid">${esc(t.id)}</span>${pill(t.waiting ? "waiting" : t.status, t.waiting ? "needs you" : t.status)}
      <span class="pill plain">${esc(t.type || "")}</span><span class="grow"></span><button class="btn ghost sm icon" id="tp-close" title="Close">${icon("x")}</button></div>
    <h3>${esc(t.title)}</h3>
    ${t.verdict ? `<div class="verdict">${esc(t.verdict)}</div>` : ""}
    ${t.blocked_by.length ? `<div class="muted" style="font-size:12px;margin:-2px 0 8px">Blocked by ${t.blocked_by.map((b) => `<a data-goto="${esc(b)}" class="mono">${esc(b)}</a>`).join(", ")}</div>` : ""}
    <div class="actions">
      ${open && t.type !== "grilling" && !wk && !m.driven ? `<button class="btn sm primary" id="tp-work">${icon("play")} Work on it</button>` : ""}
      ${t.waiting ? `<button class="btn sm primary" id="tp-answer">${icon("chat")} ${hooks.deskPane(S.route.project) ? "Answer with the desk" : "Answer"}</button>` : ""}
      ${t.status === "resolved" ? `<button class="btn sm" id="tp-review">${icon("check")} Review</button>` : ""}
      <button class="btn sm" id="tp-ask">${icon("chat")} ${esc(hooks.askLabel(S.route.project))}</button>
      <button class="btn sm" id="tp-files">${icon("folder")} Files</button>
      <button class="btn sm icon" id="tp-more" title="More">${icon("more")}</button></div></div>
    ${wk ? `<div class="panel-body" style="padding-bottom:0"><div class="card rows"><div class="row">
      <span class="dot ${safeCls(wk.status)}"></span><div class="grow"><div class="t1">${esc(agentLabel(wk))} is ${esc(AGENT_WORD[wk.status] || wk.status)}</div>
      <div class="t2">${esc(wk.title || "")}</div></div>
      <button class="btn sm primary" id="tp-wchat">${icon("chat")} Open its chat</button><button class="btn sm" id="tp-wterm">${icon("term")} Terminal</button></div></div></div>` : ""}
    ${t.jobs.length ? `<div class="panel-body" style="padding-bottom:0"><div class="sec" style="margin:0 0 6px"><h2>Jobs</h2><span class="meta">from the ticket's jobs field</span></div>
      <div class="card rows">${t.jobs.map((j, i) => jobRow(j, i)).join("")}</div></div>` : ""}
    <div class="panel-body" id="tdoc"><div class="spin"></div></div>`;
  $("#tp-close").onclick = () => goMap(S.route.project, m.folder, null);
  panel.querySelectorAll("[data-goto]").forEach((a) => a.onclick = () => {
    const hit = S.data.maps.flatMap((mm) => mm.tickets.map((x) => [mm, x])).find(([, x]) => x.id === a.dataset.goto);
    if (hit) goMap(S.route.project, hit[0].folder, hit[1].folder);
  });
  if (wk) { $("#tp-wchat").onclick = () => hooks.openChat(wk.pane); $("#tp-wterm").onclick = () => hooks.openTerminal({ kind: "attach", pane: wk.pane, label: agentLabel(wk) }); }
  panel.querySelectorAll("[data-peek]").forEach((b) => b.onclick = () => { const j = parseJob(t.jobs[+b.dataset.peek]); hooks.peekJob(j.host, j.session); });
  panel.querySelectorAll("[data-attach]").forEach((b) => b.onclick = () => { const j = parseJob(t.jobs[+b.dataset.attach]);
    hooks.openTerminal({ kind: "tmux", host: j.host, session: j.session, label: `tmux ${j.session} @ ${j.host}` }); });
  panel.querySelectorAll("[data-log]").forEach((b) => b.onclick = () => hooks.openPath(S.route.project, b.dataset.log, "server"));
  if ($("#tp-work")) $("#tp-work").onclick = () => hooks.newSession(S.route.project, "work", { ticket: dir });
  if ($("#tp-answer")) $("#tp-answer").onclick = () => askDesk(`${t.id} (${t.path}): `);
  if ($("#tp-review")) $("#tp-review").onclick = () => hooks.newSession(S.route.project, "review", { ticket: dir });
  $("#tp-ask").onclick = () => askDesk(`About ${t.id} (${t.path}): `);
  $("#tp-files").onclick = () => { filesState.focus = "tickets/" + t.folder; filesState.scope = "map"; go({ ...S.route, tab: "files" }); };
  $("#tp-more").onclick = (e) => popMenu(e.currentTarget, [
    ...(hooks.deskPane(S.route.project) ? [{ header: "Tell the desk (you edit before sending)" },
      t.status === "held" ? { label: "Release", icon: "play", run: () => askDesk(`release ${t.id}`) } : { label: "Hold", icon: "stop", run: () => askDesk(`hold ${t.id}: `) },
      { label: "Reopen…", icon: "refresh", run: () => askDesk(`reopen ${t.id}: `) }, "-"] : []),
    { label: "Work on it in a new session", icon: "play", run: () => hooks.newSession(S.route.project, "work", { ticket: dir }) },
    { label: "Review in a new session", icon: "check", run: () => hooks.newSession(S.route.project, "review", { ticket: dir }) },
    "-",
    { label: "Open in VS Code (Mac)", icon: "ext", run: () => vscode("local", dir, true) },
    ...(S.data.server ? [{ label: `Open its code in VS Code (${S.data.server})`, icon: "ext", run: () => vscode("server", sdir, true) },
      { label: `Terminal in its code folder on ${S.data.server}`, icon: "server", run: () => hooks.openTerminal({ kind: "ssh", project: S.route.project, path: sdir, label: `ssh ${S.data.server}:${t.id}` }) }] : []),
    { label: "Copy ticket path", icon: "doc", run: () => navigator.clipboard.writeText(t.path).then(() => toast("Copied")) },
  ], { right: true });
  showDoc($("#tdoc"), "local", t.path, { bare: true, frontMatter: "details", dropTitle: true, skipKeys: ["id", "title", "type", "status", "legacy", "superseded_by", "verdict", "blocked_by", "jobs"], onLink: (p, side) => linkTo(p, side) }).then(() => { panel.scrollTop = keepTop; });
}

export { openFile, store };
