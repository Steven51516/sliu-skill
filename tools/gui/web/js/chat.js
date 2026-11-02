// Chat with any live agent: its Claude Code transcript rendered, prompts answered from the exact screen, messages sent
// through herdr. Polls fast while the agent works or waits, slowly while it is idle.
import { S, $, esc, get, post, toast, icon, md, hooks, agentByPane, agentLabel, avatar, allAgents, AGENT_WORD, popMenu, store, savePrefs, codexNote, markSent, modelTag } from "./core.js";

const C = S.chat;
Object.assign(C, { items: [], tools: new Map(), offset: null, session: null, status: null, timer: null, queued: [], busy: false, seq: 0, turnFiles: new Set() });

export function openChat(pane, opt = {}) {
  const a = pane && agentByPane(pane);
  if (!pane || (!a && !(pane === C.pane && C.status === "ended"))) pane = defaultPane();   // an ended chat stays readable
  C.open = true;
  $("#chat").hidden = false;
  $("#chat-resize").hidden = false;
  if (pane !== C.pane) switchTo(pane);
  else { render(); poll(); }
  S.unread.delete(pane);
  hooks.sidebar && hooks.sidebar();
  if (opt.text != null) setComposer(opt.text);
  if (opt.focus !== false) setTimeout(() => $("#composer")?.focus(), 30);
}
export function closeChat() {
  C.open = false;
  $("#chat").hidden = true;
  $("#chat-resize").hidden = true;
  clearTimeout(C.timer);
  hooks.sidebar && hooks.sidebar();
}
export function toggleChat() { C.open ? closeChat() : openChat(C.pane); }

function defaultPane() {
  // the desk is who you talk to; without one, the session you last talked to here, else one waiting for you
  const proj = S.route.project;
  const agents = allAgents().filter((a) => !proj || a.project === proj);
  const desk = agents.find((a) => a.role === "desk");
  if (desk) return desk.pane;
  const remembered = proj && store("chat." + proj);
  if (remembered && agents.some((a) => a.pane === remembered)) return remembered;
  return (agents.find((a) => a.status === "blocked") || agents[0] || {}).pane || null;
}
export function deskPane(project) {
  const a = allAgents().find((x) => x.project === project && x.role === "desk");
  return a ? a.pane : null;
}

// Not every project runs a team: questions go to its desk if there is one, else to its most recently active
// session, else to a new session started with the text
export function askProject(project, text = "") {
  const desk = deskPane(project);
  if (desk) return openChat(desk, { text });
  const mine = allAgents().filter((a) => a.project === project);
  const recent = mine.sort((a, b) => (Date.parse(b.turn_end || 0) || 0) - (Date.parse(a.turn_end || 0) || 0))[0];
  if (recent) return openChat(recent.pane, { text });
  hooks.newSession(project, "custom", { text });
}
export const askLabel = (project) => (deskPane(project) ? "Ask the desk" : "Ask Claude");

// a saved conversation around one message (a search hit), read-only
export function openArchive(session, uuid, opt = {}) {
  C.open = true;
  $("#chat").hidden = false;
  $("#chat-resize").hidden = false;
  switchTo("session:" + session);
  Object.assign(C, { around: uuid, label: opt.title || "Saved conversation", project: opt.project || S.route.project, livePane: opt.live_pane || null });
  render();
  poll();
}

function switchTo(pane) {
  clearTimeout(C.timer);
  Object.assign(C, { pane, items: [], tools: new Map(), offset: null, session: null, status: null, queued: [], screen: null, fallback: null, cut: false, err: null,
    around: null, livePane: null, turnFiles: new Set() });
  const a = agentByPane(pane);
  C.project = a ? a.project : null;              // links and @ mentions follow the agent's project, not the page's
  C.label = a ? agentLabel(a) : null;
  if (a && a.project) store("chat." + a.project, pane);
  render();
  if (pane) poll();
}

async function poll() {
  clearTimeout(C.timer);
  if (!C.open || !C.pane) return;
  const pane = C.pane, my = ++C.seq, from = C.offset;
  try {
    const params = { pane };
    if (pane.startsWith("session:")) params.around = C.around || "";
    else if (C.offset != null) Object.assign(params, { after: C.offset, session: C.session || "" });
    if (menuOn()) params.screen = 1;
    const r = await get("/api/chat", params);
    if (pane !== C.pane || my !== C.seq || from !== C.offset) return;      // a newer poll owns the state
    const reset = r.session !== C.session || C.offset == null || r.reset;     // r.reset: a rewind forked the conversation
    if (reset) { C.items = []; C.tools = new Map(); }
    C.session = r.session; C.offset = r.offset; C.cut = reset ? r.cut : C.cut; C.err = null;
    const statusChanged = r.status !== C.status || (r.screen || null) !== (C.screen || null);
    C.status = r.status; C.title = r.title; C.screen = r.screen || null; C.fallback = r.fallback || null;
    if (r.status === "archive") {                    // a saved conversation: drawn once, opened at the hit
      C.items = []; C.tools = new Map(); C.turnFiles = new Set(); ingest(r.items); C.status = "archive"; C.focus = r.focus; render();
      const hit = [...$("#ch-body").querySelectorAll("[data-uid]")].find((e) => C.around && e.dataset.uid.startsWith(C.around));
      if (hit) { hit.classList.add("hit"); hit.scrollIntoView({ block: "center" }); }
      return;
    }
    if (reset) { C.turnFiles = new Set(); ingest(r.items); render(); }
    else {
      const fresh = ingest(r.items);
      if (fresh.length) appendItems(fresh);
      if (C.menu && fresh.some((it) => it.k !== "cmd" && it.ts && Date.parse(it.ts) > C.menu.at + 1500)) C.menu = null;
      if (statusChanged || fresh.length) renderLive();
    }
  } catch (e) {
    if (my !== C.seq) return;
    C.err = e.message;
    renderLive();
  }
  const fast = C.status === "working" || C.status === "blocked" || C.queued.length || menuOn();
  if (C.status === "archive") return;
  C.timer = setTimeout(poll, C.status === "ended" ? 15000 : fast ? 1000 : 2500);
}

function ingest(items) {
  const fresh = [];
  for (const it of items || []) {
    if (it.k === "result") {
      const t = C.tools.get(it.id);
      if (t) { t.result = it; updateTool(t); }
      continue;
    }
    if (it.k === "tool") C.tools.set(it.id, it);
    if (it.k === "user") {
      const i = C.queued.findIndex((q) => q.trim() === it.text.trim());
      if (i >= 0) C.queued.splice(i, 1);
    }
    C.items.push(it);
    fresh.push(it);
  }
  return fresh;
}

// ---------- rendering ----------

function render() {
  const el = $("#chat");
  if (!C.open) return;
  const a = agentByPane(C.pane);
  el.innerHTML = `<div class="chat-head">
      <div class="picker" id="ch-pick" title="Switch agent">${a ? avatar(a) : `<span class="avatar">?</span>`}
        <div class="txt"><div class="l1">${esc(a ? agentLabel(a) : (C.pane || "").startsWith("session:") ? (C.label || "Saved conversation") + " · saved" : C.label ? C.label + " (ended)" : "No agent")}${C.project && C.project !== S.route.project ? ` <span class="muted" style="font-weight:400">· ${esc(C.project)}</span>` : ""}</div><div class="l2" id="ch-sub"></div></div>
        <span class="muted" style="font-size:10px">▾</span></div>
      <span class="grow"></span>
      <button class="btn ghost sm icon" id="ch-verbose" title="${S.prefs.verbose ? "Fold tool calls" : "Show every tool call"}">${icon(S.prefs.verbose ? "eye" : "code")}</button>
      <button class="btn ghost sm icon" id="ch-term" title="Open its terminal here">${icon("term")}</button>
      <button class="btn ghost sm icon" id="ch-more" title="More">${icon("more")}</button>
      ${C.livePane && agentByPane(C.livePane) ? `<button class="btn sm" id="ch-live-open" title="This session is still running">Open live</button>` : ""}
      <button class="btn ghost sm icon" id="ch-close" title="Close (⌘J)">${icon("x")}</button></div>
    <div class="chat-body" id="ch-body"></div>
    <div id="ch-live"></div>
    <div class="composer"><div class="box">
      <textarea id="composer" rows="1" placeholder="${a ? `Message ${esc(agentLabel(a).toLowerCase())}…  / for skills, @ for tickets` : C.status === "ended" ? "This session has ended (its tab closed); its conversation stays readable here" : C.status === "archive" || (C.pane || "").startsWith("session:") ? "A saved conversation, read-only" : "Pick an agent first"}" ${a ? "" : "disabled"}></textarea>
      <div class="bar2"><span class="hint" id="ch-hint">⏎ send · ⇧⏎ new line</span><span class="grow"></span>
        <button class="send" id="ch-send" title="Send">${icon("send")}</button></div></div></div>`;
  $("#ch-pick").onclick = (e) => pickAgent(e.currentTarget);
  $("#ch-close").onclick = closeChat;
  if ($("#ch-live-open")) $("#ch-live-open").onclick = () => openChat(C.livePane);
  $("#ch-term").onclick = () => C.pane && hooks.openTerminal({ kind: "attach", pane: C.pane, label: agentLabel(a) });
  $("#ch-verbose").onclick = () => { S.prefs.verbose = !S.prefs.verbose; savePrefs(); render(); };
  $("#ch-more").onclick = (e) => popMenu(e.currentTarget, [
    { label: "Focus in herdr", icon: "ext", run: () => post("/api/focus", { pane: C.pane }).then(() => toast("Focused in herdr")).catch((x) => toast(x.message, "err")) },
    { label: "Interrupt (Esc)", icon: "stop", run: () => keys(["esc"]) },
    { label: "Copy session id", icon: "doc", run: () => navigator.clipboard.writeText(C.session || "").then(() => toast("Copied")) },
  ], { right: true });
  wireComposer();
  const body = $("#ch-body");
  if (!C.pane) {
    body.innerHTML = `<div class="empty big">No live agent${S.route.project ? " in this project" : ""}.<br><br>
      <button class="btn primary" id="ch-start">${icon("users")} Start team</button> <button class="btn" id="ch-new">${icon("plus")} New session</button></div>`;
    $("#ch-start").onclick = () => S.route.project ? hooks.startTeam(S.route.project) : toast("Open a project first");
    $("#ch-new").onclick = () => hooks.newSession(S.route.project);
  } else {
    if (C.cut) body.insertAdjacentHTML("beforeend", `<div class="msg note">Earlier messages are not shown here; the terminal has the full history.</div>`);
    appendItems(C.items, true);
  }
  renderLive();
  body.scrollTop = body.scrollHeight;
}

function chatProject() {
  const p = S.summary?.projects.find((x) => x.name === C.project);
  return p && p.path ? { name: p.name, path: p.path } : null;
}
function projectTargets() {
  // maps and tickets of the chat agent's project (the page may show another project)
  if (S.data && S.data.name === C.project) return S.data.maps.flatMap((m) => [{ id: m.id, title: m.title, path: m.path }, ...m.tickets.map((k) => ({ id: k.id, title: k.title, path: k.path }))]);
  const p = S.summary?.projects.find((x) => x.name === C.project);
  return Object.entries(p?.states || {}).map(([id, [, title, mf, tf]]) => id.startsWith("map:")
    ? { id: id.slice(4), title, path: `maps/${mf}/map.md` } : { id, title, path: `maps/${mf}/tickets/${tf}/ticket.md` });
}

function filesCard(files) {
  // the files this turn wrote or edited: inside the project they open in the viewer, else their path is copied
  const proj = chatProject();
  const card = document.createElement("div");
  card.className = "msg files";
  card.innerHTML = `<div class="who">${icon("doc")} Changed in this turn</div>` + files.map((f) => {
    const rel = proj && f.startsWith(proj.path + "/") ? f.slice(proj.path.length + 1) : null;
    return `<a class="fchip mono" data-rel="${esc(rel || "")}" data-abs="${esc(f)}" title="${esc(f)}">${esc(rel || f.replace(/^\/Users\/[^/]+/, "~"))}</a>`;
  }).join("");
  card.querySelectorAll(".fchip").forEach((a) => a.onclick = () => {
    if (a.dataset.rel && proj) hooks.openPath(proj.name, a.dataset.rel);
    else navigator.clipboard.writeText(a.dataset.abs).then(() => toast("Path copied (outside the project)"));
  });
  return card;
}

function nearBottom(el) { return el.scrollHeight - el.scrollTop - el.clientHeight < 120; }

function appendItems(items, initial = false) {
  const body = $("#ch-body");
  if (!body) return;
  body.querySelectorAll(".msg.queued, .working, .fallback").forEach((e) => e.remove());   // live bits go back after
  const stick = initial || nearBottom(body);
  for (const it of items) {
    if (it.k === "tool") {
      let group = body.lastElementChild;
      if (!group || !group.classList.contains("tools")) {
        group = document.createElement("div");
        group.className = "tools";
        group.innerHTML = `<div class="more" hidden></div>`;
        group.firstChild.onclick = () => { group.classList.remove("fold"); group._open = true; foldGroup(group); };
        body.appendChild(group);
      }
      group.appendChild(toolEl(it));
      foldGroup(group);
      (it.files || []).forEach((f) => C.turnFiles.add(f));
      continue;
    }
    const d = document.createElement("div");
    d.className = "msg " + it.k;
    if (it.id) d.dataset.uid = String(it.id);
    if (it.k === "user") d.innerHTML = `<div class="bubble">${esc(it.text)}</div>`;
    else if (it.k === "cmd") d.innerHTML = `<code>${esc(it.text)}</code>`;
    else if (it.k === "note") d.textContent = it.text;
    else if (it.k === "safeguard") {
      d.innerHTML = `<div class="who">⚠ ${it.kind === "fallback" ? "Model switched by safeguards" : "Reply stopped by safeguards"}</div><div>${esc(it.text)}
        This is often a false positive on biology work.</div><div class="actions" style="margin-top:6px">
        <button class="btn sm" data-model="sonnet" title="Sends /model sonnet to this session (Claude Code also saves it as the default for new sessions)">Use Sonnet here</button>
        <button class="btn sm" data-model="opus" title="Sends /model opus to this session">Back to Opus</button></div>`;
      d.querySelectorAll("[data-model]").forEach((b) => b.onclick = () => post("/api/chat/send", { pane: C.pane, text: "/model " + b.dataset.model })
        .then(() => { toast(`Sent /model ${b.dataset.model}`); setTimeout(poll, 500); }).catch((e) => toast(e.message, "err")));
    }
    else if (it.k === "turn") {
      if (!body.lastElementChild || body.lastElementChild.classList.contains("turn")) continue;   // no empty turns
      if (C.turnFiles.size) { body.appendChild(filesCard([...C.turnFiles])); C.turnFiles = new Set(); }
      const t = it.ts ? new Date(it.ts) : null, s = Math.round((it.ms || 0) / 1000);
      d.innerHTML = `<span>${t ? t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}${s ? ` · ${s < 60 ? s + " s" : Math.floor(s / 60) + " min " + (s % 60) + " s"}` : ""}</span>`;
    }
    else if (it.k === "from") { d.innerHTML = `<div class="who">↘ from ${esc(it.role ? `${it.role} (${it.who})` : it.who)}</div><div></div>`; md(d.lastChild, it.text, { paths: true, project: chatProject() }); }
    else if (it.k === "assistant") md(d, it.text, { paths: true, project: chatProject() });
    body.appendChild(d);
  }
  if (stick) body.scrollTop = body.scrollHeight;
}

function foldGroup(g) {
  const n = g.querySelectorAll(".tool").length, more = g.firstChild;
  const fold = !S.prefs.verbose && !g._open && n > 3;
  g.classList.toggle("fold", fold);
  g.querySelectorAll(".tool").forEach((t, i) => { t.hidden = fold && i < n - 2; });
  more.hidden = !fold;
  more.textContent = `▸ ${n - 2} earlier tool calls`;
}

function toolEl(t) {
  const d = document.createElement("div");
  d.className = "tool";
  d.dataset.id = t.id;
  d.innerHTML = `<div class="th"><span class="ti"></span><span class="tn">${esc(t.name)}</span><span class="ts">${esc(t.summary)}</span></div><div class="tb" hidden></div>`;
  d.firstChild.onclick = () => {
    const b = d.lastChild;
    if (b.hidden) b.innerHTML = `<pre>${esc(t.input)}</pre>` + (t.result ? `<pre class="${t.result.error ? "err" : ""}">${esc(t.result.text || "(no output)")}${t.result.more ? `\n… ${t.result.more} more characters` : ""}</pre>` : "");
    b.hidden = !b.hidden;
  };
  t.el = d;
  updateTool(t);
  return d;
}

function updateTool(t) {
  if (!t.el) return;
  const i = t.el.querySelector(".ti");
  i.className = "ti " + (t.result ? (t.result.error ? "err" : "ok") : "wait");
  i.textContent = t.result ? (t.result.error ? "✕" : "✓") : "●";
}

function renderLive() {
  const live = $("#ch-live"), body = $("#ch-body");
  if (!live) return;
  const sub = $("#ch-sub");
  const codex = codexNote(agentByPane(C.pane));
  if (sub) sub.innerHTML = C.err ? `<span class="err">${esc(C.err)}</span>` : `${modelTag(agentByPane(C.pane))}${esc(AGENT_WORD[C.status] || C.status || "…")}${codex ? " · " + esc(codex) : C.title ? " · " + esc(C.title) : ""}`;
  // queued messages + working indicator live at the bottom of the conversation
  body.querySelectorAll(".msg.queued, .working, .fallback").forEach((e) => e.remove());
  const stick = nearBottom(body);
  if (C.fallback && !C.items.length) body.insertAdjacentHTML("beforeend", `<div class="fallback"><div class="msg note">No transcript for this agent: its screen</div><pre class="mono" style="white-space:pre-wrap;font-size:11.5px">${esc(C.fallback)}</pre></div>`);
  C.queued.forEach((q) => body.insertAdjacentHTML("beforeend", `<div class="msg user queued" title="Queued: the agent reads it when its turn ends"><div class="bubble">${esc(q)}</div></div>`));
  if (C.status === "working") body.insertAdjacentHTML("beforeend", `<div class="working"><span class="dots"><span></span><span></span><span></span></span>${esc(C.title || "Working")}</div>`);
  else if (codex) body.insertAdjacentHTML("beforeend", `<div class="working"><span class="dots"><span></span><span></span><span></span></span>Waiting on Codex (${esc(codex.replace("Codex running · ", ""))}); it reports back when the job ends</div>`);
  if (stick) body.scrollTop = body.scrollHeight;
  // a prompt the agent waits at
  const asking = C.status === "blocked" || menuOn();
  const want = asking && C.screen ? C.pane + "\n" + (menuOn() && C.status !== "blocked" ? "menu" : "ask") + "\n" + C.screen : "";
  if (want !== (live.dataset.screen || "")) {          // rebuild only when the question changed: keeps a typed answer
    const pane = C.pane;
    live.innerHTML = want ? promptCard(C.screen, C.status !== "blocked" && menuOn() ? C.menu.cmd : null) : "";
    live.dataset.screen = want;
    const pre = live.querySelector("pre");
    if (pre) pre.scrollTop = pre.scrollHeight;         // the question sits at the bottom of the screen
    live.querySelector(".opts .btn, #pc-text")?.focus({ preventScroll: true });
    live.querySelectorAll("[data-key]").forEach((b) => b.onclick = () => {
      const k = b.dataset.key;
      if (menuOn() && C.menu.cmd === "/rewind") markRewound(k, b.textContent);
      if (menuOn()) {                                     // Esc closes a menu at once; after Enter, give it a few seconds
        if (k === "esc") setTimeout(() => { C.menu = null; renderLive(); }, 900);
        else if (k === "enter" || /^\d$/.test(k)) C.menu.at = Math.min(C.menu.at, Date.now() - 172000);
      }
      keys(k.split(" "), pane);
    });
    const pc = live.querySelector("#pc-close");
    if (pc) pc.onclick = () => { C.menu = null; renderLive(); };
    const pt = live.querySelector("#pc-term");
    if (pt) pt.onclick = () => hooks.openTerminal({ kind: "attach", pane, label: agentLabel(agentByPane(pane)) });
    const tx = live.querySelector("#pc-text");
    if (tx) {
      let busy = false;
      const sendText = async () => {
        if (!tx.value || busy) return;
        busy = true;
        try { await post("/api/chat/text", { pane, text: tx.value, enter: true, menu: menuOn() }); tx.value = ""; markSent(pane); setTimeout(poll, 350); }
        catch (e) { toast(e.message, "err"); }                 // the answer stays in the box
        busy = false;
      };
      tx.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); sendText(); } };
      live.querySelector("#pc-type").onclick = sendText;
    }
  }
  const send = $("#ch-send");
  if (send) {
    const working = C.status === "working";
    send.classList.toggle("stop", working && !$("#composer").value.trim());
    send.innerHTML = working && !$("#composer").value.trim() ? icon("stop") : icon("send");
    send.title = working && !$("#composer").value.trim() ? "Stop (Esc)" : "Send";
  }
}

// A rewind writes nothing to the transcript until the next message (which then forks it, and the chat redraws the
// live branch). Meanwhile, once "Restore conversation" is confirmed, the rewound messages are greyed out.
function markRewound(key, label) {
  const screen = C.screen || "";
  const chosen = /Restore conversation/i.test(label) ? true
    : key === "enter" ? /❯\s*1\.\s*Restore conversation/.test(screen) : false;
  const m = screen.match(/restore to the point before you sent this message:\s*\n\s*│\s*(.+)/i);
  if (!chosen || !m) return;
  const first = m[1].trim();
  const bubbles = [...document.querySelectorAll("#ch-body .msg.user")];
  const from = bubbles.reverse().find((b) => b.textContent.trim().startsWith(first.slice(0, 60)));
  if (!from) return;
  for (let el = from; el; el = el.nextElementSibling) if (!el.classList.contains("working")) el.classList.add("rewound");
  from.insertAdjacentHTML("beforebegin", `<div class="msg note rewound-note">Rewound: the messages below are no longer in Claude's context; they disappear here after your next message</div>`);
}

// after a /command, Claude may show a menu (rewind's checkpoints, /model, /config…) that never reaches the transcript:
// the chat shows the live screen with keys until the conversation moves on, you close it, or three minutes pass
const menuOn = () => C.menu && C.menu.pane === C.pane && Date.now() - C.menu.at < 180000;

function promptCard(screen, menuCmd = null) {
  const lines = screen.split("\n");
  const tail = lines.slice(-40).join("\n");
  const opts = [];
  for (const l of lines.slice(-24)) {
    const m = l.match(/^\s*[❯›>]?\s*(\d)[.)]\s+(.+?)\s*$/);
    if (m && !opts.some((o) => o.k === m[1])) opts.push({ k: m[1], t: m[2] });
  }
  return `<div class="prompt-card ${menuCmd ? "screenmode" : ""}"><div class="hd"><span class="dot ${menuCmd ? "working" : "blocked"}"></span>${menuCmd ? `Claude's screen after <code>${esc(menuCmd)}</code>` : "Waiting for your answer"}<span style="flex:1"></span>
      <button class="btn sm" id="pc-term" title="Answer in its terminal, when the buttons below don't fit the screen">${icon("term")} Open terminal</button>
      ${menuCmd ? `<button class="btn sm icon" id="pc-close" title="Hide the screen">${icon("x")}</button>` : ""}</div>
    <pre>${esc(tail)}</pre>
    ${opts.length ? `<div class="opts">${opts.map((o) => `<button class="btn" data-key="${o.k}"><kbd>${o.k}</kbd> ${esc(o.t)}</button>`).join("")}</div>` : ""}
    <div class="keys"><button class="btn sm" data-key="up">↑</button><button class="btn sm" data-key="down">↓</button>
      <button class="btn sm" data-key="enter">Enter</button><button class="btn sm" data-key="tab">Tab</button><button class="btn sm" data-key="esc">Esc</button>
      <input id="pc-text" placeholder="Type an answer…" style="flex:1;min-width:120px;height:24px;padding:2px 8px;font-size:12px">
      <button class="btn sm" id="pc-type">Send</button></div></div>`;
}

async function keys(k, pane = C.pane) {
  try { await post("/api/chat/keys", { pane, keys: k }); if (k.some((x) => /^\d$|enter/.test(x))) markSent(pane); setTimeout(poll, 350); }
  catch (e) { toast(e.message, "err"); }
}

function pickAgent(anchor) {
  const proj = S.route.project;
  const mine = allAgents().filter((a) => a.project === proj), rest = allAgents().filter((a) => a.project !== proj);
  const item = (a) => ({ label: agentLabel(a) + (a.project && a.project !== proj ? ` · ${a.project}` : ""), hint: AGENT_WORD[a.status] || a.status, run: () => openChat(a.pane) });
  const items = [];
  if (mine.length) items.push({ header: proj }, ...mine.map(item));
  if (rest.length) items.push({ header: proj ? "Elsewhere" : "Sessions" }, ...rest.map(item));
  items.push("-", { label: "New session…", icon: "plus", run: () => hooks.newSession(proj) });
  popMenu(anchor, items);
}

// ---------- composer ----------

function setComposer(text) {
  const t = $("#composer");
  if (!t) return;
  t.value = text;
  autosize(t);
  t.focus();
  t.setSelectionRange(text.length, text.length);
  renderLive();
}
function autosize(t) { t.style.height = "auto"; t.style.height = Math.min(220, t.scrollHeight) + "px"; }

function wireComposer() {
  const t = $("#composer"), send = $("#ch-send");
  if (!t) return;
  let menu = null, sel = 0, choices = [];
  const closeMenu = () => { if (menu) { menu.remove(); menu = null; } };
  const showMenu = () => {
    const v = t.value.slice(0, t.selectionStart);
    const slash = v.match(/^\/([\w:-]*)$/), at = v.match(/(?:^|\s)@([\w.-]*)$/);
    choices = [];
    if (slash) choices = S.skills.filter((s) => s.name.toLowerCase().includes(slash[1].toLowerCase()))
      .sort((a, b) => a.name.indexOf(slash[1]) - b.name.indexOf(slash[1])).slice(0, 40)
      .map((s) => ({ a: "/" + s.name, b: s.hint || s.description, ins: "/" + s.name + " ", re: /^\/[\w:-]*$/ }));
    else if (at) choices = projectTargets()
      .filter((x) => (x.id + " " + x.title).toLowerCase().includes(at[1].toLowerCase())).slice(0, 30)
      .map((x) => ({ a: x.id, b: x.title, ins: `${x.id} (${x.path}) `, re: /@[\w.-]*$/ }));
    if (!choices.length) return closeMenu();
    sel = Math.min(sel, choices.length - 1);
    if (!menu) { menu = document.createElement("div"); menu.className = "menu"; document.body.appendChild(menu); }
    menu.innerHTML = choices.map((c, i) => `<div class="mi ${i === sel ? "on" : ""}" data-i="${i}"><span class="a">${esc(c.a)}</span><span class="b">${esc(c.b)}</span></div>`).join("");
    const r = t.closest(".box").getBoundingClientRect();
    menu.style.left = r.left + "px"; menu.style.width = r.width + "px";
    menu.style.top = Math.max(8, r.top - menu.offsetHeight - 6) + "px";
    menu.querySelectorAll(".mi").forEach((m) => m.onmousedown = (e) => { e.preventDefault(); pick(+m.dataset.i); });
    menu.querySelector(".mi.on")?.scrollIntoView({ block: "nearest" });
  };
  const pick = (i) => {
    const c = choices[i], pos = t.selectionStart, before = t.value.slice(0, pos).replace(c.re, (m) => (m.startsWith(" ") ? " " : "") + c.ins);
    t.value = before + t.value.slice(pos);
    t.setSelectionRange(before.length, before.length);
    closeMenu(); autosize(t); renderLive();
  };
  const draftKey = "draft." + C.pane;
  if (!t.value && store(draftKey)) { t.value = store(draftKey); autosize(t); }
  t.oninput = () => { autosize(t); sel = 0; showMenu(); renderLive(); store(draftKey, t.value); };
  t.onblur = () => setTimeout(closeMenu, 150);
  t.onkeydown = (e) => {
    if (menu) {
      if (e.key === "ArrowDown") { e.preventDefault(); sel = (sel + 1) % choices.length; return showMenu(); }
      if (e.key === "ArrowUp") { e.preventDefault(); sel = (sel - 1 + choices.length) % choices.length; return showMenu(); }
      if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); return pick(sel); }
      if (e.key === "Escape") { e.preventDefault(); return closeMenu(); }
    }
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); }
    if (e.key === "Escape" && C.status === "working" && !t.value) { e.preventDefault(); keys(["esc"]); }
  };
  send.onclick = () => (C.status === "working" && !t.value.trim() ? keys(["esc"]) : submit());
  async function submit() {
    const text = t.value.trim();
    if (!text || !C.pane) return;
    if (C.status === "blocked") return toast("It's waiting at a prompt: answer that first", "err");
    closeMenu();
    t.value = ""; autosize(t); store("draft." + C.pane, "");
    if (C.status === "working") { C.queued.push(text); renderLive(); }
    try {
      const res = await post("/api/chat/send", { pane: C.pane, text });
      if (res.cleared) toast(`Cleared what was waiting in Claude's input box first: “${res.cleared.slice(0, 120)}”`, "", 7000);
      const cmd = text.match(/^\/([\w:-]+)/);                // a Claude Code command (not a skill): watch its screen
      if (cmd && S.skills.some((s) => s.kind === "builtin" && s.name === cmd[1])) C.menu = { pane: C.pane, at: Date.now(), cmd: "/" + cmd[1] };
      markSent(C.pane);
      if (!window.desk && "Notification" in window && Notification.permission === "default") Notification.requestPermission();
      setTimeout(poll, 400);
    } catch (e) {
      toast(e.message, "err");
      C.queued = C.queued.filter((q) => q !== text);
      t.value = text; autosize(t); renderLive();
    }
  }
}

export function initChatResize() {
  const bar = $("#chat-resize"), root = document.documentElement;
  const w = +localStorage.getItem("rd.chatw");
  if (w) root.style.setProperty("--chat-w", w + "px");
  bar.onpointerdown = (e) => {
    bar.setPointerCapture(e.pointerId);
    bar.onpointermove = (ev) => root.style.setProperty("--chat-w", Math.max(320, Math.min(760, window.innerWidth - ev.clientX)) + "px");
    bar.onpointerup = () => { bar.onpointermove = null; try { localStorage.setItem("rd.chatw", parseInt(getComputedStyle(root).getPropertyValue("--chat-w"))); } catch (_) { /* ignore */ } };
  };
}

// keep the header (agent label/status) fresh when the global poll sees changes
export function refreshChatHead() {
  if (!C.open) return;
  if (C.pane && !agentByPane(C.pane) && C.status !== "ended") { poll(); return; }   // gone: the next poll reads it as ended
  renderLive();
}
