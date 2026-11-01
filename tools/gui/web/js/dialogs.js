// Modal dialogs: start a team or driver, start a session (with skill presets), ask for a line of text, add a project,
// the keyboard sheet. One dialog at a time, in #overlay.
import { S, $, esc, get, post, toast, icon, hooks, store } from "./core.js";

export function closeDialog() { const o = $("#overlay"); o.hidden = true; o.innerHTML = ""; o.onclick = null; }
function dialog(html, opt = {}) {
  const o = $("#overlay");
  o.hidden = false;
  o.innerHTML = `<div class="dialog" style="${opt.width ? `width:min(${opt.width}px,92vw)` : ""}">${html}</div>`;
  o.onclick = (e) => { if (e.target === o) closeDialog(); };
  return o.firstChild;
}

async function runJob(d, start, onDone) {
  const log = $("#dlg-log", d);
  log.hidden = false;
  log.textContent = "starting…";
  try {
    const { job } = await start();
    for (;;) {
      const j = await get("/api/job", { id: job });
      log.textContent = j.log.join("\n") || "…";
      log.scrollTop = log.scrollHeight;
      if (j.done) { log.textContent += j.ok ? "\n\ndone" : "\n\nstopped (see above)"; if (j.ok && onDone) onDone(j); break; }
      await new Promise((r) => setTimeout(r, 800));
    }
  } catch (e) { log.textContent = e.message; }
  hooks.refresh && hooks.refresh();
}

function planHtml(plan) {
  const ws = plan.workspace.id ? `in herdr workspace <b>${esc(plan.workspace.label)}</b>` : `in a new herdr workspace <b>${esc(plan.workspace.label)}</b>`;
  return `${plan.dry_run ? `<div class="callout" style="margin-bottom:10px">Dry run: nothing will be sent to herdr.</div>` : ""}
    ${plan.steps.length ? `<div>${plan.steps.length === 1 ? "One tab" : "One tab each"} ${ws}:</div>
    <div class="card" style="margin:8px 0;box-shadow:none"><div class="rows">${plan.steps.map((s) => `<div class="row"><b>${esc(s.label)}</b>
      <span class="grow t2">${esc(s.kind)}${s.prompt ? ` · then <code>${esc(s.prompt)}</code>` : ""}${Object.keys(s.env || {}).length ? ` · ${esc(Object.entries(s.env).map(([k, v]) => `${k}=${v}`).join(" "))}` : ""}</span></div>`).join("")}</div></div>` : `<div class="muted">Nothing to start.</div>`}
    ${plan.notes.length ? `<ul class="muted" style="margin:6px 0;padding-left:18px">${plan.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}
    <details><summary class="muted" style="cursor:pointer">herdr commands</summary><pre>${esc(plan.commands.join("\n"))}</pre></details>
    <pre id="dlg-log" hidden style="max-height:200px;overflow:auto"></pre>`;
}

const TEAM_AGENTS = [["claude", "Claude Code", "every session on Opus 5.5"], ["codex", "Codex", "every session on gpt-6-astra"]];

export async function startTeam(project, map = null) {
  const d = dialog(`<div class="dh">${map ? "Start a driver" : "Start the team"} · ${esc(project)}</div><div class="db"><div class="spin"></div></div>`);
  let plan, agent = null;
  const load = async () => {   // a team is all Claude Code or all Codex; a live team keeps its agent
    try { plan = await get("/api/plan", { project, ...(map ? { map } : {}), ...(agent ? { agent } : {}) }); }
    catch (e) { $(".db", d).innerHTML = `<div class="err">${esc(e.message)}</div>`; return false; }
    agent = plan.agent;
    const pick = plan.agent_fixed
      ? `<div class="muted" style="margin-bottom:8px">This project's team runs on ${agent === "codex" ? "Codex" : "Claude Code"}; new sessions join it.</div>`
      : `<div class="choice" id="st-agent">${TEAM_AGENTS.map(([k, b, s]) => `<div class="opt ${k === agent ? "on" : ""}" data-k="${k}"><b>${b}</b><span>${s}</span></div>`).join("")}</div>`;
    $(".db", d).innerHTML = pick + planHtml(plan);
    $$("#st-agent .opt", d).forEach((o) => o.onclick = () => { if (o.dataset.k !== agent) { agent = o.dataset.k; load(); } });
    return true;
  };
  if (!(await load())) return;
  d.insertAdjacentHTML("beforeend", `<div class="df"><span class="grow muted" style="font-size:12px">Sessions run in herdr; closing the app leaves them running.</span>
    <button class="btn" id="dlg-cancel">Close</button>${plan.steps.length ? `<button class="btn primary" id="dlg-go">${icon("play")} ${plan.dry_run ? "Dry run" : "Start"}</button>` : ""}</div>`);
  $("#dlg-cancel", d).onclick = closeDialog;
  if ($("#dlg-go", d)) $("#dlg-go", d).onclick = (e) => {
    e.currentTarget.disabled = true;
    runJob(d, () => post("/api/start", { project, map, agent }), (j) => {
      const desk = plan.steps.findIndex((s) => s.role === "desk");
      if (!plan.dry_run && j.panes.length) setTimeout(() => { hooks.refresh(); hooks.openChat(j.panes[desk >= 0 ? desk : 0]); }, 1500);
    });
  };
}

export const PRESETS = [
  { id: "plain", label: "Plain session", prompt: "", hint: "An empty Claude Code session in the project" },
  { id: "work", label: "Work a ticket", prompt: "/research-work {ticket}", needs: "ticket", hint: "research-work: one ticket end to end" },
  { id: "review", label: "Review a ticket", prompt: "/review {ticket}", needs: "ticket", hint: "review: Fair, Spec and Code axes" },
  { id: "drive", label: "Drive a map once", prompt: "/research-drive {map}", needs: "map", hint: "research-drive: one pass over the frontier" },
  { id: "wayfinder", label: "Chart a new map", prompt: '/wayfinder "{text}"', needs: "text", ask: "The loose idea", hint: "wayfinder interviews you, then charts a map" },
  { id: "rechart", label: "Re-chart a map", prompt: "/wayfinder {map} --rechart", needs: "map", hint: "change destination or Contract on evidence" },
  { id: "tickets", label: "Add a ticket", prompt: '/to-tickets {map} "{text}"', needs: "map+text", ask: "The question", hint: "to-tickets: a question with blocking edges" },
  { id: "grill", label: "Grill a plan", prompt: "/grilling {text}", needs: "text", ask: "What to stress-test", hint: "grilling: a relentless interview" },
  { id: "research", label: "Research a question", prompt: "/research {text}", needs: "text", ask: "The question", hint: "research: primary sources into a markdown file" },
  { id: "diagnose", label: "Diagnosis card", prompt: "/diagnosis-card {text}", needs: "text", ask: "Which results", hint: "what failing or regressed scores mean" },
  { id: "custom", label: "Custom first message", prompt: "{text}", needs: "text", ask: "First message (a /skill or plain words)", hint: "" },
];

export async function newSession(project, preset = null, fill = {}) {
  project = project || S.route.project;
  if (!project) return toast("Open a project first");
  const data = S.data && S.data.name === project ? S.data : await get("/api/project", { name: project }).catch(() => null);
  const maps = data ? data.maps.filter((m) => m.status !== "closed") : [];
  const done = (t) => ["resolved", "parked", "superseded"].includes(t.status);
  const wanted = fill.ticket || "";
  const tickets = data ? data.maps.flatMap((m) => m.tickets.filter((t) => (preset === "review" ? t.status === "resolved" : !done(t))
    || t.path.replace(/\/ticket\.md$/, "") === wanted).map((t) => ({ ...t, map: m }))) : [];
  let kind = "claude", pre = PRESETS.find((p) => p.id === (preset || "plain"));
  const d = dialog(`<div class="dh">New session · ${esc(project)}</div><div class="db">
      <div class="choice" id="ns-kind">
        <div class="opt on" data-k="claude"><b>Claude Code</b><span>with your skills</span></div>
        <div class="opt" data-k="codex"><b>Codex</b><span>codex CLI</span></div>
        <div class="opt" data-k="shell"><b>Shell</b><span>a herdr shell tab</span></div></div>
      <div id="ns-claude"><div id="ns-preset-f"><label class="f">Start with</label><select id="ns-preset">${PRESETS.map((p) => `<option value="${p.id}" ${p === pre ? "selected" : ""}>${esc(p.label)}</option>`).join("")}</select>
        <div class="muted" id="ns-hint" style="font-size:12px;margin-top:4px"></div></div>
        <div id="ns-map-f"><label class="f">Map</label><select id="ns-map">${maps.map((m) => `<option value="${esc(m.path.replace(/\/(map|track)\.md$/, ""))}">${esc(m.id)} · ${esc(m.title)}</option>`).join("")}</select></div>
        <div id="ns-ticket-f"><label class="f">Ticket</label><select id="ns-ticket">${tickets.map((t) => `<option value="${esc(t.path.replace(/\/ticket\.md$/, ""))}">${esc(t.id)} · ${esc(t.title)}</option>`).join("")}</select></div>
        <div id="ns-text-f"><label class="f" id="ns-text-l">Text</label><textarea id="ns-text" rows="3"></textarea></div></div>
      <div id="ns-shell" hidden><label class="f">Command (optional)</label><input id="ns-cmd" placeholder="e.g. ssh -t ${esc(data?.server || "node-16")}"></div>
      <label class="f">Tab label (optional)</label><input id="ns-label" placeholder="shown in herdr and in the sidebar">
      <div id="ns-plan" style="margin-top:12px"></div></div>
    <div class="df"><span class="grow"></span><button class="btn" id="dlg-cancel">Cancel</button><button class="btn primary" id="dlg-go">${icon("play")} Start</button></div>`, { width: 600 });
  const sync = () => {
    $("#ns-claude", d).hidden = kind === "shell";
    $("#ns-shell", d).hidden = kind !== "shell";
    pre = PRESETS.find((p) => p.id === $("#ns-preset", d).value);
    const needs = kind === "claude" ? pre.needs || "" : kind === "codex" ? "text" : "";
    $("#ns-map-f", d).hidden = !needs.includes("map");
    $("#ns-ticket-f", d).hidden = !needs.includes("ticket");
    $("#ns-text-f", d).hidden = !needs.includes("text");
    $("#ns-text-l", d).textContent = kind === "codex" ? "First message (optional)" : pre.ask || "Text";
    $("#ns-preset-f", d).hidden = kind === "codex";
    $("#ns-hint", d).textContent = pre.hint;
  };
  $$("#ns-kind .opt", d).forEach((o) => o.onclick = () => { kind = o.dataset.k; $$("#ns-kind .opt", d).forEach((x) => x.classList.toggle("on", x === o)); sync(); });
  $("#ns-preset", d).onchange = sync;
  if (fill.map) $("#ns-map", d).value = fill.map;
  if (fill.ticket) $("#ns-ticket", d).value = fill.ticket;
  if (fill.text) $("#ns-text", d).value = fill.text;
  sync();
  $("#dlg-cancel", d).onclick = closeDialog;
  $("#dlg-go", d).onclick = async (e) => {
    const text = $("#ns-text", d).value.trim();
    let prompt = "";
    if (kind === "claude") {
      if ((pre.needs || "").includes("text") && !text) return toast(`${pre.ask || "Text"} is empty`, "err");
      const tk = $("#ns-ticket", d).value, mp = $("#ns-map", d).value, tx = text.replace(/"/g, '\\"');
      prompt = pre.prompt.replace("{ticket}", () => tk).replace("{map}", () => mp).replace("{text}", () => tx);
      if (pre.id === "custom") prompt = text;
    } else if (kind === "codex") prompt = text;
    const body = { project, kind, prompt, label: $("#ns-label", d).value.trim(), command: $("#ns-cmd", d).value.trim() };
    e.currentTarget.disabled = true;
    try {
      const plan = await post("/api/session-plan", body);
      $("#ns-plan", d).innerHTML = planHtml(plan);
      runJob(d, () => post("/api/session", body), (j) => {
        if (!plan.dry_run && j.panes.length && kind !== "shell") setTimeout(() => { hooks.refresh(); hooks.openChat(j.panes[0]); closeDialog(); }, 1500);
      });
    } catch (err) { toast(err.message, "err"); e.currentTarget.disabled = false; }
  };
}
const $$ = (sel, el) => [...el.querySelectorAll(sel)];

export function ask({ title, label = "", placeholder = "", value = "", multiline = true, ok = "OK", hint = "" }) {
  return new Promise((resolve) => {
    const d = dialog(`<div class="dh">${esc(title)}</div><div class="db">${label ? `<label class="f">${esc(label)}</label>` : ""}
      ${multiline ? `<textarea id="ask-in" rows="4" placeholder="${esc(placeholder)}">${esc(value)}</textarea>` : `<input id="ask-in" placeholder="${esc(placeholder)}" value="${esc(value)}">`}
      ${hint ? `<div class="muted" style="font-size:12px;margin-top:6px">${esc(hint)}</div>` : ""}</div>
      <div class="df"><span class="grow"></span><button class="btn" id="dlg-cancel">Cancel</button><button class="btn primary" id="dlg-go">${esc(ok)}</button></div>`, { width: 520 });
    const inp = $("#ask-in", d);
    const done = (v) => { closeDialog(); resolve(v); };
    $("#dlg-cancel", d).onclick = () => done(null);
    $("#dlg-go", d).onclick = () => done(inp.value.trim() || null);
    inp.onkeydown = (e) => { if (e.key === "Enter" && (!multiline || e.metaKey)) { e.preventDefault(); done(inp.value.trim() || null); } };
    setTimeout(() => inp.focus(), 20);
  });
}

// A new project: a fresh folder under a projects root, registered here, then a Claude session in it runs
// /research-init (scope, tracker, delegation, domain docs: it asks you section by section in the chat).
export function newProject() {
  const root = (S.summary?.roots || [])[0] || (S.summary?.projects?.[0]?.path || "~/Documents/GitHub/x").replace(/\/[^/]+\/?$/, "");
  const d = dialog(`<div class="dh">New project</div><div class="db">
      <label class="f">Name</label><input id="np-name" placeholder="prot-design" autocomplete="off" spellcheck="false">
      <label class="f">Inside folder</label><input id="np-parent" value="${esc(root)}">
      <div class="muted" style="font-size:12px;margin-top:4px" id="np-where"></div>
      <label class="f">Direction in one line (optional)</label><input id="np-dir" placeholder="e.g. design binders for X with Y, beat Z on W">
      <label class="f">Server (ssh alias, optional)</label><input id="np-server" placeholder="node-16">
      <label class="f">Code folder on the server</label><input id="np-root" placeholder="~/code/&lt;name&gt;">
      <div class="muted" style="font-size:12px;margin-top:10px">Creates the folder and adds it here, then starts a Claude session in it with
        <code>/research-init</code>, which sets up the scope, tracker and docs by asking you, a section at a time, in the chat.</div></div>
    <div class="df"><span class="grow"></span><button class="btn" id="dlg-cancel">Cancel</button><button class="btn primary" id="dlg-go">${icon("plus")} Create</button></div>`, { width: 540 });
  const where = () => { const n = $("#np-name", d).value.trim() || "<name>"; $("#np-where", d).textContent = `→ ${$("#np-parent", d).value.trim().replace(/\/$/, "")}/${n}`;
    $("#np-root", d).placeholder = `~/code/${n}`; };
  $("#np-name", d).oninput = where; $("#np-parent", d).oninput = where; where();
  $("#dlg-cancel", d).onclick = closeDialog;
  $("#dlg-go", d).onclick = async () => {
    const v = (id) => $(id, d).value.trim();
    const name = v("#np-name"), server = v("#np-server");
    try {
      await post("/api/new-project", { name, parent: v("#np-parent"), server, server_root: server ? v("#np-root") || `~/code/${name}` : "" });
      closeDialog(); toast(`Created ${name}`); hooks.refresh(); location.hash = `#/p/${encodeURIComponent(name)}`;
      const dir = v("#np-dir").replace(/"/g, "'");
      setTimeout(() => newSession(name, "custom", { text: `/research-init ${name}${dir ? ` "${dir}"` : ""}` }), 300);
    } catch (e) { toast(e.message, "err"); }
  };
  setTimeout(() => $("#np-name", d).focus(), 20);
}

export function addProject(pre = {}) {
  const d = dialog(`<div class="dh">Add an existing folder</div><div class="db">
      <label class="f">Name</label><input id="ap-name" value="${esc(pre.name || "")}" placeholder="protbench">
      <label class="f">Folder on this Mac</label><input id="ap-path" value="${esc(pre.path || "")}" placeholder="~/Documents/GitHub/scinetics/…">
      <label class="f">Server (ssh alias, optional)</label><input id="ap-server" placeholder="node-16">
      <label class="f">Code folder on the server</label><input id="ap-root" placeholder="~/code/${esc(pre.name || "project")}">
      <label class="f">Map folders on the server live under</label><input id="ap-maps" value="tracks">
      <label class="f">Shared server folders pinned beside each map (comma-separated)</label><input id="ap-shared" value="common"></div>
    <div class="df"><span class="grow"></span><button class="btn" id="dlg-cancel">Cancel</button><button class="btn primary" id="dlg-go">Add</button></div>`, { width: 520 });
  $("#dlg-cancel", d).onclick = closeDialog;
  $("#dlg-go", d).onclick = async () => {
    const v = (id) => $(id, d).value.trim();
    try {
      await post("/api/add-project", { name: v("#ap-name"), path: v("#ap-path"), server: v("#ap-server"), server_root: v("#ap-root"),
        server_maps: v("#ap-maps"), shared: v("#ap-shared").split(",").map((s) => s.trim()) });
      closeDialog(); toast(`Added ${v("#ap-name")}`); hooks.refresh(); location.hash = `#/p/${encodeURIComponent(v("#ap-name"))}`;
    } catch (e) { toast(e.message, "err"); }
  };
}

export function shortcuts() {
  const k = [["⌘K", "Search, jump, run an action"], ["⌘J", "Show or hide the chat"], ["⌃`", "Show or hide terminals"], ["⌘N", "New session"],
    ["⌘1 … ⌘9", "Switch project"], ["⌃Tab", "Next session in the chat"], ["⌘I", "Inbox"], ["⇧⌘A", "Next thing that needs you"], ["Tab, ⏎", "Move between and open sessions and files"], ["⇧⌘H", "Show herdr (app)"], ["⌘,", "Settings"], ["⌘/", "This sheet"],
    ["Esc", "Close a dialog · interrupt the agent (empty composer)"]];
  const d = dialog(`<div class="dh">Keyboard</div><div class="db"><div class="shortcuts">${k.map(([a, b]) => `<kbd>${esc(a)}</kbd><span>${esc(b)}</span>`).join("")}</div></div>
    <div class="df"><button class="btn" id="dlg-cancel">Close</button></div>`, { width: 460 });
  $("#dlg-cancel", d).onclick = closeDialog;
}

export function rememberPreset(id) { store("preset", id); }

export async function peekJob(host, session) {
  const d = dialog(`<div class="dh">tmux ${esc(session)} <span class="muted" style="font-weight:400">on ${esc(host)}</span></div>
    <div class="db"><pre id="pk" style="max-height:52vh;overflow:auto;white-space:pre"><span class="spin"></span></pre></div>
    <div class="df"><span class="grow muted" id="pk-st" style="font-size:12px"></span><button class="btn" id="pk-ref">${icon("refresh")} Refresh</button>
      <button class="btn" id="pk-att">${icon("term")} Attach</button><button class="btn primary" id="dlg-cancel">Close</button></div>`, { width: 900 });
  const load = async () => {
    try {
      const r = await get("/api/tmux", { host, session });
      $("#pk", d).textContent = r.text || "(empty)";
      $("#pk-st", d).textContent = r.alive ? "Read-only snapshot of the last 200 lines" : "No such tmux session now (finished?). Showing what the server said.";
      $("#pk", d).scrollTop = $("#pk", d).scrollHeight;
    } catch (e) { $("#pk", d).textContent = e.message; }
  };
  $("#pk-ref", d).onclick = load;
  $("#pk-att", d).onclick = () => { closeDialog(); hooks.openTerminal({ kind: "tmux", host, session, label: `tmux ${session} @ ${host}` }); };
  $("#dlg-cancel", d).onclick = closeDialog;
  load();
}
