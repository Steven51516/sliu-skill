// Left sidebar: search, inbox, projects (with the open project's maps), and the sessions of the open project by state.
import { S, $, esc, icon, go, href, hooks, agentLabel, avatar, allAgents, AGENT_WORD } from "./core.js";

const STATE_ORDER = [["blocked", "Needs you"], ["working", "Working"], ["idle", "Idle"]];

export function inboxCount() {
  if (!S.summary) return 0;
  const waiting = S.summary.projects.reduce((n, p) => n + (p.waiting || []).length, 0);
  const blockedOutside = (S.summary.other_agents || []).filter((a) => a.status === "blocked").length;
  return waiting + blockedOutside + S.unread.size;
}

export function renderSidebar() {
  const sum = S.summary, r = S.route;
  const projects = sum ? sum.projects : [];
  const cur = r.project;
  const inbox = inboxCount();
  const nav = (h, ic, label, on, extra = "") => `<a class="nav ${on ? "on" : ""}" href="${h}">${icon(ic)}<span class="label">${esc(label)}</span>${extra}</a>`;
  let html = `<div class="side-top"><span class="brand">Research Desk</span>
      <button class="btn ghost sm icon" id="sb-new" title="New session (⌘N)">${icon("plus")}</button></div>
    <div class="side-search" id="sb-search">${icon("search")}<span class="grow">Search or jump to…</span><kbd>⌘K</kbd></div>
    <div class="side-scroll">
    ${nav("#/inbox", "inbox", "Inbox", r.view === "inbox", inbox ? `<span class="count ${inbox ? "alert" : ""}">${inbox}</span>` : "")}
    ${nav("#/gpus", "gpu", "GPUs", r.view === "gpus")}
    <div class="side-sec"><span class="grow">Projects</span><button class="btn ghost sm icon" id="sb-add" title="Add a project">${icon("plus")}</button></div>`;
  for (const p of projects) {
    const working = (p.agents || []).filter((a) => a.status === "working").length;
    const blocked = (p.agents || []).filter((a) => a.status === "blocked").length;
    const waiting = (p.waiting || []).length;
    const open = p.name === cur;
    html += `<a class="nav ${open && r.view === "project" ? "on" : ""}" href="${href({ project: p.name })}" title="${esc(p.error || "")}">
      ${icon(open ? "home" : "folder")}<span class="label">${esc(p.name)}</span>
      ${p.ok === false ? `<span class="count alert">!</span>` : ""}
      ${waiting ? `<span class="count alert" title="waiting on you">${waiting}</span>` : working ? `<span class="count work" title="agents working">${working}</span>` : ""}
      ${!waiting && !working && (p.agents || []).length ? `<span class="dot idle" title="${p.agents.length} agents idle"></span>` : ""}
      ${blocked && !waiting ? `<span class="dot blocked"></span>` : ""}</a>`;
    if (open && S.data && S.data.name === p.name) {
      const maps = S.data.maps.filter((m) => m.status !== "closed");
      for (const m of maps) {
        const st = m.driven ? "working" : m.status;
        html += `<a class="nav sub ${r.view === "map" && r.map === m.folder ? "on" : ""}" href="${href({ project: p.name, map: m.folder, view: "map" })}" title="${esc(m.title)}">
          <span class="dot ${st}"></span><span class="mid">${esc(m.id)}</span><span class="label">${esc(m.title)}</span></a>`;
      }
      const closed = S.data.maps.length - maps.length;
      if (closed) html += `<a class="nav sub" href="${href({ project: p.name })}#milestones"><span class="label muted">${closed} closed map${closed > 1 ? "s" : ""}</span></a>`;
      html += `<a class="nav sub ${r.view === "files" ? "on" : ""}" href="${href({ project: p.name, view: "files" })}">${icon("folder")}<span class="label">Files</span></a>`;
    }
  }
  if (sum && sum.unregistered.length) {
    html += `<div class="side-sec">Found, not added</div>` + sum.unregistered.map((u) =>
      `<a class="nav" data-add="${esc(u.name)}" data-path="${esc(u.path)}">${icon("plus")}<span class="label muted">${esc(u.name)}</span></a>`).join("");
  }
  // sessions of the open project (else all), grouped by state
  const agents = allAgents().filter((a) => cur ? a.project === cur : true);
  html += `<div class="side-sec"><span class="grow">${cur ? "Sessions" : "All sessions"}</span>
    <button class="btn ghost sm icon" id="sb-new2" title="New session">${icon("plus")}</button></div>`;
  if (!agents.length) html += `<div class="empty" style="padding:4px 8px">${sum && sum.herdr_error ? "herdr is not running" : "No live agent"}${cur ? " in this project" : ""}.</div>`;
  for (const [st, label] of STATE_ORDER) {
    const group = agents.filter((a) => (st === "idle" ? !["blocked", "working"].includes(a.status) : a.status === st));
    if (!group.length) continue;
    if (agents.length > 3) html += `<div class="side-sec" style="padding-top:6px;font-size:10.5px">${label}</div>`;
    html += group.map((a) => `<div class="agent-row ${S.chat.open && S.chat.pane === a.pane ? "on" : ""}" data-pane="${esc(a.pane)}" title="${esc(a.title || "")}">
      ${avatar(a)}<div class="who"><div class="l1">${esc(agentLabel(a))}${!cur && a.project ? ` <span class="muted">· ${esc(a.project)}</span>` : ""}</div>
      <div class="l2">${esc(a.status === "blocked" ? "Needs your answer" : a.title || AGENT_WORD[a.status] || "")}</div></div>
      ${S.unread.has(a.pane) ? `<span class="count alert" title="finished a turn">1</span>` : `<span class="dot ${a.status}"></span>`}</div>`).join("");
  }
  html += `</div><div class="side-foot">
    <a class="btn ghost sm icon" href="#/settings" title="Settings (⌘,)">${icon("gear")}</a>
    <span class="dot ${sum && !sum.herdr_error ? "idle" : "blocked"}" title="${esc(sum?.herdr_error || "herdr connected")}"></span>
    <span>${sum && !sum.herdr_error ? "herdr" : "herdr offline"}</span><span class="grow"></span>
    ${sum && sum.dry_run ? `<span class="tag warn" title="Start buttons send nothing">dry run</span>` : ""}</div>`;
  const el = $("#sidebar"), scroll = el.querySelector(".side-scroll")?.scrollTop || 0;
  el.innerHTML = html;
  el.querySelector(".side-scroll").scrollTop = scroll;
  $("#sb-search").onclick = () => hooks.palette();
  $("#sb-new").onclick = $("#sb-new2").onclick = () => hooks.newSession(cur);
  $("#sb-add").onclick = () => hooks.addProject();
  el.querySelectorAll("[data-add]").forEach((a) => a.onclick = () => hooks.addProject({ name: a.dataset.add, path: a.dataset.path }));
  el.querySelectorAll(".agent-row").forEach((row) => row.onclick = () => hooks.openChat(row.dataset.pane));
}

export function initSidebarResize() {
  const bar = $("#sidebar-resize"), root = document.documentElement;
  const w = +localStorage.getItem("rd.sidew");
  if (w) root.style.setProperty("--side-w", w + "px");
  bar.onpointerdown = (e) => {
    bar.setPointerCapture(e.pointerId);
    bar.onpointermove = (ev) => root.style.setProperty("--side-w", Math.max(200, Math.min(420, ev.clientX)) + "px");
    bar.onpointerup = () => { bar.onpointermove = null; try { localStorage.setItem("rd.sidew", parseInt(getComputedStyle(root).getPropertyValue("--side-w"))); } catch (_) { /* ignore */ } };
  };
}

export { go };
