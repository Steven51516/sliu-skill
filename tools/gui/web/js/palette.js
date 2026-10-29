// ⌘K: one box to jump to a project, map, ticket or session, or run an action (including a skill in a new session).
import { S, $, esc, go, goMap, hooks, allAgents, agentLabel } from "./core.js";
import { closeDialog } from "./dialogs.js";
import { PRESETS } from "./dialogs.js";

function items() {
  const out = [];
  const proj = S.route.project;
  const act = (a, b, run, k = "action") => out.push({ k, a, b, run });
  if (proj) {
    act("Start the team", proj, () => hooks.startTeam(proj));
    act("New session…", proj, () => hooks.newSession(proj));
    PRESETS.filter((p) => p.id !== "plain" && p.id !== "custom").forEach((p) => act(p.label + "…", `${p.prompt.split(" ")[0]} · new session`, () => hooks.newSession(proj, p.id), "skill"));
    act("Talk to the desk", proj, () => { const d = hooks.deskPane(proj); d ? hooks.openChat(d) : hooks.startTeam(proj); });
    act("Shell in this project", proj, () => hooks.openTerminal({ kind: "shell", project: proj }), "terminal");
    if (S.data?.server) act(`SSH to ${S.data.server}`, S.data.server_root, () => hooks.openTerminal({ kind: "ssh", project: proj, server: S.data.server, label: `ssh ${S.data.server}` }), "terminal");
    act("Files", proj, () => go({ project: proj, view: "files" }), "go");
  }
  act("Inbox", "everything waiting on you", () => go({ view: "inbox" }), "go");
  act("GPUs", "nvidia-smi on the servers", () => go({ view: "gpus" }), "go");
  act("Settings", "projects, servers, notifications", () => go({ view: "settings" }), "go");
  act("Toggle chat", "⌘J", () => hooks.toggleChat());
  act("Toggle terminals", "⌃`", () => hooks.toggleDock());
  act("Keyboard shortcuts", "⌘/", () => hooks.shortcuts());
  (S.summary?.projects || []).forEach((p) => out.push({ k: "project", a: p.name, b: `${(p.waiting || []).length} waiting · ${(p.agents || []).length} agents`, run: () => go({ project: p.name }) }));
  allAgents().forEach((a) => out.push({ k: "session", a: agentLabel(a), b: `${a.project || "outside projects"} · ${a.status}${a.title ? " · " + a.title : ""}`, run: () => hooks.openChat(a.pane) }));
  if (S.data) S.data.maps.forEach((m) => {
    out.push({ k: "map", a: `${m.id} ${m.title}`, b: m.status, run: () => goMap(S.data.name, m.folder) });
    m.tickets.forEach((t) => out.push({ k: "ticket", a: `${t.id} ${t.title}`, b: `${t.status} · ${t.type || ""}`, run: () => goMap(S.data.name, m.folder, t.folder) }));
  });
  return out;
}

function score(q, s) {
  if (!q) return 1;
  s = s.toLowerCase();
  const i = s.indexOf(q);
  if (i >= 0) return 100 - i + (i === 0 || s[i - 1] === " " ? 50 : 0);
  let j = 0, sc = 0;
  for (const c of s) { if (c === q[j]) { j++; sc += 1; } if (j === q.length) return sc; }
  return 0;
}

export function palette() {
  const o = $("#overlay");
  o.hidden = false;
  o.innerHTML = `<div class="palette"><input id="pl-q" placeholder="Search projects, maps, tickets, sessions, actions…" autocomplete="off" spellcheck="false">
    <div class="list" id="pl-list"></div><div class="foot"><span>↑↓ move</span><span>⏎ open</span><span>esc close</span></div></div>`;
  o.onclick = (e) => { if (e.target === o) closeDialog(); };
  const all = items(), inp = $("#pl-q"), list = $("#pl-list");
  let shown = [], sel = 0;
  const draw = () => {
    const q = inp.value.trim().toLowerCase();
    shown = all.map((it) => ({ it, s: Math.max(score(q, it.a), score(q, it.k + " " + it.a) * 0.8, score(q, it.b || "") * 0.5) }))
      .filter((x) => x.s > 0).sort((a, b) => b.s - a.s).slice(0, 60).map((x) => x.it);
    sel = Math.min(sel, Math.max(0, shown.length - 1));
    list.innerHTML = shown.map((it, i) => `<div class="pi ${i === sel ? "on" : ""}" data-i="${i}"><span class="k">${esc(it.k)}</span><span class="a">${esc(it.a)}</span><span class="b">${esc(it.b || "")}</span></div>`).join("")
      || `<div class="empty">Nothing matches.</div>`;
    list.querySelectorAll(".pi").forEach((el) => el.onclick = () => run(+el.dataset.i));
    list.querySelector(".pi.on")?.scrollIntoView({ block: "nearest" });
  };
  const run = (i) => { const it = shown[i]; closeDialog(); if (it) it.run(); };
  inp.oninput = () => { sel = 0; draw(); };
  inp.onkeydown = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(shown.length - 1, sel + 1); draw(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(0, sel - 1); draw(); }
    else if (e.key === "Enter") { e.preventDefault(); run(sel); }
    else if (e.key === "Escape") closeDialog();
  };
  draw();
  setTimeout(() => inp.focus(), 10);
}
