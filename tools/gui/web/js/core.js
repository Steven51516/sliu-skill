// Shared state, API calls, routing and small rendering helpers. Every other module imports from here.

export const S = {
  summary: null,          // /api/projects: every project's waiting items and agents, plus agents outside projects
  data: null,             // /api/project for the open project
  route: {},
  skills: [],
  chat: { open: false, pane: null },
  sent: new Map(loadMap("sent")),     // pane -> when the human last prompted it from the app (notify when that turn ends)
  unread: new Map(loadMap("unread")), // pane -> {project, label, at}: finished turns not looked at yet
  notes: [],              // recent attention events for the inbox
  prefs: loadPrefs(),
};
export const hooks = {};  // filled by modules to break import cycles: openChat, openTerminal, render, ...

export const $ = (sel, el = document) => el.querySelector(sel);
export const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const isApp = !!window.desk;
if (isApp) document.documentElement.classList.add("app");

function loadMap(key) { try { return JSON.parse(localStorage.getItem("rd." + key) || "[]"); } catch (_) { return []; } }
export function saveAttention() {
  try { localStorage.setItem("rd.sent", JSON.stringify([...S.sent])); localStorage.setItem("rd.unread", JSON.stringify([...S.unread])); }
  catch (_) { /* private mode */ }
}
export function markSent(pane) { S.sent.set(pane, Date.now()); saveAttention(); }

function loadPrefs() {
  const d = { verbose: false };
  try { return { ...d, ...JSON.parse(localStorage.getItem("rd.prefs") || "{}") }; }
  catch (_) { return d; }
}
export function savePrefs() { try { localStorage.setItem("rd.prefs", JSON.stringify(S.prefs)); } catch (_) { /* private mode */ } }
export function store(key, val) { try { if (val === undefined) return JSON.parse(localStorage.getItem("rd." + key)); localStorage.setItem("rd." + key, JSON.stringify(val)); } catch (_) { return null; } }

// every /api and /ws call carries the backend's per-launch token; a restarted backend has a new one, so refetch once
let TOKEN = null;
export async function token(fresh = false) {
  if (!TOKEN || fresh) TOKEN = (await (await fetch("/api/token")).json()).token;
  return TOKEN;
}
export const tokenNow = () => TOKEN;
async function call(make) {
  let r = await make(await token());
  if (r.status === 403) r = await make(await token(true));
  const j = await r.json().catch(() => ({ error: `HTTP ${r.status}` }));
  if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
  return j;
}
export const get = (path, params = {}) => call((t) => fetch(path + "?" + new URLSearchParams(params), { headers: { "X-RG-Token": t } }));
export const post = (path, body) => call((t) => fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "X-RG": "1", "X-RG-Token": t }, body: JSON.stringify(body) }));

export function toast(msg, kind = "", ms = 3200) {
  const t = document.createElement("div");
  t.className = "toast " + kind;
  t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), ms);
}

export const fmtSize = (n) => n == null ? "" : n < 1024 ? `${n} B` : n < 1 << 20 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(1)} MB`;
export function ago(ts) {
  if (!ts) return "";
  const t = typeof ts === "number" ? ts * (ts < 1e12 ? 1000 : 1) : Date.parse(ts);
  const s = (Date.now() - t) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}
const KNOWN = ["open", "claimed", "running", "held", "resolved", "parked", "superseded", "closed", "paused", "working", "idle", "done", "blocked", "unknown", "waiting"];
export const scls = (s) => "s-" + (KNOWN.includes(s) ? s : "other");
export const safeCls = (s) => String(s ?? "").replace(/[^\w-]/g, "");
export const pill = (s, text) => `<span class="pill ${scls(s)}">${esc(text ?? s)}</span>`;
export const AGENT_WORD = { blocked: "needs you", working: "working", idle: "idle", done: "done", unknown: "unknown" };
export const fmtDur = (s) => s < 60 ? `${s} s` : s < 3600 ? `${Math.floor(s / 60)} min` : `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
// "Codex running · 9 min" when the agent's delegated Codex job is still going (its own screen may say idle)
// an Opus safeguard flag in the last two hours (biology work trips them falsely now and then)
// the model a session answers with: a quiet tag, amber when it is not the newest Opus in use (team-watch moves stuck
// drivers to Sonnet; Claude's safeguards can switch a session to an older Opus)
const opusVer = (m) => { const r = /^opus\s+(\d+(?:\.\d+)?)/i.exec(m || ""); return r ? parseFloat(r[1]) : null; };
export const modelOff = (a) => {
  if (!a?.model) return false;
  const v = opusVer(a.model), top = Math.max(0, ...allAgents().map((x) => opusVer(x.model) || 0));
  return v === null || v < top;
};
export const modelTag = (a) => a?.model ? `<span class="mtag ${modelOff(a) ? "alt" : ""}" title="answering with ${esc(a.model)}">${esc(a.model.replace(/\s*\(.*\)$/, ""))}</span>` : "";
// Claude Code's own "API Error: ..." reply, until a real reply follows (an account block stops every loop)
export const apiNote = (a) => a?.api_error ? `⚠ API error: ${(a.api_error.text || "").replace(/^API Error:\s*/i, "").split(/\. /)[0]}` : "";
export const guardNote = (a) => {
  if (apiNote(a)) return apiNote(a);
  const g = a?.safeguard;
  if (!g || Date.now() - Date.parse(g.ts) > 2 * 3600 * 1000) return "";
  return g.kind === "fallback" ? "⚠ Opus safeguards: an older model is answering" : "⚠ Opus safeguards stopped a reply";
};
// a driver's /loop: when its next pass is due, or that it has gone quiet (missed a pass, or a pass died)
const hhmm = (iso) => iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
export const loopNote = (a) => {
  const l = a?.loop;
  if (!l) return "";
  if (a.api_error && l.state !== "ended") return apiNote(a);
  return { scheduled: `next pass ${l.fallback ? "~" : ""}${hhmm(l.due)}`, running: "pass running",
    missed: l.fired && !l.fallback ? `⚠ loop pass from ${hhmm(l.fired)} still running` : `⚠ loop missed its ${hhmm(l.due)} pass`, ended: "loop ended" }[l.state] || "";
};
export const loopDead = (a) => a?.loop?.state === "missed" || (!!a?.api_error && !!a?.loop && a.loop.state !== "ended");
export const codexNote = (a) => a?.codex?.length ? `Codex running · ${fmtDur(Math.max(...a.codex.map((r) => r.seconds)))}` : "";

// ---------- routing: #/inbox  #/gpus  #/settings  #/p/<project>[/files | /map/<folder>[/<tab>[/<ticket>]]] ----------

export function parseRoute() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
  if (parts[0] !== "p") return { view: parts[0] || "inbox" };
  const r = { view: "project", project: parts[1] };
  if (parts[2] === "files") r.view = "files";
  if (parts[2] === "search") r.view = "search";
  if (parts[2] === "map") Object.assign(r, { view: "map", map: parts[3], tab: parts[4] || "dag", ticket: parts[5] || null });
  return r;
}
export function href(r) {
  if (!r.project) return "#/" + (r.view || "inbox");
  const parts = ["p", r.project];
  if (r.view === "files") parts.push("files");
  if (r.view === "search") parts.push("search");
  if (r.map) parts.push("map", r.map, r.tab || "dag", ...(r.ticket ? [r.ticket] : []));
  return "#/" + parts.map(encodeURIComponent).join("/");
}
export function go(r) { location.hash = href(r); }
export const goProject = (name) => go({ project: name });
export const goMap = (project, map, ticket = null, tab = "dag") => go({ project, view: "map", map, tab, ticket });

// ---------- lookups ----------

export const projectSummary = (name) => S.summary?.projects.find((p) => p.name === name);
export function allAgents() {
  const out = [];
  (S.summary?.projects || []).forEach((p) => (p.agents || []).forEach((a) => out.push({ ...a, project: p.name })));
  (S.summary?.other_agents || []).forEach((a) => out.push({ ...a, project: null }));
  return out;
}
export const agentByPane = (pane) => allAgents().find((a) => a.pane === pane);
export function agentLabel(a) {
  if (!a) return "agent";
  if (a.remote) return a.title || "Claude session";          // a session on a remote host: its conversation's title
  if (a.role === "worker" && a.ticket) return `Worker · ${a.ticket}`;
  if (a.role === "driver" && a.drives) return `Driver · ${a.drives}`;
  const role = a.role ? a.role[0].toUpperCase() + a.role.slice(1) : (a.agent || "agent");
  const tab = a.tab_label && !/^\d+$/.test(a.tab_label) && !a.tab_label.toLowerCase().includes(a.role || "\0") ? ` · ${a.tab_label}` : "";
  return role + tab;
}
export function avatar(a) {
  const role = a?.role || "";
  const letter = role === "desk" ? "D" : role === "driver" ? "B" : role === "implementer" || role === "worker" ? "W" : a?.agent === "codex" ? "X" : "C";
  const cls = role === "desk" ? "desk" : role === "driver" ? "driver" : a?.agent === "codex" ? "codex" : "";
  return `<span class="avatar ${cls}">${letter}</span>`;
}

// ---------- markdown ----------

export function md(el, text, opt = {}) {
  let fm = "";
  const m = text.match(/^---\n([\s\S]*?)\n---\n?/);
  if (m && opt.frontMatter !== false) {
    text = text.slice(m[0].length);
    const skip = new Set(opt.skipKeys || []);
    if (opt.frontMatter !== "hide") {
      const rows = m[1].split("\n").filter((l) => /^[\w-]+:/.test(l) && !skip.has(l.split(":")[0])).map((l) => {
        const i = l.indexOf(":"), v = l.slice(i + 1).trim().replace(/^"(.*)"$/, "$1");
        return v && v !== "null" && v !== "[]" ? `<span class="k">${esc(l.slice(0, i))}</span><span class="v">${esc(v)}</span>` : "";
      }).join("");
      fm = !rows ? "" : opt.frontMatter === "details" ? `<details class="fmd"><summary>Details</summary><div class="fm">${rows}</div></details>` : `<div class="fm">${rows}</div>`;
    }
  }
  // GFM strikes through ~single~ tildes; notes use ~ for "about", so only ~~ strikes (code left alone)
  text = text.split(/(```[\s\S]*?```|`[^`\n]*`)/).map((seg, i) => i % 2 ? seg : seg.replace(/(^|[^~\\])~(?=[^~]|$)/g, "$1\\~")).join("");
  el.classList.add("md");
  el.innerHTML = fm + DOMPurify.sanitize(marked.parse(text, { gfm: true, breaks: !!opt.breaks }), { SANITIZE_NAMED_PROPS: true });
  if (opt.dropTitle) el.querySelector(":scope > h1:first-of-type")?.remove();   // the panel header already shows it
  el.querySelectorAll("pre code").forEach((c) => { if (c.textContent.length < 150000) hljs.highlightElement(c); });
  const proj = opt.project || (S.data && { name: S.data.name, path: S.data.path });
  if (opt.paths && proj) {                      // project paths in `code` open in the file viewer
    const root = proj.path + "/";
    el.querySelectorAll(":not(pre) > code").forEach((c) => {
      const t = c.textContent.trim();
      const rel = t.startsWith(root) ? t.slice(root.length) : /^(maps|tracks|docs|resources|scratch|common|lit)\//.test(t) ? t : null;
      if (!rel || /\s/.test(rel)) return;
      c.classList.add("pathlink");
      c.title = "Open in the file viewer";
      c.onclick = () => hooks.openPath(proj.name, rel.replace(/\/$/, ""));
    });
  }
  el.querySelectorAll("a[href]").forEach((a) => {
    const h = a.getAttribute("href");
    if (/^https?:/i.test(h)) { a.target = "_blank"; a.rel = "noreferrer"; return; }
    a.onclick = (e) => {                      // relative links open in the app; they never navigate the window
      e.preventDefault();
      if (h.startsWith("#") || /^[a-z]+:/i.test(h)) return;
      if (opt.onLink) return opt.onLink(h);
      const rel = h.split("#")[0];
      if (proj && rel) hooks.openPath(proj.name, rel.startsWith(proj.path + "/") ? rel.slice(proj.path.length + 1) : rel.replace(/^\.\//, ""));
    };
  });
  return el;
}
export function resolvePath(dir, rel) {
  const out = dir ? dir.split("/") : [];
  rel.split("/").forEach((p) => { if (p === "..") out.pop(); else if (p && p !== ".") out.push(p); });
  return out.join("/");
}

// ---------- icons (inline SVG, stroke = currentColor) ----------

const P = {
  inbox: '<path d="M3 13h4l2 3h6l2-3h4"/><path d="M5 5h14l2 8v6H3v-6z"/>',
  gpu: '<rect x="4" y="6" width="16" height="12" rx="2"/><path d="M8 10h8v4H8zM2 9h2M2 15h2M20 9h2M20 15h2"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
  map: '<circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="12" r="2.5"/><path d="M8.5 6.5 15.6 11M8.5 17.5l7.1-4.5"/>',
  home: '<path d="M4 11 12 4l8 7v8a1 1 0 0 1-1 1h-5v-6h-4v6H5a1 1 0 0 1-1-1z"/>',
  chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.4A8 8 0 1 1 21 12z"/>',
  term: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3M13 15h4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  play: '<path d="M7 5v14l11-7z"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  send: '<path d="M12 19V5M5 12l7-7 7 7"/>',
  stop: '<rect x="7" y="7" width="10" height="10" rx="1.5"/>',
  ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  code: '<path d="m8 8-4 4 4 4M16 8l4 4-4 4M14 5l-4 14"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6"/>',
  server: '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01"/>',
  bolt: '<path d="M13 3 4 14h7l-1 7 9-11h-7z"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M21.5 20a6.5 6.5 0 0 0-4-6"/>',
  side: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/>',
  bottom: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 14h18"/>',
  more: '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>',
  check: '<path d="m5 12 5 5 9-10"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
  doc: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5M10 13h6M10 17h6"/>',
  phone: '<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
  belloff: '<path d="M6 16V11a6 6 0 0 1 9.5-4.9M18 11v5l1.5 2H8"/><path d="M10 20a2 2 0 0 0 4 0M4 4l16 16"/>',
  bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
};
export const icon = (name, cls = "") => `<svg class="ico ${cls}" viewBox="0 0 24 24">${P[name] || ""}</svg>`;

// ---------- small menus ----------

export function popMenu(anchor, items, opt = {}) {
  closeMenus();
  const m = document.createElement("div");
  m.className = "menu";
  m.innerHTML = items.map((it, i) => it === "-" ? `<div class="sep"></div>` : it.header ? `<div class="mh">${esc(it.header)}</div>`
    : `<div class="mi" data-i="${i}">${it.icon ? icon(it.icon) : ""}<span class="a" style="font-family:var(--font);font-weight:500">${esc(it.label)}</span>${it.hint ? `<span class="b">${esc(it.hint)}</span>` : ""}</div>`).join("");
  document.body.appendChild(m);
  const r = anchor.getBoundingClientRect(), w = m.offsetWidth, h = m.offsetHeight;
  m.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, opt.right ? r.right - w : r.left)) + "px";
  m.style.top = (r.bottom + h + 6 > window.innerHeight ? Math.max(8, r.top - h - 4) : r.bottom + 4) + "px";
  m.querySelectorAll(".mi").forEach((el) => el.onclick = () => { closeMenus(); items[+el.dataset.i].run(); });
  setTimeout(() => document.addEventListener("mousedown", outside), 0);
  function outside(e) { if (!m.contains(e.target)) closeMenus(); }
  m._outside = outside;
  return m;
}
export function closeMenus() {
  $$(".menu.pop, body > .menu").forEach((m) => { document.removeEventListener("mousedown", m._outside); m.remove(); });
}
