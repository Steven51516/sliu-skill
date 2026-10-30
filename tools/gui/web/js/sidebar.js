// Left sidebar: search, inbox, projects (with the open project's maps), and the sessions of the open project by state.
import { S, $, esc, icon, go, href, hooks, agentLabel, avatar, allAgents, AGENT_WORD, safeCls, codexNote, guardNote, loopNote, loopDead, store } from "./core.js";

export function inboxCount() {
  if (!S.summary) return 0;
  const waiting = S.summary.projects.reduce((n, p) => n + (p.waiting || []).length, 0);
  const blockedOutside = (S.summary.other_agents || []).filter((a) => a.status === "blocked").length;
  return waiting + blockedOutside + S.unread.size + (S.summary.asks || []).length;
}

// projects folded in the sidebar (their maps, Files and Search hidden); remembered across reloads
const folded = new Set(store("folded") || []);
function setFold(name, fold) { fold ? folded.add(name) : folded.delete(name); store("folded", [...folded]); renderSidebar(); }

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
    const open = p.name === cur, unfolded = open && !folded.has(p.name);
    html += `<a class="nav ${open && r.view === "project" ? "on" : ""}" href="${href({ project: p.name })}" data-proj="${esc(p.name)}" title="${esc(p.error || "")}">
      <span class="pcaret" data-fold="${esc(p.name)}" title="${unfolded ? "Fold" : "Unfold"}">${unfolded ? "▾" : "▸"}</span>${icon(open ? "home" : "folder")}<span class="label">${esc(p.name)}</span>
      ${p.ok === false ? `<span class="count alert">!</span>` : ""}
      ${waiting ? `<span class="count alert" title="waiting on you">${waiting}</span>` : working ? `<span class="count" title="${working} agent${working > 1 ? "s" : ""} working"><span style="color:var(--c-work)">●</span> ${working}</span>` : ""}
      ${!waiting && !working && (p.agents || []).length ? `<span class="dot idle" title="${p.agents.length} agents idle"></span>` : ""}
      ${blocked && !waiting ? `<span class="dot blocked"></span>` : ""}</a>`;
    if (unfolded && S.data && S.data.name === p.name) {
      const maps = S.data.maps.filter((m) => m.status !== "closed");
      for (const m of maps) {
        const st = m.driven ? "working" : m.status;
        html += `<a class="nav sub ${r.view === "map" && r.map === m.folder ? "on" : ""}" href="${href({ project: p.name, map: m.folder, view: "map" })}" title="${esc(m.title)}">
          <span class="dot ${safeCls(st)}"></span><span class="mid">${esc(m.id)}</span><span class="label">${esc(m.title)}</span></a>`;
      }
      const closed = S.data.maps.length - maps.length;
      if (closed) html += `<a class="nav sub" data-milestones="${esc(p.name)}"><span class="label muted">${closed} closed map${closed > 1 ? "s" : ""}</span></a>`;
      html += `<a class="nav sub ${r.view === "files" ? "on" : ""}" href="${href({ project: p.name, view: "files" })}">${icon("folder")}<span class="label">Files</span></a>`;
      html += `<a class="nav sub ${r.view === "search" ? "on" : ""}" href="${href({ project: p.name, view: "search" })}">${icon("search")}<span class="label">Search conversations</span></a>`;
    }
  }
  if (sum && sum.unregistered.length) {
    html += `<div class="side-sec">Found, not added</div>` + sum.unregistered.map((u) =>
      `<a class="nav" data-add="${esc(u.name)}" data-path="${esc(u.path)}">${icon("plus")}<span class="label muted">${esc(u.name)}</span></a>`).join("");
  }
  // inside a project: its sessions as a team tree. Outside one (Inbox, GPUs, Settings): only sessions that need you;
  // the project rows above already show how busy each project is
  // a folded project shows its sessions the same way: only those that need you
  const needsYou = (a) => a.status === "blocked" || S.unread.has(a.pane) || loopDead(a) || !!guardNote(a);
  const tree = cur && !folded.has(cur);
  const agents = allAgents().filter((a) => (tree ? a.project === cur : needsYou(a)));
  if (tree || agents.length) {
    html += `<div class="side-sec"><span class="grow">${tree ? "Sessions" : "Needs you"}</span>
      ${tree ? `<button class="btn ghost sm icon" id="sb-new2" title="New session">${icon("plus")}</button>` : ""}</div>`;
    if (!agents.length) html += `<div class="empty" style="padding:4px 10px">${sum && sum.herdr_error ? "herdr is not running" : "No live agent in this project"}.</div>`;
  }
  const row = (a, sub = false) => `<div tabindex="0" class="agent-row ${sub ? "sub" : ""} ${S.chat.open && S.chat.pane === a.pane ? "on" : ""}" data-pane="${esc(a.pane)}" title="${esc(a.title || "")}">
      ${avatar(a)}<div class="who"><div class="l1">${esc(agentLabel(a))}${!cur && a.project ? ` <span class="muted">· ${esc(a.project)}</span>` : ""}</div>
      <div class="l2 ${(guardNote(a) || loopDead(a)) && a.status !== "blocked" ? "err" : ""}">${esc(a.status === "blocked" ? "Needs your answer" : guardNote(a) || (loopDead(a) ? loopNote(a) : "") || codexNote(a) || (a.role === "worker" ? a.ticket_title : "") || a.title || AGENT_WORD[a.status] || "")}</div></div>
      ${S.unread.has(a.pane) ? `<span class="count alert" title="finished a turn">1</span>` : `<span class="dot ${safeCls(a.status)}"></span>`}</div>`;
  if (tree) {
    // the team as a tree: desk, then each driver with the workers it opened, then everything else
    const workers = agents.filter((a) => a.role === "worker");
    const placed = new Set();
    for (const a of agents.filter((x) => x.role === "desk")) { html += row(a); placed.add(a.pane); }
    for (const d of agents.filter((x) => x.role === "driver")) {
      html += row(d); placed.add(d.pane);
      for (const w of workers.filter((x) => x.driver === d.pane)) { html += row(w, true); placed.add(w.pane); }
    }
    const loose = workers.filter((w) => !placed.has(w.pane));
    if (loose.length) html += `<div class="side-sec" style="padding-top:6px;font-size:10.5px">Workers without a live driver</div>` + loose.map((w) => { placed.add(w.pane); return row(w, true); }).join("");
    const rest = agents.filter((a) => !placed.has(a.pane));
    if (rest.length && placed.size) html += `<div class="side-sec" style="padding-top:6px;font-size:10.5px">Other sessions</div>`;
    html += rest.map((a) => row(a)).join("");
  } else html += agents.map((a) => row(a)).join("");
  html += `</div><div class="side-foot">
    <button class="btn ghost sm icon ${r.view === "settings" ? "on" : ""}" id="sb-gear" title="Settings (⌘,)">${icon("gear")}</button>
    <button class="btn ghost sm icon" id="sb-bell" title="Notifications: what reaches you, and how">${icon("bell")}</button>
    <button class="btn ghost sm icon ${S.summary?.moshi_mode ? "on moshi" : ""}" id="sb-moshi" title="${S.summary?.moshi_mode
      ? "Moshi mode is on: agents put yes/no and multiple-choice questions on your phone. Click to turn it off."
      : "Moshi mode is off. Click to have agents put yes/no and multiple-choice questions on your phone as buttons."}">${icon("phone")}</button>
    <span class="dot ${sum && !sum.herdr_error ? "idle" : "blocked"}" title="${esc(sum?.herdr_error || "herdr connected")}"></span>
    ${window.desk?.showHerdr ? `<a id="sb-herdr" title="Show herdr (⇧⌘H)" style="color:inherit">${sum && !sum.herdr_error ? "herdr" : "herdr offline"}</a>`
      : `<span>${sum && !sum.herdr_error ? "herdr" : "herdr offline"}</span>`}<span class="grow"></span>
    ${sum && sum.dry_run ? `<span class="tag warn" title="Start buttons send nothing">dry run</span>` : ""}</div>`;
  const el = $("#sidebar"), scroll = el.querySelector(".side-scroll")?.scrollTop || 0;
  el.innerHTML = html;
  el.querySelector(".side-scroll").scrollTop = scroll;
  $("#sb-search").onclick = () => hooks.palette();
  $("#sb-new").onclick = () => hooks.newSession(cur);
  if ($("#sb-new2")) $("#sb-new2").onclick = () => hooks.newSession(cur);
  $("#sb-add").onclick = () => hooks.addProject();
  el.querySelectorAll("[data-proj]").forEach((a) => a.onclick = (e) => {
    const name = a.dataset.proj;
    if (e.target.closest("[data-fold]") && name === S.route.project) { e.preventDefault(); return setFold(name, !folded.has(name)); }
    if (name === S.route.project && S.route.view === "project") { e.preventDefault(); return setFold(name, !folded.has(name)); }   // a second click folds
    if (folded.has(name)) setFold(name, false);   // opening a project unfolds it
  });
  $("#sb-moshi").onclick = () => hooks.setMoshiMode(!S.summary?.moshi_mode);
  $("#sb-bell").onclick = () => { S.scrollToNotify = true; if (S.route.view === "settings") $("#notify")?.scrollIntoView({ block: "start", behavior: "smooth" }); else go({ view: "settings" }); };
  $("#sb-gear").onclick = () => (S.route.view === "settings" ? hooks.leaveSettings() : go({ view: "settings" }));
  el.querySelectorAll("[data-milestones]").forEach((a) => a.onclick = () => {
    const show = () => document.getElementById("milestones")?.scrollIntoView({ behavior: "smooth", block: "start" });
    if (S.route.view === "project" && S.route.project === a.dataset.milestones) return show();
    go({ project: a.dataset.milestones }); setTimeout(show, 600);
  });
  if ($("#sb-herdr")) $("#sb-herdr").onclick = () => window.desk.showHerdr();
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
