// Entry point: routing, the 4-second poll, attention (notifications, dock badge, title), keyboard, module wiring.
import { S, $, get, post, hooks, parseRoute, go, store, isApp, agentLabel, allAgents, closeMenus, toast, saveAttention } from "./core.js";
import { renderSidebar, initSidebarResize, inboxCount } from "./sidebar.js";
import { renderView, renderTitlebar, renderInbox } from "./views.js";
import { openChat, closeChat, toggleChat, initChatResize, refreshChatHead, deskPane, askProject, askLabel, openArchive } from "./chat.js";
import { initDock, toggleDock, typeIntoTerminal } from "./term.js";
import { startTeam, newSession, addProject, newProject, shortcuts, closeDialog, peekJob } from "./dialogs.js";
import { palette } from "./palette.js";
import { resetFiles, openPathLater, openFile } from "./files.js";
import { resetMap } from "./map.js";

const POLL_MS = 4000;
let lastSig = "", polling = false, lastAttention = "";

Object.assign(hooks, {
  openChat, toggleChat, toggleDock, startTeam, newSession, addProject, newProject, shortcuts, palette, deskPane, peekJob, askProject, askLabel, openArchive,
  sidebar: () => renderSidebar(), refresh: () => poll(true), badge,
  nextAttention,
  setMoshiMode: async (on) => {
    try { await post("/api/moshi-mode", { on }); toast(on ? "Moshi mode on: yes/no and multiple-choice questions go to your phone" : "Moshi mode off: agents ask in the chat"); }
    catch (e) { toast(e.message, "err"); }
    poll(true);
  },
  openPath: (project, rel, side = "local") => {
    if (S.route.view === "files" && S.route.project === project && document.getElementById("viewer")) return openFile(side, rel);
    openPathLater(side, rel); go({ project, view: "files" });
  },
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
    const sig = JSON.stringify(d), wasErr = !!S.err;
    S.err = null;
    if (sig === lastSig && S.data && !wasErr) return false;
    S.data = d; lastSig = sig;
    return true;
  } catch (e) {
    if (name !== S.route.project) return false;
    S.err = e.message;                       // keep showing the last good data; a toast says the backend failed
    if (!S.data || S.data.name !== name) { S.data = null; lastSig = ""; }
    toastOnce("Couldn't refresh " + name + ": " + e.message);
    return true;
  }
}

let again = false;
async function poll(force = false) {
  if (polling) { if (force) again = true; return; }
  polling = true;
  try {
    const sum = await get("/api/projects");
    S.summary = sum;
    attention();
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

// Events (a prompt, a reply, a quiet loop, a safeguard flag, a decision, a result) are detected by the backend, which
// also plays their sounds and sends their pushes (rg_notify), so they work with this window closed. Here they become
// banners, inbox notes and unread replies.
let evSeq = null;
const NOTE_KIND = { prompt: "blocked", loop: "blocked", safeguard: "blocked", decision: "blocked", reply: "idle", desk_reply: "idle",
  any_reply: "idle", result: "idle", progress: "working" };
async function events() {
  let r;
  try { r = await get("/api/events", { after: evSeq ?? 0 }); } catch (_) { return; }
  if (evSeq === null) { evSeq = r.last; return; }          // first look: no replay of what happened before the page loaded
  evSeq = r.last;
  for (const e of r.events) {
    note(NOTE_KIND[e.kind] || "idle", e.title);
    if (e.kind === "reply" && e.pane && !looking(e.pane)) S.unread.set(e.pane, { project: e.project, label: e.title.replace(/ replied.*$/, ""), at: Date.now(), text: e.body });
    if (e.channels.includes("banner") && !(e.pane && looking(e.pane))) notify(e.title, e.body, e.pane || null, e.map ? { project: e.project, map: e.map, ticket: e.ticket } : null);
  }
}

function attention() {
  const live = new Set(allAgents().map((a) => a.pane));
  for (const pane of [...S.unread.keys()]) if (!live.has(pane)) S.unread.delete(pane);
  saveAttention();
  events().then(badge);
  badge();
}

function note(kind, text) { S.notes.unshift({ kind, text, at: Date.now() }); S.notes.length = Math.min(S.notes.length, 50); }

function notify(title, body, pane, where = null) {
  try {
    if (!("Notification" in window) || Notification.permission === "denied") return;
    if (Notification.permission === "default") { Notification.requestPermission(); return; }
    const n = new Notification(title, { body, silent: true });   // the sound is its own channel (rg_notify plays it)
    n.onclick = () => {
      window.focus(); if (isApp) window.desk.focus();
      if (pane) openChat(pane);
      else if (where) go({ project: where.project, view: "map", map: where.map, tab: "dag", ticket: where.ticket });
    };
  } catch (_) { /* notifications unavailable */ }
}

function badge() {
  const blocked = allAgents().filter((a) => a.status === "blocked").length;
  const n = blocked;                                   // replies to you are not waiting on you
  document.title = n ? `(${n}) Research Desk` : "Research Desk";
  if (isApp) {
    window.desk.setBadge(n);
    const items = [
      ...allAgents().filter((a) => a.status === "blocked").map((a) => ({ label: `● ${agentLabel(a)}${a.project ? " · " + a.project : ""} needs your answer`, cmd: "openChat", arg: a.pane })),
      ...allAgents().filter((a) => a.loop?.state === "missed").map((a) => ({ label: `↻ ${agentLabel(a)}${a.project ? " · " + a.project : ""}: loop ${a.loop.state}`, cmd: "openChat", arg: a.pane })),
      ...(S.summary?.projects || []).flatMap((p) => (p.waiting || []).filter((w) => w.kind === "ticket").map((w) => ({ label: `◆ ${p.name} · ${w.id}: ${w.text}`, cmd: "goTicket", arg: [p.name, w.map_folder, w.folder] }))),
    ];
    const sig = JSON.stringify(items);
    if (window.desk.attention && sig !== lastAttention) { lastAttention = sig; window.desk.attention(items); }
  }
  void inboxCount;
}

// the next thing that needs you, in turn: an agent at a prompt, then a decision ticket
let attnIndex = 0;
function nextAttention() {
  const items = [
    ...allAgents().filter((a) => a.status === "blocked").map((a) => () => openChat(a.pane)),
    ...(S.summary?.projects || []).flatMap((p) => (p.waiting || []).filter((w) => w.kind !== "agent")
      .map((w) => () => go({ project: p.name, view: "map", map: w.map_folder, tab: "dag", ticket: w.folder || null }))),
  ];
  if (!items.length) return toast("Nothing needs you right now");
  items[attnIndex++ % items.length]();
}

let beforeSettings = null;
window.addEventListener("hashchange", (e) => { if (S.route.view !== "settings" && !location.hash.startsWith("#/settings")) beforeSettings = null;
  else if (!beforeSettings && e.oldURL && !e.oldURL.includes("#/settings")) beforeSettings = e.oldURL.split("#")[1] || ""; });
function leaveSettings() { location.hash = beforeSettings ? "#" + beforeSettings : (store("project") ? `#/p/${encodeURIComponent(store("project"))}` : "#/inbox"); }
hooks.leaveSettings = leaveSettings;

// ---------- keyboard ----------

const COMMANDS = {
  palette: () => palette(), chat: () => toggleChat(), dock: () => toggleDock(), newSession: () => newSession(S.route.project),
  inbox: () => go({ view: "inbox" }), settings: () => go({ view: "settings" }), shortcuts: () => shortcuts(),
  gpus: () => go({ view: "gpus" }), refresh: () => poll(true), next: () => nextAttention(),
};
function project(i) { const p = S.summary?.projects[i]; if (p) go({ project: p.name }); }

document.addEventListener("keydown", (e) => {
  const mod = e.metaKey || e.ctrlKey;
  if (e.key === "Enter" && e.target.matches?.(".agent-row, .trow")) { e.preventDefault(); e.target.click(); return; }
  if (e.key === "Escape") {
    if (!$("#overlay").hidden) { closeDialog(); e.preventDefault(); }
    else if (S.route.view === "settings" && !e.target.closest?.("textarea, input")) leaveSettings();
    closeMenus(); return;
  }
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
  if (e.metaKey && e.shiftKey && k === "a") { e.preventDefault(); return nextAttention(); }
  if (map[k] && e.metaKey) { e.preventDefault(); COMMANDS[map[k]](); }
  else if (e.metaKey && /^[1-9]$/.test(k)) { e.preventDefault(); project(+k - 1); }
});

if (isApp) window.desk.onCommand((cmd, arg) => {
  if (cmd === "project") return project(arg);
  if (cmd === "openChat") return openChat(arg);
  if (cmd === "goTicket") return go({ project: arg[0], view: "map", map: arg[1], tab: "dag", ticket: arg[2] });
  (COMMANDS[cmd] || (() => {}))();
});

// ---------- dropping files: their paths are typed where they land, as in Terminal ----------

const shellPath = (p) => p.replace(/([\s'"()&;|<>$`\\!*?[\]{}#~^])/g, "\\$1");
const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");

function insertAt(field, text) {
  const s = field.selectionStart ?? field.value.length, end = field.selectionEnd ?? s;
  const before = field.value.slice(0, s), pad = before && !/\s$/.test(before) ? " " : "";
  field.value = before + pad + text + field.value.slice(end);
  const pos = (before + pad + text).length;
  field.setSelectionRange(pos, pos);
  field.focus();
  field.dispatchEvent(new Event("input", { bubbles: true }));   // autosize, draft, menus
}

document.addEventListener("dragover", (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = "copy";
  document.body.classList.add("dragging");
});
document.addEventListener("dragleave", (e) => { if (!e.relatedTarget) document.body.classList.remove("dragging"); });
document.addEventListener("drop", (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  document.body.classList.remove("dragging");
  const paths = [...e.dataTransfer.files].map((f) => (window.desk?.pathForFile ? window.desk.pathForFile(f) : "")).filter(Boolean);
  if (!paths.length) return toast(isApp ? "Couldn't read the dropped file's path" : "Dropped files give their path only in the app (a browser hides it)", "err", 5000);
  const text = paths.map(shellPath).join(" ") + " ";
  const term = e.target.closest?.(".term");
  if (term && typeIntoTerminal(term, text)) return;
  const field = e.target.closest?.("textarea, input:not([type]), input[type=text], input[type=search]");
  if (field && !field.disabled) return insertAt(field, text);
  if (!S.chat.open || !$("#composer")) openChat(S.chat.pane, { focus: false });
  setTimeout(() => { const c = $("#composer"); if (c && !c.disabled) insertAt(c, text); else toast("No agent to drop the path into: open a chat first", "err"); }, 60);
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
  window.rdReady = true;                                // boot.js stops watching
  try { sessionStorage.removeItem("rd.boot"); } catch (_) { /* no storage */ }
  setInterval(poll, POLL_MS);
  if (store("chatOpen")) openChat(null, { focus: false });
  window.addEventListener("beforeunload", () => store("chatOpen", S.chat.open));
  void closeChat;
})();
