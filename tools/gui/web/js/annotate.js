// Mark a figure and ask a session to fix it: numbered circles or boxes drawn on a copy, a note, the session to ask.
// The backend (/api/figure-fix) puts the marked copy where that session runs and sends it the original's path, the
// copy's path and the note. Defaults to the worker of the ticket the figure belongs to, else the desk, else the chat.
import { S, $, esc, post, toast, icon, hooks, allAgents, agentLabel } from "./core.js";
import { closeDialog } from "./dialogs.js";

const RED = "#e2553a", MAX_SIDE = 2400;

function sessionsFor(path) {
  const live = allAgents().filter((a) => a.project === S.route.project && a.status !== "ended" && (!a.remote || a.live) && a.role !== "btw");
  const owner = live.find((a) => a.role === "worker" && a.map_folder && a.ticket_folder && path.includes(`${a.map_folder}/tickets/${a.ticket_folder}/`));
  const pick = owner || live.find((a) => a.role === "desk") || live.find((a) => a.pane === S.chat?.pane) || live[0];
  return { live, pick };
}

export function markFigure({ side, path, src }) {
  const { live, pick } = sessionsFor(path);
  const o = $("#overlay");
  o.hidden = false;
  o.innerHTML = `<div class="dialog markfig" style="width:min(1100px,94vw);max-height:92vh">
    <div class="dh mk-head"><span>Mark what to fix</span><span class="muted mono mk-path" title="${esc(path)}">${esc(path.split("/").pop())}</span><span class="grow"></span>
      <div class="seg"><button class="btn sm on" data-tool="circle" title="Drag to circle something (C)">◯ Circle</button><button class="btn sm" data-tool="box" title="Drag to box something (B)">▢ Box</button></div>
      <button class="btn sm" id="mk-undo" title="Remove the last mark (⌘Z)">Undo</button><button class="btn ghost sm icon" id="mk-x" title="Close (Esc)">${icon("x")}</button></div>
    <div class="db"><div class="mk-stage"><canvas id="mk-c"></canvas></div>
      <textarea id="mk-note" rows="2" placeholder="What to change. Refer to the marks by number, e.g. 1: label the y axis; 2: use a log scale"></textarea></div>
    <div class="df"><span class="muted mk-hint">${live.length ? "Marks go on a copy; the figure itself is unchanged." : "No live session in this project: start one first."}</span><span class="grow"></span>
      <label class="muted" for="mk-to">Ask</label><select id="mk-to" ${live.length ? "" : "disabled"}>${live.map((a) => `<option value="${esc(a.pane)}" ${a === pick ? "selected" : ""}>${esc(agentLabel(a))}${a.machine ? ` · ${esc(a.machine)}` : ""}</option>`).join("")}</select>
      <button class="btn primary" id="mk-send" ${live.length ? "" : "disabled"} title="Send (⌘↩)">Send</button></div></div>`;
  const d = o.firstChild, c = $("#mk-c", d), ctx = c.getContext("2d");
  const img = new Image();
  const marks = [];
  let tool = "circle", drag = null, k = 1;

  const close = () => { document.removeEventListener("keydown", keys, true); closeDialog(); };
  o.onclick = (e) => { if (e.target === o) close(); };

  function draw(g, scale, list, w, h) {        // the image, then each mark (in image pixels) at `scale`
    g.drawImage(img, 0, 0, w, h);
    const lw = Math.max(2.5, Math.min(w, h) / 220), r = Math.max(9, Math.min(w, h) / 45);
    list.forEach((m, i) => {
      const x0 = Math.min(m.x0, m.x1) * scale, y0 = Math.min(m.y0, m.y1) * scale, x1 = Math.max(m.x0, m.x1) * scale, y1 = Math.max(m.y0, m.y1) * scale;
      g.strokeStyle = RED; g.lineWidth = lw;
      g.beginPath();
      if (m.tool === "box") g.rect(x0, y0, x1 - x0, y1 - y0);
      else g.ellipse((x0 + x1) / 2, (y0 + y1) / 2, Math.max(2, (x1 - x0) / 2), Math.max(2, (y1 - y0) / 2), 0, 0, 2 * Math.PI);
      g.stroke();
      if (m.num) {                               // the number the note refers to, at the mark's top-left
        const bx = Math.max(r, x0), by = Math.max(r, y0);
        g.fillStyle = RED; g.beginPath(); g.arc(bx, by, r, 0, 2 * Math.PI); g.fill();
        g.fillStyle = "#fff"; g.font = `600 ${Math.round(r * 1.2)}px -apple-system, system-ui, sans-serif`;
        g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(String(m.num), bx, by + 0.5);
      }
    });
  }
  const redraw = () => draw(ctx, k, drag ? [...marks, drag] : marks, c.width, c.height);

  img.onload = () => {
    const stage = $(".mk-stage", d);
    k = Math.min(1, (stage.clientWidth || 900) / img.naturalWidth, (window.innerHeight * 0.6) / img.naturalHeight);
    c.width = Math.round(img.naturalWidth * k); c.height = Math.round(img.naturalHeight * k);
    redraw();
  };
  img.src = src;

  const at = (e) => { const r = c.getBoundingClientRect(); return { x: (e.clientX - r.left) / k * (c.width / r.width), y: (e.clientY - r.top) / k * (c.height / r.height) }; };
  c.onpointerdown = (e) => { c.setPointerCapture(e.pointerId); const p = at(e); drag = { tool, x0: p.x, y0: p.y, x1: p.x, y1: p.y, num: marks.length + 1 }; };
  c.onpointermove = (e) => { if (!drag) return; const p = at(e); drag.x1 = p.x; drag.y1 = p.y; redraw(); };
  c.onpointerup = () => {
    if (drag && Math.abs(drag.x1 - drag.x0) * k > 6 && Math.abs(drag.y1 - drag.y0) * k > 6) marks.push(drag);   // a click is not a mark
    drag = null; redraw();
  };
  const setTool = (t) => { tool = t; d.querySelectorAll("[data-tool]").forEach((b) => b.classList.toggle("on", b.dataset.tool === t)); };
  d.querySelectorAll("[data-tool]").forEach((b) => b.onclick = () => setTool(b.dataset.tool));
  $("#mk-undo", d).onclick = () => { marks.pop(); redraw(); };
  $("#mk-x", d).onclick = close;

  async function send() {
    const pane = $("#mk-to", d).value, note = $("#mk-note", d).value.trim();
    if (!pane) return;
    if (!marks.length && !note) return toast("Mark something or write what to change", "err");
    const e = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));   // the copy: full size, at most 2400 px
    const out = document.createElement("canvas");
    out.width = Math.round(img.naturalWidth * e); out.height = Math.round(img.naturalHeight * e);
    draw(out.getContext("2d"), e, marks, out.width, out.height);
    const b64 = out.toDataURL("image/png").split(",")[1];
    const btn = $("#mk-send", d); btn.disabled = true; btn.textContent = "Sending…";
    try {
      await post("/api/figure-fix", { project: S.route.project, side, path, pane, note, b64 });
      const a = live.find((x) => x.pane === pane);
      toast(`Sent to ${a ? agentLabel(a) : "the session"}`);
      close();
      hooks.openChat(pane);
    } catch (err) { toast(err.message, "err", 6000); btn.disabled = false; btn.textContent = "Send"; }
  }
  $("#mk-send", d).onclick = send;
  function keys(e) {
    if (!d.isConnected) return document.removeEventListener("keydown", keys, true);
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); }
    else if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); send(); }
    else if ((e.metaKey || e.ctrlKey) && e.key === "z" && document.activeElement !== $("#mk-note", d)) { e.preventDefault(); marks.pop(); redraw(); }
    else if (document.activeElement !== $("#mk-note", d) && !e.metaKey && !e.ctrlKey && (e.key === "c" || e.key === "b")) setTool(e.key === "c" ? "circle" : "box");
  }
  document.addEventListener("keydown", keys, true);
}
