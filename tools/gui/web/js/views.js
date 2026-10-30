// Pages: project overview, inbox, GPUs, settings, project files; and the title bar.
import { S, $, esc, get, post, toast, icon, pill, ago, go, goMap, href, hooks, agentLabel, avatar, allAgents, AGENT_WORD, popMenu, savePrefs, codexNote, fmtDur, loopNote, loopDead, store } from "./core.js";
import { renderFiles, vscode } from "./files.js";
import { renderMap, curMap } from "./map.js";

// ---------- title bar ----------

export function renderTitlebar() {
  const r = S.route, crumbs = [];
  if (r.view === "inbox") crumbs.push("Inbox");
  else if (r.view === "gpus") crumbs.push("GPUs");
  else if (r.view === "settings") crumbs.push("Settings");
  else if (r.project) {
    crumbs.push(r.view === "project" ? esc(r.project) : `<a href="${href({ project: r.project })}">${esc(r.project)}</a>`);
    if (r.view === "files") crumbs.push("Files");
    if (r.view === "map") { const m = curMap(); crumbs.push(m ? `<span class="cur">${esc(m.id)} · ${esc(m.title)}</span>` : esc(r.map)); }
  }
  const unread = S.unread.size;
  $("#titlebar").innerHTML = `<div class="crumbs">${crumbs.map((c, i) => (i ? `<span class="sep">/</span>` : "") + `<span class="${i === crumbs.length - 1 ? "cur" : ""}">${c}</span>`).join("")}</div>
    <span class="grow"></span>
    <button class="btn ghost sm icon" id="tb-term" title="Terminals (⌃\`)">${icon("bottom")}</button>
    <button class="btn ${S.chat.open ? "" : "ghost"} sm" id="tb-chat" title="Chat (⌘J)">${icon("chat")} Chat${unread ? ` <span class="count alert">${unread}</span>` : ""}</button>`;
  $("#tb-term").onclick = () => hooks.toggleDock();
  $("#tb-chat").onclick = () => hooks.toggleChat();
}

// ---------- project overview ----------

export function renderOverview() {
  const d = S.data, host = $("#view");
  if (!d) { host.innerHTML = `<div class="empty big"><div class="spin"></div></div>`; return; }
  const open = d.maps.filter((m) => m.status !== "closed"), closed = d.maps.filter((m) => m.status === "closed").reverse();
  const tickets = d.maps.flatMap((m) => m.tickets.map((t) => ({ ...t, map: m })));
  const running = tickets.filter((t) => ["running", "claimed"].includes(t.status)), ready = tickets.filter((t) => t.frontier);
  const desk = d.agents.find((a) => a.role === "desk");
  const working = d.agents.filter((a) => a.status === "working").length;
  const ch = d.changes;
  host.innerHTML = `<div class="page">
    <div class="ph"><div class="grow"><h1>${esc(d.name)}</h1><div class="sub mono">${esc(d.path.replace(/^\/Users\/[^/]+/, "~"))}${d.server ? ` · ${esc(d.server)}:${esc(d.server_root)}` : ""}</div></div>
      <div class="actions">
        ${d.team ? (desk ? `<button class="btn primary" id="ov-desk">${icon("chat")} Talk to the desk</button>` : `<button class="btn primary" id="ov-team">${icon("users")} Start team</button>`)
          : `<button class="btn primary" id="ov-new">${icon("plus")} New session</button>${d.agents.length ? `<button class="btn" id="ov-ask">${icon("chat")} Ask Claude</button>` : ""}`}
        ${d.team && desk && open.some((m) => ["open", "claimed"].includes(m.status) && !m.driven) ? `<button class="btn" id="ov-team">${icon("users")} Start drivers</button>` : ""}
        ${d.team ? `<button class="btn" id="ov-new">${icon("plus")} New session</button>` : ""}
        ${d.maps.length || d.team ? `<button class="btn" id="ov-idea">${icon("spark")} New map from an idea</button>` : ""}
        <button class="btn icon" id="ov-more" title="More">${icon("more")}</button></div></div>
    <div class="statline">
      ${statChip(d.waiting.length, "need you", "alert")}${statChip(running.length, "running", "work")}${statChip(ready.length, "ready", "open")}
      ${statChip(open.length, "open maps", "")}${statChip(`${working}/${d.agents.length}`, "agents working", working ? "work" : "")}</div>
    <div class="cols" style="margin-top:6px"><div>
      ${d.waiting.length ? `<div class="sec"><h2>Needs you</h2></div><div class="card rows">${d.waiting.map(waitingRow).join("")}</div>` : ""}
      ${ch.since && ch.items.length ? changesBlock(ch, tickets) : ""}
      ${running.length ? `<div class="sec"><h2>Running</h2></div><div class="card rows">${running.map((t) => `<div class="row click" data-map="${esc(t.map.folder)}" data-ticket="${esc(t.folder)}">
          <span class="mono muted">${esc(t.id)}</span><div class="grow"><div class="t1">${esc(t.title)}</div>${t.jobs.length ? `<div class="t2 mono">${esc(t.jobs.slice(-2).join(" · "))}</div>` : ""}</div>${pill(t.status)}</div>`).join("")}</div>` : ""}
      <div class="sec"><h2>Maps</h2><span class="meta">${open.length} open · ${closed.length} closed</span></div>
      <div class="grid">${open.map(mapCard).join("") || `<div class="card empty">No open map. Chart one with “New map from an idea”.</div>`}</div>
    </div><div>
      <div class="sec"><h2>${d.team ? "Team" : "Sessions"}</h2><span class="meta">${d.herdr_error ? `<span class="err">herdr: ${esc(d.herdr_error)}</span>` : ""}</span></div>
      <div class="card rows">${teamRows(d.agents) || `<div class="empty">Nobody is working here. <a id="ov-team2">Start the team</a> or open a new session.</div>`}</div>
      <div class="sec"><h2>GPUs</h2><span class="grow"></span><a href="#/gpus" class="meta">every node</a></div><div class="card pad" id="ov-gpus">${gpuCache.all || `<div class="spin"></div>`}</div>
      <div class="sec" id="milestones"><h2>Milestones</h2><span class="meta">closed maps</span></div>
      <div class="card pad"><div class="timeline">${closed.map((m) => `<div class="tl" data-map="${esc(m.folder)}"><div class="h"><span class="mid">${esc(m.id)}</span>${esc(m.title)}</div>
        <div class="d">${esc(m.updated || "")}</div><div class="o">${esc(plain(m.outcome) || "(no outcome recorded)")}</div></div>`).join("") || `<div class="muted">None yet.</div>`}</div></div>
      ${d.problems.length ? `<div class="sec"><h2>Tracker warnings</h2></div><div class="card pad"><details><summary>${d.problems.length} from <code>research-status --check</code></summary>
        <ul style="padding-left:18px;font-size:12px">${d.problems.map((p) => `<li class="mono">${esc(p)}</li>`).join("")}</ul></details></div>` : ""}
    </div></div></div>`;
  wire(host);
  const team = () => hooks.startTeam(d.name);
  if ($("#ov-desk")) $("#ov-desk").onclick = () => hooks.openChat(desk.pane);
  if ($("#ov-team")) $("#ov-team").onclick = team;
  if ($("#ov-team2")) $("#ov-team2").onclick = team;
  $("#ov-new").onclick = () => hooks.newSession(d.name);
  if ($("#ov-idea")) $("#ov-idea").onclick = () => hooks.newSession(d.name, "wayfinder");
  if ($("#ov-ask")) $("#ov-ask").onclick = () => hooks.askProject(d.name);
  host.querySelectorAll("[data-restart]").forEach((b) => b.onclick = (e) => { e.stopPropagation(); restartLoop(b.dataset.restart); });
  if ($("#ov-seen")) $("#ov-seen").onclick = () => post("/api/seen", { project: d.name }).then(() => hooks.refresh());
  $("#ov-more").onclick = (e) => popMenu(e.currentTarget, [
    ...(desk ? [{ label: "Ask the desk for a digest", icon: "doc", run: () => hooks.openChat(desk.pane, { text: "digest" }) }, "-"] : []),
    ...(!d.team && d.maps.length ? [{ label: "Start a team (desk and drivers)", icon: "users", run: () => hooks.startTeam(d.name) }, "-"] : []),
    { label: "Search conversations", icon: "search", run: () => go({ project: d.name, view: "search" }) },
    { label: "Shell in this project", icon: "term", run: () => hooks.openTerminal({ kind: "shell", project: d.name }) },
    ...(d.server ? [{ label: `SSH to ${d.server}`, icon: "server", run: () => hooks.openTerminal({ kind: "ssh", project: d.name, server: d.server, label: `ssh ${d.server}` }) }] : []),
    "-",
    { label: "Open in VS Code (Mac)", icon: "ext", run: () => vscode("local", "", true) },
    ...(d.server ? [{ label: `Open in VS Code (${d.server})`, icon: "ext", run: () => vscode("server", "", true) }] : []),
    { label: "Reveal in Finder", icon: "folder", run: () => post("/api/reveal", { project: d.name, path: "" }) },
    "-",
    { label: "Mark everything as seen", icon: "check", run: () => post("/api/seen", { project: d.name }).then(() => hooks.refresh()) },
  ], { right: true });
  if (!ch.since) post("/api/seen", { project: d.name }).catch(() => {});   // first visit: start tracking from now
  loadMiniGpus();
}

function changesBlock(ch, tickets) {
  const byId = new Map(tickets.map((t) => [t.id, t]));
  const results = ch.items.filter((c) => !c.is_map && c.to === "resolved");
  const rest = ch.items.filter((c) => !results.includes(c));
  const row = (c) => `<div class="change"><a data-map="${esc(c.map_folder)}" data-ticket="${esc(c.folder || "")}" class="mono">${esc(c.id)}</a>
    <span class="grow" style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.title)}</span>
    ${c.from ? pill(c.from) : `<span class="pill plain">new</span>`}<span class="arrow">→</span>${pill(c.to)}</div>`;
  return `<div class="sec"><h2>${results.length ? "New results" : "Since you last looked"}</h2><span class="meta">since ${esc(ago(ch.since))}</span><span class="grow"></span>
      <button class="btn sm" id="ov-seen">${icon("check")} Mark as seen</button></div>
    ${results.length ? `<div class="card rows">${results.map((c) => { const t = byId.get(c.id) || {};
      return `<div class="row click" data-map="${esc(c.map_folder)}" data-ticket="${esc(c.folder || "")}"><span class="mono muted">${esc(c.id)}</span>
        <div class="grow"><div class="t1">${esc(c.title)}</div><div class="t2">${esc(t.verdict || "resolved — open it for the answer")}</div></div>${pill("resolved")}</div>`; }).join("")}</div>` : ""}
    ${rest.length ? `<details class="card" style="padding:4px 0;margin-top:${results.length ? 8 : 0}px" ${results.length ? "" : "open"}>
      <summary class="muted" style="padding:6px 14px;font-size:12.5px">${rest.length} other change${rest.length > 1 ? "s" : ""}</summary>${rest.slice(0, 40).map(row).join("")}</details>` : ""}`;
}

// map destinations and outcomes are markdown; cards show them as plain text
const plain = (s) => String(s || "").replace(/`([^`]*)`/g, "$1").replace(/\*\*([^*]+)\*\*/g, "$1")
  .replace(/(^|[\s(])_+(?=\S)/g, "$1").replace(/(?<=\S)_+(?=[\s).,;:]|$)/g, "");

export async function restartLoop(pane) {
  const a = allAgents().find((x) => x.pane === pane);
  if (!a?.loop?.prompt) return toast("No loop command recorded for this session", "err");
  try { await post("/api/chat/send", { pane, text: a.loop.prompt }); toast(`Sent ${a.loop.prompt}`); hooks.refresh(); }
  catch (e) { toast(e.message, "err"); }
}

const statChip = (n, l, cls) => `<span class="schip ${n && n !== "0" && !String(n).startsWith("0/") ? cls : ""}"><b>${esc(n)}</b> ${esc(l)}</span>`;

function waitingRow(w) {
  if (w.kind === "agent") return `<div class="row click" data-pane="${esc(w.pane)}">${pill("blocked", "prompt")}<div class="grow"><div class="t1">${esc(w.text)}</div></div>
    <button class="btn sm primary" data-pane="${esc(w.pane)}">Answer</button></div>`;
  if (w.kind === "ticket") return `<div class="row click" data-map="${esc(w.map_folder)}" data-ticket="${esc(w.folder)}">${pill("waiting", "decision")}
    <div class="grow"><div class="t1">${esc(w.text)}</div><div class="t2 mono">${esc(w.id)}</div></div><button class="btn sm" data-open="1">Open</button></div>`;
  return `<div class="row click" data-map="${esc(w.map_folder)}">${pill("waiting", "map")}<div class="grow"><div class="t1">${esc(w.text)}</div><div class="t2 mono">${esc(w.map)}</div></div></div>`;
}

function agentRow(a, sub = false) {
  return `<div class="row click" data-pane="${esc(a.pane)}" style="${sub ? "padding-left:40px" : ""}">${avatar(a)}<div class="grow"><div class="t1">${esc(agentLabel(a))}</div>
    <div class="t2 ${loopDead(a) ? "err" : ""}">${esc(a.status === "blocked" ? "waiting for your answer" : [loopNote(a), codexNote(a), (a.role === "worker" ? a.ticket_title : "") || a.title].filter(Boolean).join(" · "))}</div></div>
    ${loopDead(a) && a.status !== "working" ? `<button class="btn sm primary" data-restart="${esc(a.pane)}" title="Send ${esc(a.loop.prompt)}">Restart loop</button>` : ""}${pill(a.status, a.codex?.length ? "Codex" : AGENT_WORD[a.status] || a.status)}
    <button class="btn ghost sm icon" data-term="${esc(a.pane)}" title="Open its terminal">${icon("term")}</button></div>`;
}
function teamRows(agents) {
  // desk, each driver followed by the workers it opened, then the rest
  const out = [], placed = new Set();
  agents.filter((a) => a.role === "desk").forEach((a) => { out.push(agentRow(a)); placed.add(a.pane); });
  agents.filter((a) => a.role === "driver").forEach((dr) => {
    out.push(agentRow(dr)); placed.add(dr.pane);
    agents.filter((w) => w.role === "worker" && w.driver === dr.pane).forEach((w) => { out.push(agentRow(w, true)); placed.add(w.pane); });
  });
  agents.filter((a) => !placed.has(a.pane)).forEach((a) => out.push(agentRow(a, a.role === "worker")));
  // Codex jobs no session here claims (codex-run detaches them): one row each, opening the run's folder
  (S.data?.codex || []).filter((r) => !r.pane).forEach((r) => out.push(`<div class="row click" data-run="${esc(r.run)}" title="${esc(r.run)}">
    <span class="avatar codex">X</span><div class="grow"><div class="t1">Codex · ${esc(r.name)}</div><div class="t2">${esc(r.ticket ? r.ticket + " · " : "")}running ${esc(fmtDur(r.seconds))}</div></div>${pill("working", "Codex")}</div>`));
  return out.join("");
}

const BAR = [["resolved", "--c-ok"], ["running", "--c-work"], ["claimed", "--c-work"], ["held", "--c-held"], ["open", "--c-open"], ["parked", "--c-dim"], ["superseded", "--c-dim"]];
function mapCard(m) {
  const total = m.tickets.length || 1;
  const bar = BAR.map(([s, c]) => m.counts[s] ? `<span style="width:${100 * m.counts[s] / total}%;background:var(${c})" title="${m.counts[s]} ${s}"></span>` : "").join("");
  const live = ["open", "claimed"].includes(m.status);
  const ready = m.tickets.filter((t) => t.frontier).length, waiting = m.tickets.filter((t) => t.waiting).length;
  return `<div class="card mapcard" data-map="${esc(m.folder)}">
    <div class="top"><span class="mid">${esc(m.id)}</span><span class="title">${esc(m.title)}</span></div>
    <div style="display:flex;gap:6px;flex-wrap:wrap">${pill(m.driven ? "working" : m.status, m.driven ? "driver live" : m.status)}
      ${waiting ? pill("waiting", `${waiting} need you`) : ""}${ready ? pill("open", `${ready} ready`) : ""}</div>
    <div class="dest">${esc(plain(m.destination))}</div>
    <div class="foot"><div class="bar">${bar}</div><span>${m.counts.resolved || 0}/${m.tickets.length}</span>
      ${live && !m.driven ? `<button class="btn sm" data-driver="${esc(m.folder)}">${icon("play")} Driver</button>` : ""}</div></div>`;
}

function wire(root) {
  root.querySelectorAll("[data-map]").forEach((el) => el.onclick = (e) => {
    const b = e.target.closest("button");
    if (b && !b.dataset.map && !b.dataset.open) return;
    e.preventDefault();
    goMap(S.route.project || el.dataset.project, el.dataset.map, el.dataset.ticket || null);
  });
  root.querySelectorAll("[data-pane]").forEach((el) => el.onclick = (e) => { if (e.target.closest("[data-term]")) return; e.stopPropagation(); hooks.openChat(el.dataset.pane); });
  root.querySelectorAll("[data-term]").forEach((el) => el.onclick = (e) => { e.stopPropagation(); hooks.openTerminal({ kind: "attach", pane: el.dataset.term }); });
  root.querySelectorAll("[data-run]").forEach((el) => el.onclick = () => hooks.openPath(S.route.project, el.dataset.run + "/codex.log"));
  root.querySelectorAll("[data-driver]").forEach((el) => el.onclick = (e) => { e.stopPropagation(); hooks.startTeam(S.route.project, el.dataset.driver); });
}


// ---------- inbox ----------

export function renderInbox() {
  const host = $("#view"), sum = S.summary;
  if (!sum) { host.innerHTML = `<div class="empty big"><div class="spin"></div></div>`; return; }
  const blocked = allAgents().filter((a) => a.status === "blocked");
  const tickets = sum.projects.flatMap((p) => (p.waiting || []).filter((w) => w.kind !== "agent").map((w) => ({ ...w, project: p.name })));
  const unread = [...S.unread.entries()].map(([pane, u]) => ({ pane, ...u }));
  const changed = sum.projects.filter((p) => p.changes);
  const loops = allAgents().filter((a) => loopDead(a));
  const none = !blocked.length && !tickets.length && !unread.length && !loops.length;
  host.innerHTML = `<div class="page" style="max-width:920px">
    <div class="ph"><div class="grow"><h1>Inbox</h1><div class="sub">Everything waiting on you, across projects</div></div>
      ${unread.length ? `<div class="actions"><button class="btn" id="ib-clear">${icon("check")} Mark all read</button></div>` : ""}</div>
    ${!sum.projects.length ? `<div class="card pad" style="padding:22px 24px"><h2 style="margin:0 0 6px;font-size:16px">Welcome to Research Desk</h2>
      <div class="muted" style="margin-bottom:12px">Add a project folder that uses the research harness (it has <code>maps/</code>), and its maps, tickets, agents and files appear here.</div>
      <button class="btn primary" id="ib-add">${icon("plus")} Add a project</button></div>` : none ? `<div class="card empty big">${icon("check")} All clear. Nothing is waiting on you.</div>` : ""}
    ${blocked.length ? `<div class="sec"><h2>Waiting for your answer</h2><span class="meta">agents stopped at a prompt</span></div><div class="card rows">${blocked.map((a) => `<div class="row click" data-pane="${esc(a.pane)}">
      ${avatar(a)}<div class="grow"><div class="t1">${esc(agentLabel(a))}${a.project ? ` · <span class="muted">${esc(a.project)}</span>` : ""}</div><div class="t2">${esc(a.title || "")}</div></div>
      <button class="btn sm primary">Answer</button></div>`).join("")}</div>` : ""}
    ${loops.length ? `<div class="sec"><h2>Loops that went quiet</h2><span class="meta">a driver missed its pass, or a pass died (network, sleep)</span></div><div class="card rows">${loops.map((a) => `<div class="row click" data-pane="${esc(a.pane)}">
      ${avatar(a)}<div class="grow"><div class="t1">${esc(agentLabel(a))}${a.project ? ` · <span class="muted">${esc(a.project)}</span>` : ""}</div><div class="t2 err">${esc(loopNote(a))}</div></div>
      <button class="btn sm primary" data-restart="${esc(a.pane)}">Restart loop</button></div>`).join("")}</div>` : ""}
    ${unread.length ? `<div class="sec"><h2>Finished turns</h2><span class="meta">replies to what you sent</span></div><div class="card rows">${unread.map((u) => `<div class="row click" data-pane="${esc(u.pane)}">
      ${icon("chat")}<div class="grow"><div class="t1">${esc(u.label)}${u.project ? ` · <span class="muted">${esc(u.project)}</span>` : ""}</div><div class="t2">${esc(u.text || "finished its turn")}</div></div>
      <span class="meta muted">${esc(ago(u.at / 1000))}</span></div>`).join("")}</div>` : ""}
    ${tickets.length ? `<div class="sec"><h2>Decisions waiting</h2><span class="meta">grilling tickets and needs-you items</span></div><div class="card rows">${tickets.map((w) => `<div class="row click" data-project="${esc(w.project)}" data-map="${esc(w.map_folder)}" data-ticket="${esc(w.folder || "")}">
      ${pill("waiting", w.project)}<div class="grow"><div class="t1">${esc(w.text)}</div><div class="t2 mono">${esc(w.id || w.map)}</div></div></div>`).join("")}</div>` : ""}
    ${changed.length ? `<div class="sec"><h2>Changed since you last looked</h2></div><div class="card rows">${changed.map((p) => `<a class="row click" href="${href({ project: p.name })}" style="color:inherit;text-decoration:none">
      ${icon("folder")}<div class="grow"><div class="t1">${esc(p.name)}</div></div><span class="count">${p.changes}</span></a>`).join("")}</div>` : ""}
    ${S.notes.length ? `<div class="sec"><h2>Recent</h2></div><div class="card rows">${S.notes.slice(0, 20).map((n) => `<div class="row"><span class="dot ${n.kind}"></span><div class="grow"><div class="t1">${esc(n.text)}</div></div><span class="meta muted">${esc(ago(n.at / 1000))}</span></div>`).join("")}</div>` : ""}
  </div>`;
  host.querySelectorAll("[data-map]").forEach((el) => el.onclick = () => goMap(el.dataset.project, el.dataset.map, el.dataset.ticket || null));
  host.querySelectorAll("[data-pane]").forEach((el) => el.onclick = () => hooks.openChat(el.dataset.pane));
  if ($("#ib-add")) $("#ib-add").onclick = () => hooks.addProject();
  host.querySelectorAll("[data-restart]").forEach((b) => b.onclick = (e) => { e.stopPropagation(); restartLoop(b.dataset.restart); });
  if ($("#ib-clear")) $("#ib-clear").onclick = () => { S.unread.clear(); hooks.badge(); renderInbox(); };
}

// ---------- GPUs ----------

let gpuTimer = null;
// every node of each pool (projects file [gpu_pools]); your jobs first, since on a shared cluster they can land anywhere
async function loadGpus(fresh) {
  const { pools } = await get("/api/gpu-hosts");
  const hosts = Object.values(pools).flat();
  const res = await Promise.all(hosts.map((h) => get("/api/gpus", { host: h, ...(fresh ? { fresh: 1 } : {}) }).then((g) => [h, g]).catch((e) => [h, { error: e.message }])));
  return { pools, by: Object.fromEntries(res) };
}
const isFree = (x) => x.util < 5 && !x.procs.length;

export async function renderGpus(fresh = false, quiet = false) {
  const host = $("#view");
  if (!quiet) host.innerHTML = `<div class="page"><div class="ph"><div class="grow"><h1>GPUs</h1><div class="sub">Every node of each pool, from <code>nvidia-smi</code>; refreshed every 20 s while this page is open. Edit the node lists in Settings (<code>[gpu_pools]</code>).</div></div>
    <div class="actions"><button class="btn" id="gp-ref">${icon("refresh")} Refresh</button></div></div><div id="gp-body"><div class="spin"></div></div></div>`;
  $("#gp-ref").onclick = () => renderGpus(true, true);
  clearInterval(gpuTimer);
  gpuTimer = setInterval(() => { if (S.route.view !== "gpus" || !$("#gp-body")) return clearInterval(gpuTimer); renderGpus(false, true); }, 20000);
  let data;
  try { data = await loadGpus(fresh); } catch (e) { $("#gp-body").innerHTML = `<div class="err">${esc(e.message)}</div>`; return; }
  if (!$("#gp-body")) return;
  const mine = [];
  Object.entries(data.by).forEach(([h, g]) => (g.gpus || []).forEach((x) => { if (x.mine) mine.push({ h, x, me: g.me }); }));
  const cell = (h, x) => `<div class="gcell ${x.mine ? "mine" : isFree(x) ? "free" : "busy"}" title="${esc(h)} GPU ${x.index} · ${x.util}% · ${(x.mem / 1024).toFixed(0)}/${(x.total / 1024).toFixed(0)} GB · ${x.temp}°C${x.procs.length ? "\n" + x.procs.map((p) => `${p.user} pid ${p.pid} ${p.mem} MiB`).join("\n") : "\nidle"}">
      <div class="gfill" style="height:${Math.max(4, x.util)}%"></div><div class="gmem" style="width:${(100 * x.mem / Math.max(1, x.total)).toFixed(0)}%"></div><span>${x.index}</span></div>`;
  $("#gp-body").innerHTML = `
    <div class="sec" style="margin-top:0"><h2>Your jobs</h2><span class="meta">${mine.length ? `${mine.length} GPU${mine.length > 1 ? "s" : ""}` : "none running"}</span></div>
    ${mine.length ? `<div class="card rows">${mine.map(({ h, x, me }) => `<div class="row"><b class="mono">${esc(h)}</b><span class="mono muted">GPU ${x.index}</span>
      <div class="grow"><div class="bar" style="max-width:260px"><span style="width:${x.util}%;background:var(--c-work)"></span></div></div>
      <span class="muted" style="font-size:12px">${x.util}% · ${(x.mem / 1024).toFixed(0)}/${(x.total / 1024).toFixed(0)} GB · pid ${esc(x.procs.filter((p) => p.user === me).map((p) => p.pid).join(", "))}</span></div>`).join("")}</div>` : ""}
    ${Object.entries(data.pools).map(([pool, hosts]) => {
      const all = hosts.flatMap((h) => data.by[h]?.gpus || []);
      return `<div class="sec"><h2>${esc(pool)}</h2><span class="meta">${all.filter(isFree).length} of ${all.length} free · ${all.filter((x) => x.mine).length} yours</span></div>
      <div class="card rows">${hosts.map((h) => { const g = data.by[h] || {};
        if (g.error) return `<div class="row"><b class="mono" style="width:96px">${esc(h)}</b><span class="err" style="font-size:12px">${esc(g.error)}</span></div>`;
        const gs = g.gpus || [];
        return `<div class="row"><b class="mono" style="width:96px">${esc(h)}</b><div class="gcells">${gs.map((x) => cell(h, x)).join("")}</div>
          <span class="muted" style="font-size:12px;white-space:nowrap">${gs.filter(isFree).length}/${gs.length} free · ${esc(gs[0]?.name?.replace(/NVIDIA |GeForce /g, "") || "")}</span></div>`; }).join("")}</div>`;
    }).join("")}
    <div class="legend-inline"><span><i class="gcell mine"></i> yours</span><span><i class="gcell busy"></i> someone's job</span><span><i class="gcell free"></i> free</span><span class="muted">bar height: utilisation · line: memory</span></div>`;
}

const gpuCache = {};
async function loadMiniGpus() {
  try {
    const data = await loadGpus(false);
    const el = $("#ov-gpus");
    if (!el) return;
    const mine = Object.values(data.by).flatMap((g) => (g.gpus || []).filter((x) => x.mine)).length;
    el.innerHTML = gpuCache.all = `<div class="rows">${Object.entries(data.pools).map(([pool, hosts]) => {
      const all = hosts.flatMap((h) => data.by[h]?.gpus || []);
      return `<div class="row" style="padding:6px 0"><b style="width:80px">${esc(pool)}</b><div class="grow"><div class="bar"><span style="width:${100 * (all.length - all.filter(isFree).length) / Math.max(1, all.length)}%;background:var(--c-work)"></span></div></div>
        <span class="muted" style="font-size:12px;white-space:nowrap">${all.filter(isFree).length}/${all.length} free · ${all.filter((x) => x.mine).length} yours</span></div>`; }).join("")}</div>
      <div class="muted" style="font-size:11.5px;margin-top:4px">${mine ? `${mine} GPU${mine > 1 ? "s" : ""} running your jobs` : "No GPU is running your jobs"}</div>`;
  } catch (e) { if ($("#ov-gpus")) $("#ov-gpus").innerHTML = `<div class="err" style="font-size:12px">${esc(e.message)}</div>`; }
}

// ---------- search across a project's conversations ----------

export function renderSearch() {
  const host = $("#view"), project = S.route.project;
  host.innerHTML = `<div class="page" style="max-width:980px"><div class="ph"><div class="grow"><h1>Search conversations</h1>
      <div class="sub">Every desk, driver, worker and Codex conversation in ${esc(project)}, newest first</div></div></div>
    <input id="sq" class="searchbox" placeholder="Words to find, e.g. AFDB v2 filter" value="${esc(store("search." + project) || "")}" autocomplete="off" spellcheck="false">
    <div id="sres" style="margin-top:14px"></div></div>`;
  const inp = $("#sq");
  let timer = null, seq = 0;
  const run = async () => {
    const q = inp.value.trim();
    store("search." + project, q);
    if (q.length < 2) { $("#sres").innerHTML = `<div class="empty">Type at least two characters.</div>`; return; }
    const my = ++seq;
    $("#sres").innerHTML = `<div class="spin"></div>`;
    let r;
    try { r = await get("/api/search", { project, q }); } catch (e) { $("#sres").innerHTML = `<div class="err">${esc(e.message)}</div>`; return; }
    if (my !== seq) return;
    const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    const mark = (s) => terms.reduce((h, t) => h.replace(new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"), (m) => `<mark>${m}</mark>`), esc(s));
    const groups = new Map();
    r.hits.forEach((h) => { if (!groups.has(h.session)) groups.set(h.session, []); groups.get(h.session).push(h); });
    $("#sres").innerHTML = `<div class="muted" style="font-size:12px;margin-bottom:8px">${r.hits.length} matches in ${groups.size} conversation${groups.size === 1 ? "" : "s"} · ${r.ms} ms</div>`
      + [...groups.values()].map((hs) => `<div class="card" style="margin-bottom:10px"><div class="shead">${icon(hs[0].codex ? "code" : "chat")}<b>${esc(hs[0].title || "Untitled conversation")}</b>
          ${hs[0].live_pane ? `<span class="pill s-working">live · ${esc(hs[0].live_label || "")}</span>` : ""}<span class="grow"></span><span class="muted">${esc(ago(hs[0].ts))}</span></div>
        <div class="rows">${hs.slice(0, 6).map((h) => `<div class="row click" data-s="${esc(h.session)}" data-u="${esc(h.uuid)}">
          <span class="pill plain" style="min-width:64px;justify-content:center">${esc(h.role === "from" ? "message" : h.role === "user" ? "you" : "agent")}</span>
          <div class="grow"><div class="t2" style="color:var(--ink-2);-webkit-line-clamp:3">${mark(h.snippet)}</div></div><span class="muted" style="font-size:11px">${esc(ago(h.ts))}</span></div>`).join("")}
          ${hs.length > 6 ? `<div class="empty" style="padding:6px 14px">${hs.length - 6} more in this conversation</div>` : ""}</div></div>`).join("")
      || `<div class="empty big">Nothing found.</div>`;
    $("#sres").querySelectorAll("[data-s]").forEach((el) => el.onclick = () => {
      const h = r.hits.find((x) => x.session === el.dataset.s && x.uuid === el.dataset.u);
      hooks.openArchive(h.session, h.uuid, { title: h.title, project, live_pane: h.live_pane });
    });
  };
  inp.oninput = () => { clearTimeout(timer); timer = setTimeout(run, 350); };
  inp.onkeydown = (e) => { if (e.key === "Enter") { clearTimeout(timer); run(); } };
  setTimeout(() => inp.focus(), 20);
  if (inp.value) run();
}

// ---------- settings ----------

export async function renderSettings() {
  const host = $("#view");
  host.innerHTML = `<div class="page" style="max-width:980px"><div class="ph"><div class="grow"><h1>Settings</h1></div></div><div class="spin"></div></div>`;
  let cfg;
  try { cfg = await get("/api/config"); } catch (e) { host.innerHTML = `<div class="page"><div class="err">${esc(e.message)}</div></div>`; return; }
  const sum = S.summary || {};
  const pr = S.prefs;
  host.innerHTML = `<div class="page" style="max-width:980px"><div class="ph"><div class="grow"><h1>Settings</h1><div class="sub">Research Desk ${esc(sum.version || "")}${window.desk ? " · app" : " · browser"}</div></div>
      <div class="actions"><button class="btn" id="st-close" title="Back (Esc)">${icon("x")} Close</button></div></div>
    <div class="sec"><h2>Notifications</h2></div><div class="card pad" style="display:flex;flex-direction:column;gap:8px">
      <label><input type="checkbox" id="pf-prompt" ${pr.notifyPrompt ? "checked" : ""}> When an agent stops at a prompt and needs your answer</label>
      <label><input type="checkbox" id="pf-done" ${pr.notifyDone ? "checked" : ""}> When an agent finishes a turn you started from here (only if you aren't looking at it)</label>
      <label><input type="checkbox" id="pf-progress" ${pr.notifyProgress ? "checked" : ""}> When a ticket resolves, starts running, is held or parked, or a map closes (in projects you aren't looking at)</label>
      <label><input type="checkbox" id="pf-verbose" ${pr.verbose ? "checked" : ""}> Show every tool call in the chat (otherwise long runs fold)</label>
      ${window.desk?.loginItem ? `<label><input type="checkbox" id="pf-login"> Open Research Desk when you log in</label>` : ""}</div>
    <div class="sec"><h2>Status</h2></div><div class="card pad kv">
      <span class="k">herdr</span><span>${sum.herdr_error ? `<span class="err">${esc(sum.herdr_error)}</span>` : "connected"}</span>
      <span class="k">Claude token</span><span>${S.data ? (S.data.keychain ? "Keychain item found; agents get it when they start" : "no Keychain item; agents use claude's own login") : "—"}</span>
      <span class="k">Start buttons</span><span>${sum.dry_run ? "dry run: they only show the herdr commands" : "live"}</span>
      <span class="k">Projects file</span><span class="mono">${esc(cfg.path)}</span></div>
    <div class="sec"><h2>Projects</h2><span class="grow"></span><button class="btn sm" id="st-add">${icon("plus")} Add a project</button></div>
    <div class="card pad"><div class="muted" style="font-size:12px;margin-bottom:8px">The whole file: projects, servers, Claude flags and per-role environment. Saved only if it parses; the old copy is kept as <code>.bak</code>.</div>
      <textarea class="code" id="st-cfg" spellcheck="false">${esc(cfg.text)}</textarea>
      <div class="actions" style="margin-top:8px"><button class="btn primary" id="st-save">Save</button><span class="muted" id="st-msg"></span></div></div></div>`;
  const pref = (id, k) => { $(id).onchange = (e) => { S.prefs[k] = e.target.checked; savePrefs(); }; };
  if ($("#pf-login")) {
    window.desk.loginItem().then((on) => { $("#pf-login").checked = on; });
    $("#pf-login").onchange = (e) => window.desk.loginItem(e.target.checked);
  }
  pref("#pf-prompt", "notifyPrompt"); pref("#pf-done", "notifyDone"); pref("#pf-progress", "notifyProgress"); pref("#pf-verbose", "verbose");
  $("#st-add").onclick = () => hooks.addProject();
  $("#st-close").onclick = () => hooks.leaveSettings();
  $("#st-save").onclick = async () => {
    try { await post("/api/config", { text: $("#st-cfg").value }); $("#st-msg").textContent = "Saved."; hooks.refresh(); }
    catch (e) { $("#st-msg").innerHTML = `<span class="err">${esc(e.message)}</span>`; }
  };
}

// ---------- dispatch ----------

export function renderView(full = true) {
  const r = S.route;
  renderTitlebar();
  if (r.view === "inbox") return renderInbox();
  if (r.view === "gpus") return full ? renderGpus() : null;
  if (r.view === "settings") return full ? renderSettings() : null;
  if (!S.data || S.data.name !== r.project) { $("#view").innerHTML = S.err ? `<div class="page"><div class="err">${esc(S.err)}</div></div>` : `<div class="empty big"><div class="spin"></div></div>`; return; }
  if (r.view === "project") return renderOverview();
  if (r.view === "search") return full ? renderSearch() : null;
  if (r.view === "files") { if (full || !$("#trees")) { $("#view").innerHTML = `<div class="page full"><div class="tabbody" id="pfiles"></div></div>`; renderFiles($("#pfiles"), null); } return; }
  if (r.view === "map") return renderMap(full);
}
export { go };
