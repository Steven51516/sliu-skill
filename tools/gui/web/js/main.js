// Entry point: routing, the 4-second poll, attention (notifications, dock badge, title), keyboard, module wiring.
import { S, $, get, hooks, parseRoute, go, store, isApp, agentLabel, allAgents, closeMenus, toast } from "./core.js";
import { renderSidebar, initSidebarResize, inboxCount } from "./sidebar.js";
import { renderView, renderTitlebar, renderInbox } from "./views.js";
import { openChat, closeChat, toggleChat, initChatResize, refreshChatHead, deskPane } from "./chat.js";
import { initDock, toggleDock } from "./term.js";
import { startTeam, newSession, addProject, shortcuts, closeDialog, peekJob } from "./dialogs.js";
import { palette } from "./palette.js";
import { resetFiles, openPathLater } from "./files.js";
import { resetMap } from "./map.js";

const POLL_MS = 4000;
let lastSig = "", prevStatus = new Map(), prevStates = null, polling = false, lastAttention = "";

Object.assign(hooks, {
  openChat, toggleChat, toggleDock, startTeam, newSession, addProject, shortcuts, palette, deskPane, peekJob,
  sidebar: () => renderSidebar(), refresh: () => poll(true), badge,
  openPath: (project, rel, side = "local") => { openPathLater(side, rel); go({ project, view: "files" }); },
});

async function route() {
  const prev = S.route;
  S.route = parseRoute();
  if (!location.hash) {
    const last = store("project");
    return go(last && S.summary?.projects.some((p) => p.name === last) ? { project: last } : { view: "inbox" });
  }
  if (S.route.project) store("project", S.route.project);
  if (S.route.project !== prev.project) { S.data = null; lastSig = ""; resetFiles(); resetMap(); }
  else if (S.route.map !== prev.map) { resetFiles(); resetMap(); }
  closeMenus();
  renderSidebar();
  renderView(true);
  if (S.route.project && (!S.data || S.data.name !== S.route.project)) { await loadProject(); renderSidebar(); renderView(true); }
}

async function loadProject() {
  const name = S.route.project;
  if (!name) return false;
  try {
    const d = await get("/api/project", { name });
    if (name !== S.route.project) return false;
    const sig = JSON.stringify(d);
    S.err = null;
    if (sig === lastSig) return false;
    S.data = d; lastSig = sig;
    return true;
  } catch (e) { S.err = e.message; S.data = null; return true; }
}

let again = false;
async function poll(force = false) {
  if (polling) { if (force) again = true; return; }
  polling = true;
  try {
    const sum = await get("/api/projects");
    S.summary = sum;
    attention(sum);
    const changed = await loadProject();
    renderSidebar();
    refreshChatHead();
    renderTitlebar();
    if (changed && S.route.view !== "gpus" && S.route.view !== "settings") renderView(false);
    else if (S.route.view === "inbox") renderInbox();
  } catch (e) {
    S.summary = S.summary || null;
    $("#titlebar .crumbs") && toastOnce("The backend is not answering: " + e.message);
  } finally { polling = false; if (again) { again = false; poll(); } }
}

let lastToast = 0;
function toastOnce(msg) { if (Date.now() - lastToast > 30000) { lastToast = Date.now(); toast(msg, "err", 6000); } }

// ---------- attention ----------

function looking(pane) { return document.hasFocus() && S.chat.open && S.chat.pane === pane; }

function attention(sum) {
  const now = new Map();
  allAgents().forEach((a) => {
    now.set(a.pane, a.status);
    const before = prevStatus.get(a.pane);
    if (before === undefined && prevStatus.size === 0) return;   // first poll: no history
    if (a.status === "blocked" && before !== "blocked") {
      note("blocked", `${agentLabel(a)}${a.project ? " · " + a.project : ""} needs your answer`);
      if (S.prefs.notifyPrompt && !looking(a.pane)) notify(`${agentLabel(a)} needs your answer`, a.project ? `${a.project} · ${a.title || ""}` : a.title || "", a.pane);
    }
    if (S.sent.has(a.pane) && before === "working" && ["idle", "done"].includes(a.status)) {
      S.sent.delete(a.pane);
      note("idle", `${agentLabel(a)} finished its turn`);
      if (!looking(a.pane)) {
        S.unread.set(a.pane, { project: a.project, label: agentLabel(a), at: Date.now(), text: a.title });
        if (S.prefs.notifyDone) notify(`${agentLabel(a)} finished`, a.project ? `${a.project} · ${a.title || ""}` : a.title || "", a.pane);
      }
    }
  });
  for (const pane of [...S.unread.keys()]) if (!now.has(pane)) S.unread.delete(pane);
  prevStatus = now;
  progress(sum);
  badge();
}

const NEWS = { resolved: "resolved", parked: "parked", held: "held", closed: "closed", running: "started running", paused: "paused" };
function progress(sum) {
  // ticket and map changes in any project while the app is open (what changed while away is on each overview)
  const now = {};
  sum.projects.forEach((p) => { now[p.name] = p.states || {}; });
  if (prevStates) for (const [proj, states] of Object.entries(now)) {
    const before = prevStates[proj];
    if (!before) continue;
    for (const [id, [st, title]] of Object.entries(states)) {
      const old = before[id]?.[0];
      if (old === st) continue;
      const what = id.startsWith("map:") ? `Map ${id.slice(4)}` : id;
      const verb = old === undefined ? "was added" : NEWS[st] || `is now ${st}`;
      note(st === "resolved" || st === "closed" ? "idle" : "working", `${proj} · ${what} ${verb}: ${title}`);
      if (S.prefs.notifyProgress && (NEWS[st] || old === undefined) && !(document.hasFocus() && S.route.project === proj))
        notify(`${what} ${verb}`, `${proj} · ${title}`, null, { project: proj, map: states[id][2], ticket: states[id][3] });
    }
  }
  prevStates = now;
}

function note(kind, text) { S.notes.unshift({ kind, text, at: Date.now() }); S.notes.length = Math.min(S.notes.length, 50); }

function notify(title, body, pane, where = null) {
  try {
    if (!("Notification" in window) || Notification.permission === "denied") return;
    if (Notification.permission === "default") { Notification.requestPermission(); return; }
    const n = new Notification(title, { body, silent: false });
    n.onclick = () => {
      window.focus(); if (isApp) window.desk.focus();
      if (pane) openChat(pane);
      else if (where) go({ project: where.project, view: "map", map: where.map, tab: "dag", ticket: where.ticket });
    };
  } catch (_) { /* notifications unavailable */ }
}

function badge() {
  const blocked = allAgents().filter((a) => a.status === "blocked").length;
  const n = blocked + S.unread.size;
  document.title = n ? `(${n}) Research Desk` : "Research Desk";
  if (isApp) {
    window.desk.setBadge(n);
    const items = [
      ...allAgents().filter((a) => a.status === "blocked").map((a) => ({ label: `● ${agentLabel(a)}${a.project ? " · " + a.project : ""} needs your answer`, cmd: "openChat", arg: a.pane })),
      ...[...S.unread.entries()].map(([pane, u]) => ({ label: `✓ ${u.label}${u.project ? " · " + u.project : ""} finished`, cmd: "openChat", arg: pane })),
      ...(S.summary?.projects || []).flatMap((p) => (p.waiting || []).filter((w) => w.kind === "ticket").map((w) => ({ label: `◆ ${p.name} · ${w.id}: ${w.text}`, cmd: "goTicket", arg: [p.name, w.map_folder, w.folder] }))),
    ];
    const sig = JSON.stringify(items);
    if (window.desk.attention && sig !== lastAttention) { lastAttention = sig; window.desk.attention(items); }
  }
  void inboxCount;
}

// ---------- keyboard ----------

const COMMANDS = {
  palette: () => palette(), chat: () => toggleChat(), dock: () => toggleDock(), newSession: () => newSession(S.route.project),
  inbox: () => go({ view: "inbox" }), settings: () => go({ view: "settings" }), shortcuts: () => shortcuts(),
  gpus: () => go({ view: "gpus" }), refresh: () => poll(true),
};
function project(i) { const p = S.summary?.projects[i]; if (p) go({ project: p.name }); }

document.addEventListener("keydown", (e) => {
  const mod = e.metaKey || e.ctrlKey;
  if (e.key === "Escape") { if (!$("#overlay").hidden) { closeDialog(); e.preventDefault(); } closeMenus(); return; }
  if (e.ctrlKey && e.key === "Tab") {                       // next session in the chat
    e.preventDefault();
    const list = allAgents().filter((a) => !S.route.project || a.project === S.route.project);
    if (!list.length) return;
    const i = list.findIndex((a) => a.pane === S.chat.pane);
    openChat(list[(i + (e.shiftKey ? -1 : 1) + list.length) % list.length].pane, { focus: false });
    return;
  }
  if (isApp) return;                                       // the app's menu owns the ⌘ shortcuts
  if (!mod) return;
  const k = e.key.toLowerCase();
  const map = { k: "palette", j: "chat", n: "newSession", i: "inbox", ",": "settings", "/": "shortcuts", g: "gpus" };
  if (e.ctrlKey && e.key === "`") { e.preventDefault(); return toggleDock(); }
  if (map[k] && e.metaKey) { e.preventDefault(); COMMANDS[map[k]](); }
  else if (e.metaKey && /^[1-9]$/.test(k)) { e.preventDefault(); project(+k - 1); }
});

if (isApp) window.desk.onCommand((cmd, arg) => {
  if (cmd === "project") return project(arg);
  if (cmd === "openChat") return openChat(arg);
  if (cmd === "goTicket") return go({ project: arg[0], view: "map", map: arg[1], tab: "dag", ticket: arg[2] });
  (COMMANDS[cmd] || (() => {}))();
});

// ---------- start ----------

(async function init() {
  initDock();
  initSidebarResize();
  initChatResize();
  get("/api/skills").then((j) => { S.skills = j.skills; }).catch(() => {});
  await poll(true);
  window.addEventListener("hashchange", route);
  await route();
  setInterval(poll, POLL_MS);
  if (store("chatOpen")) openChat(null, { focus: false });
  window.addEventListener("beforeunload", () => store("chatOpen", S.chat.open));
  void closeChat;
})();
