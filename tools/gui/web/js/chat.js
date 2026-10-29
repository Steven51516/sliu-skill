// Chat with any live agent: its Claude Code transcript rendered, prompts answered from the exact screen, messages sent
// through herdr. Polls fast while the agent works or waits, slowly while it is idle.
import { S, $, esc, get, post, toast, icon, md, hooks, agentByPane, agentLabel, avatar, allAgents, AGENT_WORD, popMenu, store, savePrefs } from "./core.js";

const C = S.chat;
Object.assign(C, { items: [], tools: new Map(), offset: null, session: null, status: null, timer: null, queued: [], busy: false });

export function openChat(pane, opt = {}) {
  const a = pane && agentByPane(pane);
  if (!pane || !a) pane = defaultPane();
  C.open = true;
  $("#chat").hidden = false;
  $("#chat-resize").hidden = false;
  if (pane !== C.pane) switchTo(pane);
  else render();
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
  const proj = S.route.project;
  const remembered = proj && store("chat." + proj);
  const agents = allAgents().filter((a) => !proj || a.project === proj);
  if (remembered && agents.some((a) => a.pane === remembered)) return remembered;
  const desk = agents.find((a) => a.role === "desk");
  return (desk || agents.find((a) => a.status === "blocked") || agents[0] || {}).pane || null;
}
export function deskPane(project) {
  const a = allAgents().find((x) => x.project === project && x.role === "desk");
  return a ? a.pane : null;
}

function switchTo(pane) {
  clearTimeout(C.timer);
  Object.assign(C, { pane, items: [], tools: new Map(), offset: null, session: null, status: null, queued: [], screen: null, fallback: null, cut: false, err: null });
  const a = agentByPane(pane);
  if (a && a.project) store("chat." + a.project, pane);
  render();
  if (pane) poll();
}

async function poll() {
  clearTimeout(C.timer);
  if (!C.open || !C.pane) return;
  const pane = C.pane;
  try {
    const params = { pane };
    if (C.offset != null) Object.assign(params, { after: C.offset, session: C.session || "" });
    const r = await get("/api/chat", params);
    if (pane !== C.pane) return;
    const reset = r.session !== C.session || C.offset == null;
    if (reset) { C.items = []; C.tools = new Map(); }
    C.session = r.session; C.offset = r.offset; C.cut = reset ? r.cut : C.cut; C.err = null;
    const statusChanged = r.status !== C.status || (r.screen || null) !== (C.screen || null);
    C.status = r.status; C.title = r.title; C.screen = r.screen || null; C.fallback = r.fallback || null;
    if (reset) { ingest(r.items); render(); }
    else {
      const fresh = ingest(r.items);
      if (fresh.length) appendItems(fresh);
      if (statusChanged || fresh.length) renderLive();
    }
  } catch (e) {
    C.err = e.message;
    renderLive();
  }
  const fast = C.status === "working" || C.status === "blocked" || C.queued.length;
  C.timer = setTimeout(poll, fast ? 1000 : 2500);
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
        <div class="txt"><div class="l1">${esc(a ? agentLabel(a) : "No agent")}</div><div class="l2" id="ch-sub"></div></div>
        <span class="muted" style="font-size:10px">▾</span></div>
      <span class="grow"></span>
      <button class="btn ghost sm icon" id="ch-verbose" title="${S.prefs.verbose ? "Fold tool calls" : "Show every tool call"}">${icon(S.prefs.verbose ? "eye" : "code")}</button>
      <button class="btn ghost sm icon" id="ch-term" title="Open its terminal here">${icon("term")}</button>
      <button class="btn ghost sm icon" id="ch-more" title="More">${icon("more")}</button>
      <button class="btn ghost sm icon" id="ch-close" title="Close (⌘J)">${icon("x")}</button></div>
    <div class="chat-body" id="ch-body"></div>
    <div id="ch-live"></div>
    <div class="composer"><div class="box">
      <textarea id="composer" rows="1" placeholder="${a ? `Message ${esc(agentLabel(a).toLowerCase())}…  / for skills, @ for tickets` : "Pick an agent first"}" ${a ? "" : "disabled"}></textarea>
      <div class="bar2"><span class="hint" id="ch-hint">⏎ send · ⇧⏎ new line</span><span class="grow"></span>
        <button class="send" id="ch-send" title="Send">${icon("send")}</button></div></div></div>`;
  $("#ch-pick").onclick = (e) => pickAgent(e.currentTarget);
  $("#ch-close").onclick = closeChat;
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

function nearBottom(el) { return el.scrollHeight - el.scrollTop - el.clientHeight < 120; }

function appendItems(items, initial = false) {
  const body = $("#ch-body");
  if (!body) return;
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
      continue;
    }
    const d = document.createElement("div");
    d.className = "msg " + it.k;
    if (it.k === "user") d.innerHTML = `<div class="bubble">${esc(it.text)}</div>`;
    else if (it.k === "cmd") d.innerHTML = `<code>${esc(it.text)}</code>`;
    else if (it.k === "note") d.textContent = it.text;
    else if (it.k === "from") { d.innerHTML = `<div class="who">↘ from ${esc(it.who)}</div><div></div>`; md(d.lastChild, it.text); }
    else if (it.k === "assistant") md(d, it.text);
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
  if (sub) sub.innerHTML = C.err ? `<span class="err">${esc(C.err)}</span>` : `${esc(AGENT_WORD[C.status] || C.status || "…")}${C.title ? " · " + esc(C.title) : ""}`;
  // queued messages + working indicator live at the bottom of the conversation
  body.querySelectorAll(".msg.queued, .working, .fallback").forEach((e) => e.remove());
  const stick = nearBottom(body);
  if (C.fallback && !C.items.length) body.insertAdjacentHTML("beforeend", `<div class="fallback"><div class="msg note">No transcript for this agent: its screen</div><pre class="mono" style="white-space:pre-wrap;font-size:11.5px">${esc(C.fallback)}</pre></div>`);
  C.queued.forEach((q) => body.insertAdjacentHTML("beforeend", `<div class="msg user queued" title="Queued: the agent reads it when its turn ends"><div class="bubble">${esc(q)}</div></div>`));
  if (C.status === "working") body.insertAdjacentHTML("beforeend", `<div class="working"><span class="dots"><span></span><span></span><span></span></span>${esc(C.title || "Working")}</div>`);
  if (stick) body.scrollTop = body.scrollHeight;
  // a prompt the agent waits at
  const was = live.dataset.screen;
  live.innerHTML = C.status === "blocked" && C.screen ? promptCard(C.screen) : "";
  live.dataset.screen = C.screen || "";
  const pre = live.querySelector("pre");
  if (pre) pre.scrollTop = pre.scrollHeight;           // the question sits at the bottom of the screen
  if (C.screen && was !== C.screen) live.querySelector(".opts .btn, #pc-text")?.focus({ preventScroll: true });
  live.querySelectorAll("[data-key]").forEach((b) => b.onclick = () => keys(b.dataset.key.split(" ")));
  const tx = live.querySelector("#pc-text");
  if (tx) {
    const sendText = async (enter) => { if (!tx.value) return; await post("/api/chat/text", { pane: C.pane, text: tx.value }).catch((e) => toast(e.message, "err")); if (enter) await keys(["enter"]); tx.value = ""; };
    tx.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); sendText(true); } };
    live.querySelector("#pc-type").onclick = () => sendText(true);
  }
  const send = $("#ch-send");
  if (send) {
    const working = C.status === "working";
    send.classList.toggle("stop", working && !$("#composer").value.trim());
    send.innerHTML = working && !$("#composer").value.trim() ? icon("stop") : icon("send");
    send.title = working && !$("#composer").value.trim() ? "Stop (Esc)" : "Send";
  }
}

function promptCard(screen) {
  const lines = screen.split("\n");
  const tail = lines.slice(-40).join("\n");
  const opts = [];
  for (const l of lines.slice(-24)) {
    const m = l.match(/^\s*[❯›>]?\s*(\d)[.)]\s+(.+?)\s*$/);
    if (m && !opts.some((o) => o.k === m[1])) opts.push({ k: m[1], t: m[2] });
  }
  return `<div class="prompt-card"><div class="hd"><span class="dot blocked"></span>Waiting for your answer</div>
    <pre>${esc(tail)}</pre>
    ${opts.length ? `<div class="opts">${opts.map((o) => `<button class="btn" data-key="${o.k}"><kbd>${o.k}</kbd> ${esc(o.t)}</button>`).join("")}</div>` : ""}
    <div class="keys"><button class="btn sm" data-key="up">↑</button><button class="btn sm" data-key="down">↓</button>
      <button class="btn sm" data-key="enter">Enter</button><button class="btn sm" data-key="tab">Tab</button><button class="btn sm" data-key="esc">Esc</button>
      <input id="pc-text" placeholder="Type an answer…" style="flex:1;min-width:120px;height:24px;padding:2px 8px;font-size:12px">
      <button class="btn sm" id="pc-type">Send</button></div></div>`;
}

async function keys(k) {
  try { await post("/api/chat/keys", { pane: C.pane, keys: k }); setTimeout(poll, 350); }
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
    else if (at && S.data) choices = S.data.maps.flatMap((m) => [{ id: m.id, title: m.title, path: m.path }, ...m.tickets.map((k) => ({ id: k.id, title: k.title, path: k.path }))])
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
  t.oninput = () => { autosize(t); sel = 0; showMenu(); renderLive(); };
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
    if (e.key === "ArrowUp" && !t.value && C.queued.length) { e.preventDefault(); setComposer(C.queued.pop()); }
  };
  send.onclick = () => (C.status === "working" && !t.value.trim() ? keys(["esc"]) : submit());
  async function submit() {
    const text = t.value.trim();
    if (!text || !C.pane) return;
    if (C.status === "blocked") return toast("It's waiting at a prompt: answer that first", "err");
    t.value = ""; autosize(t);
    if (C.status === "working") { C.queued.push(text); renderLive(); }
    try {
      await post("/api/chat/send", { pane: C.pane, text });
      S.sent.add(C.pane);
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
  if (C.pane && !agentByPane(C.pane)) { C.status = "gone"; C.title = "this agent has exited"; }
  renderLive();
}
