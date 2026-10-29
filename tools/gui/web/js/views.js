// Pages: project overview, inbox, GPUs, settings, project files; and the title bar.
import { S, $, esc, get, post, toast, icon, pill, ago, go, goMap, href, hooks, agentLabel, avatar, allAgents, AGENT_WORD, popMenu, savePrefs } from "./core.js";
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
        ${desk ? `<button class="btn primary" id="ov-desk">${icon("chat")} Talk to the desk</button>` : `<button class="btn primary" id="ov-team">${icon("users")} Start team</button>`}
        ${desk && open.some((m) => ["open", "claimed"].includes(m.status) && !m.driven) ? `<button class="btn" id="ov-team">${icon("users")} Start drivers</button>` : ""}
        <button class="btn" id="ov-new">${icon("plus")} New session</button>
        <button class="btn" id="ov-idea">${icon("spark")} New map from an idea</button>
        <button class="btn icon" id="ov-more" title="More">${icon("more")}</button></div></div>
    <div class="stats">
      ${stat(d.waiting.length, "need you", d.waiting.length ? "alert" : "")}${stat(running.length, "tickets running", running.length ? "work" : "")}
      ${stat(ready.length, "ready to start", ready.length ? "open" : "")}${stat(open.length, "open maps")}${stat(`${working}/${d.agents.length}`, "agents working", working ? "work" : "")}</div>
    <div class="cols" style="margin-top:6px"><div>
      ${d.waiting.length ? `<div class="sec"><h2>Needs you</h2></div><div class="card rows">${d.waiting.map(waitingRow).join("")}</div>` : ""}
      ${ch.since && ch.items.length ? `<div class="sec"><h2>Since you last looked</h2><span class="meta">${esc(ago(ch.since))}</span><span class="grow"></span>
          <button class="btn sm" id="ov-seen">${icon("check")} Mark as seen</button></div>
        <div class="card" style="padding:4px 0">${ch.items.slice(0, 30).map((c) => `<div class="change"><a data-map="${esc(c.map_folder)}" data-ticket="${esc(c.folder || "")}" class="mono">${esc(c.id)}</a>
          <span class="grow" style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.title)}</span>
          ${c.from ? pill(c.from) : `<span class="pill plain">new</span>`}<span class="arrow">→</span>${pill(c.to)}</div>`).join("")}</div>` : ""}
      ${running.length ? `<div class="sec"><h2>Running</h2></div><div class="card rows">${running.map((t) => `<div class="row click" data-map="${esc(t.map.folder)}" data-ticket="${esc(t.folder)}">
          <span class="mono muted">${esc(t.id)}</span><div class="grow"><div class="t1">${esc(t.title)}</div>${t.jobs.length ? `<div class="t2 mono">${esc(t.jobs.slice(-2).join(" · "))}</div>` : ""}</div>${pill(t.status)}</div>`).join("")}</div>` : ""}
      <div class="sec"><h2>Maps</h2><span class="meta">${open.length} open · ${closed.length} closed</span></div>
      <div class="grid">${open.map(mapCard).join("") || `<div class="card empty">No open map. Chart one with “New map from an idea”.</div>`}</div>
    </div><div>
      <div class="sec"><h2>Team</h2><span class="meta">${d.herdr_error ? `<span class="err">herdr: ${esc(d.herdr_error)}</span>` : ""}</span></div>
      <div class="card rows">${d.agents.map(agentRow).join("") || `<div class="empty">Nobody is working here. <a id="ov-team2">Start the team</a> or open a new session.</div>`}</div>
      ${d.server ? `<div class="sec"><h2>GPUs · ${esc(d.server)}</h2><span class="grow"></span><a href="#/gpus" class="meta">all hosts</a></div><div class="card pad" id="ov-gpus">${gpuCache[d.server] || `<div class="spin"></div>`}</div>` : ""}
      <div class="sec" id="milestones"><h2>Milestones</h2><span class="meta">closed maps</span></div>
      <div class="card pad"><div class="timeline">${closed.map((m) => `<div class="tl" data-map="${esc(m.folder)}"><div class="h"><span class="mid">${esc(m.id)}</span>${esc(m.title)}</div>
        <div class="d">${esc(m.updated || "")}</div><div class="o">${esc(m.outcome || "(no outcome recorded)")}</div></div>`).join("") || `<div class="muted">None yet.</div>`}</div></div>
      ${d.problems.length ? `<div class="sec"><h2>Tracker warnings</h2></div><div class="card pad"><details><summary>${d.problems.length} from <code>research-status --check</code></summary>
        <ul style="padding-left:18px;font-size:12px">${d.problems.map((p) => `<li class="mono">${esc(p)}</li>`).join("")}</ul></details></div>` : ""}
    </div></div></div>`;
  wire(host);
  const team = () => hooks.startTeam(d.name);
  if ($("#ov-desk")) $("#ov-desk").onclick = () => hooks.openChat(desk.pane);
  if ($("#ov-team")) $("#ov-team").onclick = team;
  if ($("#ov-team2")) $("#ov-team2").onclick = team;
  $("#ov-new").onclick = () => hooks.newSession(d.name);
  $("#ov-idea").onclick = () => hooks.newSession(d.name, "wayfinder");
  if ($("#ov-seen")) $("#ov-seen").onclick = () => post("/api/seen", { project: d.name }).then(() => hooks.refresh());
  $("#ov-more").onclick = (e) => popMenu(e.currentTarget, [
    ...(desk ? [{ label: "Ask the desk for a digest", icon: "doc", run: () => hooks.openChat(desk.pane, { text: "digest" }) }, "-"] : []),
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
  if (d.server) loadMiniGpus(d.server);
}

const stat = (n, l, cls = "") => `<div class="card stat ${cls}"><div class="n">${esc(n)}</div><div class="l">${esc(l)}</div></div>`;

function waitingRow(w) {
  if (w.kind === "agent") return `<div class="row click" data-pane="${esc(w.pane)}">${pill("blocked", "prompt")}<div class="grow"><div class="t1">${esc(w.text)}</div></div>
    <button class="btn sm primary" data-pane="${esc(w.pane)}">Answer</button></div>`;
  if (w.kind === "ticket") return `<div class="row click" data-map="${esc(w.map_folder)}" data-ticket="${esc(w.folder)}">${pill("waiting", "decision")}
    <div class="grow"><div class="t1">${esc(w.text)}</div><div class="t2 mono">${esc(w.id)}</div></div><button class="btn sm">Open</button></div>`;
  return `<div class="row click" data-map="${esc(w.map_folder)}">${pill("waiting", "map")}<div class="grow"><div class="t1">${esc(w.text)}</div><div class="t2 mono">${esc(w.map)}</div></div></div>`;
}

function agentRow(a) {
  return `<div class="row click" data-pane="${esc(a.pane)}">${avatar(a)}<div class="grow"><div class="t1">${esc(agentLabel(a))}</div>
    <div class="t2">${esc(a.status === "blocked" ? "waiting for your answer" : a.title || "")}</div></div>${pill(a.status, AGENT_WORD[a.status] || a.status)}
    <button class="btn ghost sm icon" data-term="${esc(a.pane)}" title="Open its terminal">${icon("term")}</button></div>`;
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
    <div class="dest">${esc(m.destination)}</div>
    <div class="foot"><div class="bar">${bar}</div><span>${m.counts.resolved || 0}/${m.tickets.length}</span>
      ${live && !m.driven ? `<button class="btn sm" data-driver="${esc(m.folder)}">${icon("play")} Driver</button>` : ""}</div></div>`;
}

function wire(root) {
  root.querySelectorAll("[data-map]").forEach((el) => el.onclick = (e) => {
    if (e.target.closest("button") && !e.target.closest("button").dataset.map) return;
    e.preventDefault();
    goMap(S.route.project || el.dataset.project, el.dataset.map, el.dataset.ticket || null);
  });
  root.querySelectorAll("[data-pane]").forEach((el) => el.onclick = (e) => { if (e.target.closest("[data-term]")) return; e.stopPropagation(); hooks.openChat(el.dataset.pane); });
  root.querySelectorAll("[data-term]").forEach((el) => el.onclick = (e) => { e.stopPropagation(); hooks.openTerminal({ kind: "attach", pane: el.dataset.term }); });
  root.querySelectorAll("[data-driver]").forEach((el) => el.onclick = (e) => { e.stopPropagation(); hooks.startTeam(S.route.project, el.dataset.driver); });
}

const gpuCache = {};
async function loadMiniGpus(host) {
  try {
    const g = await get("/api/gpus", { host });
    const el = $("#ov-gpus");
    if (!el) return;
    const mine = g.gpus.filter((x) => x.mine).length;
    el.innerHTML = gpuCache[host] = `<div style="display:flex;gap:4px;align-items:flex-end;height:46px">${g.gpus.map((x) => `<div title="GPU ${x.index}: ${x.util}% util, ${(x.mem / 1024).toFixed(0)}/${(x.total / 1024).toFixed(0)} GB${x.procs.length ? " · " + x.procs.map((p) => p.user).join(", ") : ""}"
        style="flex:1;display:flex;flex-direction:column;justify-content:flex-end;height:100%;background:var(--active);border-radius:4px;overflow:hidden;${x.mine ? "outline:2px solid var(--accent)" : ""}">
        <div style="height:${Math.max(3, x.util)}%;background:var(--c-work)"></div></div>`).join("")}</div>
      <div class="muted" style="font-size:11.5px;margin-top:6px">${g.gpus.filter((x) => x.util < 5 && !x.procs.length).length} free of ${g.gpus.length}${mine ? ` · ${mine} running yours` : ""} · ${esc(g.gpus[0]?.name || "")}</div>`;
  } catch (e) { if ($("#ov-gpus")) $("#ov-gpus").innerHTML = `<div class="err" style="font-size:12px">${esc(e.message)}</div>`; }
}

// ---------- inbox ----------

export function renderInbox() {
  const host = $("#view"), sum = S.summary;
  if (!sum) { host.innerHTML = `<div class="empty big"><div class="spin"></div></div>`; return; }
  const blocked = allAgents().filter((a) => a.status === "blocked");
  const tickets = sum.projects.flatMap((p) => (p.waiting || []).filter((w) => w.kind !== "agent").map((w) => ({ ...w, project: p.name })));
  const unread = [...S.unread.entries()].map(([pane, u]) => ({ pane, ...u }));
  const changed = sum.projects.filter((p) => p.changes);
  const none = !blocked.length && !tickets.length && !unread.length;
  host.innerHTML = `<div class="page" style="max-width:920px">
    <div class="ph"><div class="grow"><h1>Inbox</h1><div class="sub">Everything waiting on you, across projects</div></div>
      ${unread.length ? `<div class="actions"><button class="btn" id="ib-clear">${icon("check")} Mark all read</button></div>` : ""}</div>
    ${!sum.projects.length ? `<div class="card pad" style="padding:22px 24px"><h2 style="margin:0 0 6px;font-size:16px">Welcome to Research Desk</h2>
      <div class="muted" style="margin-bottom:12px">Add a project folder that uses the research harness (it has <code>maps/</code>), and its maps, tickets, agents and files appear here.</div>
      <button class="btn primary" id="ib-add">${icon("plus")} Add a project</button></div>` : none ? `<div class="card empty big">${icon("check")} All clear. Nothing is waiting on you.</div>` : ""}
    ${blocked.length ? `<div class="sec"><h2>Waiting for your answer</h2><span class="meta">agents stopped at a prompt</span></div><div class="card rows">${blocked.map((a) => `<div class="row click" data-pane="${esc(a.pane)}">
      ${avatar(a)}<div class="grow"><div class="t1">${esc(agentLabel(a))}${a.project ? ` · <span class="muted">${esc(a.project)}</span>` : ""}</div><div class="t2">${esc(a.title || "")}</div></div>
      <button class="btn sm primary">Answer</button></div>`).join("")}</div>` : ""}
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
  if ($("#ib-clear")) $("#ib-clear").onclick = () => { S.unread.clear(); hooks.badge(); renderInbox(); };
}

// ---------- GPUs ----------

export async function renderGpus(fresh = false) {
  const host = $("#view");
  if (!fresh) host.innerHTML = `<div class="page"><div class="ph"><div class="grow"><h1>GPUs</h1><div class="sub">Live from <code>nvidia-smi</code> on each project's server (cached 20 s)</div></div>
    <div class="actions"><button class="btn" id="gp-ref">${icon("refresh")} Refresh</button></div></div><div id="gp-list" style="display:flex;flex-direction:column;gap:12px"><div class="spin"></div></div></div>`;
  $("#gp-ref").onclick = () => renderGpus(true);
  let hosts;
  try { hosts = (await get("/api/gpu-hosts")).hosts; } catch (e) { $("#gp-list").innerHTML = `<div class="err">${esc(e.message)}</div>`; return; }
  if (!hosts.length) { $("#gp-list").innerHTML = `<div class="card empty">No servers yet: set a project's <code>server</code> in Settings, or add <code>gpu_hosts</code>.</div>`; return; }
  $("#gp-list").innerHTML = hosts.map((h) => `<div class="card gpuhost" id="gh-${esc(h)}"><div class="hh">${icon("server")}<b>${esc(h)}</b><span class="spin"></span></div></div>`).join("");
  hosts.forEach(async (h) => {
    const el = document.getElementById("gh-" + h);
    try {
      const g = await get("/api/gpus", { host: h, ...(fresh ? { fresh: 1 } : {}) });
      const free = g.gpus.filter((x) => x.util < 5 && !x.procs.length).length;
      el.innerHTML = `<div class="hh">${icon("server")}<b>${esc(h)}</b><span class="muted">${esc(g.gpus[0]?.name || "")} · ${free} of ${g.gpus.length} free · ${esc(ago(g.at))}</span></div>
        <div class="gpus">${g.gpus.map((x) => `<div class="gpu ${x.mine ? "mine" : ""}"><div class="gh"><span>GPU ${x.index}</span><span>${x.util}%</span></div>
          <div class="meter"><span style="width:${x.util}%"></span></div><div class="meter mem"><span style="width:${(100 * x.mem / Math.max(1, x.total)).toFixed(0)}%"></span></div>
          <div class="gl"><span>${(x.mem / 1024).toFixed(0)}/${(x.total / 1024).toFixed(0)} GB</span><span>${x.temp}°C</span></div>
          <div class="gl" title="${esc(x.procs.map((p) => `${p.user} pid ${p.pid} ${p.mem} MiB`).join("\n"))}"><span>${x.procs.length ? esc([...new Set(x.procs.map((p) => p.user))].join(", ")) : "idle"}</span></div></div>`).join("")}</div>`;
    } catch (e) { el.innerHTML = `<div class="hh">${icon("server")}<b>${esc(h)}</b></div><div class="err">${esc(e.message)}</div>`; }
  });
}

// ---------- settings ----------

export async function renderSettings() {
  const host = $("#view");
  host.innerHTML = `<div class="page" style="max-width:980px"><div class="ph"><div class="grow"><h1>Settings</h1></div></div><div class="spin"></div></div>`;
  let cfg;
  try { cfg = await get("/api/config"); } catch (e) { host.innerHTML = `<div class="page"><div class="err">${esc(e.message)}</div></div>`; return; }
  const sum = S.summary || {};
  const pr = S.prefs;
  host.innerHTML = `<div class="page" style="max-width:980px"><div class="ph"><div class="grow"><h1>Settings</h1><div class="sub">Research Desk ${esc(sum.version || "")}${window.desk ? " · app" : " · browser"}</div></div></div>
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
  if (r.view === "files") { if (full || !$("#trees")) { $("#view").innerHTML = `<div class="page full"><div class="tabbody" id="pfiles"></div></div>`; renderFiles($("#pfiles"), null); } return; }
  if (r.view === "map") return renderMap(full);
}
export { go };
