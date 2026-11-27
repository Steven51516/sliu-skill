// The paper reader: a PDF drawn by PDF.js, so its text can be selected. Ask works on a selection, or on a box drawn
// around an equation or a figure: the passage (or a crop of the box), its page and the question go to a session, the
// way Mark & ask sends a figure (annotate.js).
// Marks are the highlights kept beside the PDF in <name>.marks.json (/api/marks): what you highlighted or asked about,
// with the session's reply pinned to it, and what an agent marked (a claim, the method, a result, a limitation).
import { S, $, esc, get, post, toast, icon, md, hooks, store, allAgents, agentLabel, markSent } from "./core.js";

const V = "/vendor/pdfjs/";
const KINDS = { claim: "Claim", method: "Method", result: "Result", limit: "Limitation", ask: "Asked", note: "Highlight" };
const R = (a) => ({ l: a[0], t: a[1], w: a[2], h: a[3] });       // a kept rect, as fractions of its page
const flat = (r) => [r.l, r.t, r.w, r.h].map((x) => +x.toFixed(5));
const norm = (t) => String(t || "").replace(/\s+/g, " ").trim();
let lib = null;

// A question about a passage, as the message a session gets, and read back from a conversation (the chat draws it as
// the passage, folded, and the question). Claude Code wraps a pasted message in <pasted_content> tags.
const LEAD = "Read the pages around this in the PDF before you answer, cite the page or equation, and write math as LaTeX ($…$).";
const askText = (file, where, quote, question) => `From ${file}, ${where}:\n\n> ${quote}\n\n${question}`;
const boxText = (file, where, crop, question) => `A region of ${file}, ${where}, cropped here: ${crop}\n\n${question}`;
export function readAsk(text) {
  const t = text.replace(/<\\?\/?pasted_content[^>]*>/g, "").trim().replace(LEAD, "").trim();
  const m = t.match(/^From (.+), (pp?\. [\d–]+):\n\n> (.+)\n\n([\s\S]+)$/), b = !m && t.match(/^A region of (.+), (p\. \d+), cropped here: (\S+)\n\n([\s\S]+)$/);
  return m ? { file: m[1], where: m[2], quote: m[3], question: m[4] } : b ? { file: b[1], where: b[2], crop: b[3], question: b[4] } : null;
}

// pdf.js and its viewer, loaded on first use. The viewer's stylesheet is scoped to .pdfbox: it styles .dialog, .page and
// other class names the app uses too.
function load() {
  return lib || (lib = (async () => {
    const css = (await (await fetch(V + "pdf_viewer.css")).text()).replaceAll(":root", ":scope").replace(/url\((["']?)images\//g, `url($1${V}images/`);
    const st = document.createElement("style");
    st.textContent = `@scope (.pdfbox) {\n${css}\n}`;
    document.head.appendChild(st);
    const pdfjs = await import(V + "pdf.min.js");
    globalThis.pdfjsLib = pdfjs;                   // pdf_viewer.js reads the library from this global
    pdfjs.GlobalWorkerOptions.workerSrc = V + "pdf.worker.min.js";
    return { pdfjs, view: await import(V + "pdf_viewer.js") };
  })().catch((e) => { lib = null; throw e; }));
}

// Draws the PDF at `url` into el's .pdfbox and adds zoom, page and Box & ask to its .vhead. Returns a function that
// frees the document. `gone(folder)` is called after Delete paper moved the PDF's folder to the trash; `open(path)`
// shows another file of the project (the paper's note).
export async function showPdf(el, { side, path, url, gone, open }) {
  const req = el._req, alive = () => el._req === req && el.isConnected;
  const box = $(".pdfbox", el), scroll = $(".pdfscroll", el);
  let L, task, doc;
  try {
    L = await load();
    task = L.pdfjs.getDocument({ url, cMapUrl: V + "cmaps/", standardFontDataUrl: V + "standard_fonts/", wasmUrl: V + "wasm/", useWasm: false });
    doc = await task.promise;
  } catch (e) {
    if (alive()) box.innerHTML = `<div class="err" style="padding:16px">Couldn't open this PDF: ${esc(e.message)}</div>`;
    return null;
  }
  if (!alive()) { task.destroy(); return null; }
  $(".spin", box)?.remove();
  const bus = new L.view.EventBus();
  const links = new L.view.PDFLinkService({ eventBus: bus, externalLinkTarget: L.view.LinkTarget.BLANK });
  const pv = new L.view.PDFViewer({ container: scroll, eventBus: bus, linkService: links, imageResourcesPath: V + "images/" });
  links.setViewer(pv);
  pv.setDocument(doc);
  links.setDocument(doc, null);

  const key = `pdf.${S.route.project}:${side}:${path}`;       // the page you were on, kept per file
  const marks = [];                                            // what is being asked about: {page, rects: [{l,t,w,h}]} in page fractions
  let keep = side === "local";                                 // marks are kept for a PDF on this Mac
  let saved = [], boxing = false;                              // saved: the marks kept beside the PDF

  const fit = () => { pv.currentScaleValue = "auto"; };
  if ($(".vhead #vsize", el)) {
    $(".vhead #vsize", el).insertAdjacentHTML("afterend", `<span class="pdfctl">
      <button class="btn ghost sm icon" id="pz-out" title="Zoom out">−</button><button class="btn ghost sm" id="pz-val" title="Fit the width">100%</button><button class="btn ghost sm icon" id="pz-in" title="Zoom in">+</button>
      <span class="muted" id="pg-n"></span>
      ${keep ? `<button class="btn ghost sm icon" id="pmarks" title="Show or hide the highlights">${icon("eye")}</button>` : ""}
      <button class="btn sm" id="pbox" title="Drag a box around an equation or a figure and ask about it. For text, select it and press Ask.">${icon("mark")} Box &amp; ask</button></span>`);
    $("#pz-out", el).onclick = () => pv.decreaseScale();
    $("#pz-in", el).onclick = () => pv.increaseScale();
    $("#pz-val", el).onclick = fit;
    $("#pbox", el).onclick = () => setBoxing(!boxing);
    const hide = (on) => { box.classList.toggle("nomarks", on); $("#pmarks", el)?.classList.toggle("off", on); };
    hide(!!store("pdf.nomarks"));
    if ($("#pmarks", el)) $("#pmarks", el).onclick = () => { const on = !box.classList.contains("nomarks"); store("pdf.nomarks", on); hide(on); closeTip(); };
  }
  // A paper's folder holds the PDF beside its note.md. Delete paper moves that folder to the trash (undone with
  // `trash --restore`).
  const dir = path.split("/").slice(0, -1).join("/");
  if (side === "local" && dir && $(".vhead #vvs", el)) get("/api/tree", { project: S.route.project, side, path: dir }).then((j) => {
    if (!alive() || !j.entries.some((e) => e.name === "note.md")) return;
    if (open) {
      $(".vhead #vvs", el).insertAdjacentHTML("beforebegin", `<button class="btn sm" id="pnote" title="Open this paper's note">${icon("doc")} Note</button>`);
      $("#pnote", el).onclick = () => open(`${dir}/note.md`);
    }
    $(".vhead #vvs", el).insertAdjacentHTML("beforebegin", `<button class="btn sm danger" id="pdel" title="Move this paper's folder (note, PDF, figures) to the trash">${icon("trash")} Delete paper</button>`);
    $("#pdel", el).onclick = async () => {
      if (!window.confirm(`Delete this paper?\n\n${dir}/ (its note, PDF and figures) moves to the trash.\nUndo: trash --restore "${S.data.path}/${dir}"`)) return;
      try {
        const r = await post("/api/trash", { project: S.route.project, path: dir });
        toast(r.dry_run ? `Dry run: ${r.path} would move to the trash` : "Paper moved to the trash", "", 6000);
        if (!r.dry_run) gone?.(dir);
      } catch (e) { toast(e.message, "err", 7000); }
    };
  }).catch(() => {});

  bus.on("pagesinit", () => { fit(); const p = store(key); if (p > 1 && p <= pv.pagesCount) pv.currentPageNumber = p; pageLabel(); });
  bus.on("scalechanging", (e) => { const v = $("#pz-val", el); if (v) v.textContent = Math.round(e.scale * 100) + "%"; });
  bus.on("pagechanging", (e) => { store(key, e.pageNumber); pageLabel(); });
  bus.on("pagerendered", (e) => paint(e.pageNumber));
  function pageLabel() { const n = $("#pg-n", el); if (n) n.textContent = `${pv.currentPageNumber} / ${pv.pagesCount}`; }

  let auto = true;                                             // refit when the pane's width changes, until you zoom by hand
  bus.on("scalechanging", (e) => { auto = e.presetValue === "auto"; });
  const ro = new ResizeObserver(() => requestAnimationFrame(() => { if (auto && pv.pagesCount && alive()) fit(); }));
  ro.observe(scroll);
  // pinch on the trackpad, or ⌘/Ctrl with the wheel, zooms about the pointer (the page would zoom the whole window)
  let want = 0, settle = 0;
  scroll.addEventListener("wheel", (e) => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    want = Math.max(0.25, Math.min(6, (want || pv.currentScale) * Math.exp(-e.deltaY / 100)));   // small steps add up
    pv.updateScale({ scaleFactor: want / pv.currentScale, origin: [e.clientX, e.clientY], drawingDelay: 250 });
    clearTimeout(settle);
    settle = setTimeout(() => { want = 0; }, 300);
  }, { passive: false });

  // ----- the kept marks and what is being asked about, drawn over their page (pdf.js rebuilds a page's layers when
  // it redraws). The rects take no clicks, so the text under them can still be selected; a click is matched by place. -----
  function paint(n) {
    const pg = pv.getPageView(n - 1)?.div;
    if (!pg) return;
    pg.querySelector(".rdmarks")?.remove();
    const div = (r, cls) => `<div class="rdmark ${cls}" style="left:${r.l * 100}%;top:${r.t * 100}%;width:${r.w * 100}%;height:${r.h * 100}%"></div>`;
    const html = saved.filter((m) => m.page === n).flatMap((m) => m.rects.map((r) => div(R(r), `saved k-${KINDS[m.kind] ? m.kind : "note"}${m.box ? " box" : ""}`)))
      .concat(marks.filter((m) => m.page === n).flatMap((m) => m.rects.map((r) => div(r, m.box ? "box" : "")))).join("");
    if (!html) return;
    const layer = document.createElement("div");
    layer.className = "rdmarks";
    layer.innerHTML = html;
    pg.appendChild(layer);
  }
  function repaint(also = []) {
    const pages = new Set([...saved, ...marks, ...also].map((m) => m.page));
    scroll.querySelectorAll(".rdmarks").forEach((l) => pages.add(+l.closest(".page").dataset.pageNumber));
    pages.forEach(paint);
  }
  function setMarks(list) {
    const old = marks.splice(0, marks.length, ...list);
    repaint(old);
  }
  async function loadMarks() {
    if (!keep) return;
    try { saved = (await get("/api/marks", { project: S.route.project, path })).marks || []; }
    catch (_) { keep = false; $("#pmarks", el)?.remove(); return; }   // a backend from before marks: read and ask as before
    if (!alive()) return;
    repaint();
    if (saved.some((m) => m.question)) (hooks.chatTurns?.() || []).forEach(pin);   // replies that came before this paper was open
  }
  let queue = Promise.resolve();                               // one change at a time: the backend rewrites the whole file
  function change(body) {                                      // put a mark or delete one; the backend answers with them all
    return (queue = queue.then(async () => {
      try { saved = (await post("/api/marks", { project: S.route.project, path, ...body })).marks || []; repaint(); return true; }
      catch (e) { toast(`The highlight wasn't saved: ${e.message}`, "err", 6000); return false; }
    }));
  }
  loadMarks();
  const frame = (pg) => { const r = pg.getBoundingClientRect(); return { x: r.left + pg.clientLeft, y: r.top + pg.clientTop, w: pg.clientWidth, h: pg.clientHeight }; };

  // ----- ask about selected text -----
  function selection() {
    const sel = document.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount || !scroll.contains(sel.anchorNode) || !scroll.contains(sel.focusNode)) return null;
    const quote = sel.toString().replace(/-\n(?=[a-z])/g, "").replace(/\s+/g, " ").trim();   // a word split at a line end is joined
    if (quote.length < 2) return null;
    const range = sel.getRangeAt(0), by = new Map(), top = range.commonAncestorContainer;
    const walk = document.createTreeWalker(top.nodeType === 1 ? top : top.parentNode, NodeFilter.SHOW_TEXT);
    let at = null;
    for (let n = walk.nextNode(); n; n = walk.nextNode()) {    // the selected part of each piece of text (the range's own
      const pg = n.parentElement.closest(".textLayer")?.closest(".page");   // rects would add whole pages and layers)
      if (!pg || !range.intersectsNode(n)) continue;
      const part = document.createRange();
      part.setStart(n, n === range.startContainer ? range.startOffset : 0);
      part.setEnd(n, n === range.endContainer ? range.endOffset : n.nodeValue.length);
      const f = frame(pg), num = +pg.dataset.pageNumber;
      for (const r of part.getClientRects()) {
        if (r.width < 1 || r.height < 1) continue;
        if (!by.has(num)) by.set(num, []);
        by.get(num).push({ l: (r.left - f.x) / f.w, t: (r.top - f.y) / f.h, w: r.width / f.w, h: r.height / f.h });
        at = r;
      }
    }
    if (!at) return null;
    const list = [...by].sort((a, b) => a[0] - b[0]).map(([page, rects]) => ({ page, rects: lines(rects) }));
    return { quote, marks: list, pages: list.map((m) => m.page), at };
  }
  const kept = (m, more) => ({ id: crypto.randomUUID().slice(0, 8), page: m.page, rects: m.rects.map(flat), by: "you", ...more });   // a selection over pages keeps its first page
  function lines(rects) {                                      // rects that share a line become one
    const out = [];
    rects.sort((a, b) => a.t - b.t || a.l - b.l).forEach((r) => {
      const last = out[out.length - 1];
      if (last && Math.min(last.t + last.h, r.t + r.h) - Math.max(last.t, r.t) > 0.5 * Math.min(last.h, r.h)) {
        const l = Math.min(last.l, r.l), t = Math.min(last.t, r.t);
        Object.assign(last, { w: Math.max(last.l + last.w, r.l + r.w) - l, h: Math.max(last.t + last.h, r.t + r.h) - t, l, t });
      } else out.push({ ...r });
    });
    return out;
  }
  const onUp = (e) => {                                        // anywhere: a drag may end outside the page
    const mine = !!tip?.contains(e.target);                    // a click in the tip itself, read now: the click replaces the tip
    setTimeout(() => {
    if (boxing || !alive() || mine) return;
    const s = selection();
    if (!s) { if (tip?.className === "asktip") closeTip(); return; }
    const go = pop(`<button class="btn sm primary" id="ask-go">${icon("chat")} Ask</button>${keep ? `<button class="btn sm" id="hl-go" title="Keep this passage highlighted">Highlight</button>` : ""}`, s.at, "asktip");
    $("#ask-go", go).onclick = () => { setMarks(s.marks); document.getSelection().removeAllRanges(); askBox(s.at, { pages: s.pages, quote: s.quote, mark: s.marks[0] }); };
    if ($("#hl-go", go)) $("#hl-go", go).onclick = () => { document.getSelection().removeAllRanges(); closeTip(); change({ put: kept(s.marks[0], { kind: "note", quote: s.quote }) }); };
    }, 0);
  };
  document.addEventListener("mouseup", onUp);

  // ----- ask about a boxed region: an equation, a figure, a table -----
  function setBoxing(on) {
    boxing = on;
    box.classList.toggle("boxing", on);
    $("#pbox", el)?.classList.toggle("primary", on);
    if (on) { closeTip(); document.getSelection().removeAllRanges(); }
  }
  scroll.addEventListener("pointerdown", (e) => {
    const pg = boxing && e.button === 0 && e.target.closest(".page");
    if (!pg) return;
    e.preventDefault();
    const f = frame(pg), n = +pg.dataset.pageNumber;
    const at = (ev) => ({ x: Math.max(0, Math.min(1, (ev.clientX - f.x) / f.w)), y: Math.max(0, Math.min(1, (ev.clientY - f.y) / f.h)) });
    const a = at(e);
    const rect = (b) => ({ l: Math.min(a.x, b.x), t: Math.min(a.y, b.y), w: Math.abs(a.x - b.x), h: Math.abs(a.y - b.y) });
    const move = (ev) => setMarks([{ page: n, box: true, rects: [rect(at(ev))] }]);
    const up = async (ev) => {
      scroll.removeEventListener("pointermove", move);
      const r = rect(at(ev));
      setBoxing(false);
      if (r.w * f.w < 8 || r.h * f.h < 8) return setMarks([]);   // a click, not a box
      setMarks([{ page: n, box: true, rects: [r] }]);
      const m = pg.querySelector(".rdmark")?.getBoundingClientRect() || pg.getBoundingClientRect();
      try { askBox(m, { pages: [n], image: await crop(n, r), mark: { page: n, rects: [r] } }); }
      catch (err) { setMarks([]); toast(`Couldn't crop that region: ${err.message}`, "err", 6000); }
    };
    try { scroll.setPointerCapture(e.pointerId); } catch (_) { /* the pointer is already up */ }
    scroll.addEventListener("pointermove", move);
    scroll.addEventListener("pointerup", up, { once: true });
  });
  async function crop(n, r) {                                  // the region drawn again at 3x (about 216 dpi), whatever the zoom
    const page = await doc.getPage(n), scale = 3, full = page.getViewport({ scale });
    const c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(r.w * full.width));
    c.height = Math.max(1, Math.round(r.h * full.height));
    await page.render({ canvas: c, viewport: page.getViewport({ scale, offsetX: -r.l * full.width, offsetY: -r.t * full.height }) }).promise;
    return c.toDataURL("image/png");
  }

  // ----- the question: what to ask, whom to ask -----
  function sessions() {
    const live = allAgents().filter((a) => a.project === S.route.project && a.status !== "ended" && (!a.remote || a.live));
    const pick = live.find((a) => a.pane === S.chat.pane) || live.find((a) => a.role === "desk")
      || [...live].sort((a, b) => (Date.parse(b.turn_end || 0) || 0) - (Date.parse(a.turn_end || 0) || 0))[0];
    return { live, pick };
  }
  function askBox(at, ctx) {
    const { live, pick } = sessions();
    const where = ctx.pages.length > 1 ? `pp. ${ctx.pages[0]}–${ctx.pages[ctx.pages.length - 1]}` : `p. ${ctx.pages[0]}`;
    const p = pop(`<div class="ah"><span class="muted">${where}</span>${ctx.image ? `<img src="${ctx.image}" alt="the boxed region">` : `<span class="q">${esc(ctx.quote)}</span>`}
        <button class="btn ghost sm icon" id="ask-x" title="Close (Esc)">${icon("x")}</button></div>
      <textarea id="ask-q" rows="2" placeholder="${ctx.image ? "Ask about this region… (empty: explain it)" : "Ask about this passage… (empty: explain it)"}"></textarea>
      <div class="af">${live.length ? `<label class="muted" for="ask-to">Ask</label><select id="ask-to">${live.map((a) => `<option value="${esc(a.pane)}" ${a === pick ? "selected" : ""}>${esc(agentLabel(a))}${a.machine ? ` · ${esc(a.machine)}` : ""}</option>`).join("")}
        <option value="">A new Claude session</option></select>` : `<span class="muted">Starts a Claude session</span>`}<span class="grow"></span><button class="btn sm primary" id="ask-send" title="Send (⏎) · new line: ⇧⏎">Send</button></div>`, at, "askpop");
    const q = $("#ask-q", p), send = $("#ask-send", p);
    $("#ask-x", p).onclick = closeTip;
    q.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send.click(); } };
    send.onclick = async () => {
      const pane = $("#ask-to", p)?.value || "";               // none: a new session is started with the question
      send.disabled = true;
      try {
        const file = side === "server" ? `${S.data.server}:${S.data.server_root.replace(/\/$/, "")}/${path}` : `${S.data.path}/${path}`;
        let text, asked, crop;
        if (ctx.image) {
          const up = await post("/api/paste", { pane, b64: ctx.image.split(",")[1], name: "region.png", type: "image/png" });
          asked = q.value.trim() || "Explain what this shows.";
          crop = up.path;
          text = boxText(file, where, up.path, asked);
        } else {
          asked = q.value.trim() || "Explain this passage.";
          text = askText(file, where, ctx.quote.length > 6000 ? ctx.quote.slice(0, 6000) + "…" : ctx.quote, asked);
        }
        if (!pane) await startSession(`${LEAD}\n\n${text}`);
        else {
          await post("/api/chat/send", { pane, text });
          markSent(pane);
          hooks.openChat(pane, { focus: false });
        }
        // the passage stays marked, waiting for the reply: `question` is what the reply will answer (ended, below)
        if (keep) change({ put: ctx.old ? { ...ctx.old, kind: ctx.old.by === "agent" ? ctx.old.kind : "ask", question: asked, crop: crop || ctx.old.crop } : kept(ctx.mark, { kind: "ask", quote: ctx.quote || "", box: !!ctx.image, question: asked, ...(crop ? { crop } : {}) }) });
        closeTip();
      } catch (e) { toast(e.message, "err", 6000); send.disabled = false; }
    };
    setTimeout(() => q.focus(), 0);
  }

  // No session to ask: a new Claude session in the project, its first message the question; the chat opens on it.
  async function startSession(text) {
    const { job } = await post("/api/session", { project: S.route.project, kind: "claude", prompt: text, label: (path.split("/").slice(-2, -1)[0] || "reader").slice(0, 28) });
    toast("Starting a Claude session with your question…", "", 5000);
    (async () => {
      for (;;) {
        const j = await get("/api/job", { id: job });
        if (!j.done) { await new Promise((r) => setTimeout(r, 800)); continue; }
        hooks.refresh();
        if (!j.ok) toast(`The session did not start: ${j.log[j.log.length - 1] || ""}`, "err", 8000);
        else if (j.panes[0]) setTimeout(() => hooks.openChat(j.panes[0], { focus: false }), 1500);
        else toast("Dry run: no session was started", "", 5000);
        return;
      }
    })().catch((e) => toast(e.message, "err", 6000));
  }

  // ----- a kept mark: its note (the pinned reply, the agent's gloss, or your own words), ask again, delete -----
  scroll.addEventListener("click", (e) => {
    const pg = e.target.closest?.(".page");
    if (!pg || boxing || !document.getSelection().isCollapsed || box.classList.contains("nomarks")) return;
    const f = frame(pg), x = (e.clientX - f.x) / f.w, y = (e.clientY - f.y) / f.h, n = +pg.dataset.pageNumber;
    for (const m of saved.filter((k) => k.page === n)) {
      const r = m.rects.map(R).find((k) => x >= k.l && x <= k.l + k.w && y >= k.t - 0.002 && y <= k.t + k.h + 0.002);
      if (r) return viewMark(m, { left: f.x + r.l * f.w, top: f.y + r.t * f.h, bottom: f.y + (r.t + r.h) * f.h });
    }
  });
  function viewMark(m, at) {
    const own = m.by !== "agent" && m.kind === "note";
    const p = pop(`<div class="ah"><span class="muted">${KINDS[m.kind] || "Highlight"} · p. ${m.page}</span><span class="grow"></span>
        <button class="btn ghost sm" id="mk-ask" title="Ask about this passage">${icon("chat")} Ask</button>
        <button class="btn ghost sm icon" id="mk-del" title="Remove this highlight (Delete)">${icon("trash")}</button>
        <button class="btn ghost sm icon" id="ask-x" title="Close (Esc)">${icon("x")}</button></div>
      ${m.quote ? `<div class="q">${esc(m.quote)}</div>` : ""}
      ${own ? `<textarea id="mk-note" rows="2" placeholder="Your note…">${esc(m.note || "")}</textarea><div class="af"><span class="grow"></span><button class="btn sm primary" id="mk-save">Save</button></div>` : `<div class="mn"></div>`}
      ${m.question ? `<div class="muted mw">No reply pinned yet to “${esc(m.question)}”. It is pinned when the session has replied and its chat is open here.</div>` : ""}`, at, "askpop markpop");
    if (!own && m.note) md($(".mn", p), m.note);
    p._mark = m;                                               // Delete removes it (esc2)
    $("#ask-x", p).onclick = closeTip;
    $("#mk-del", p).onclick = () => { closeTip(); change({ delete: m.id }); };
    if (own) $("#mk-save", p).onclick = async () => { if (await change({ put: { ...m, note: $("#mk-note", p).value.trim() } })) closeTip(); };
    $("#mk-ask", p).onclick = async () => {
      const part = { page: m.page, box: !!m.box, rects: m.rects.map(R) };
      setMarks([part]);
      try { askBox(at, { pages: [m.page], quote: m.quote, mark: part, old: m, ...(m.box ? { image: await crop(m.page, part.rects[0]) } : {}) }); }
      catch (err) { setMarks([]); toast(`Couldn't crop that region: ${err.message}`, "err", 6000); }
    };
  }
  // A reply is pinned to the passage it was asked about: when a session's turn ends (chat.js), and, for replies that
  // came while this paper was closed, from the turns of the conversation the chat shows (loadMarks). Marks an agent
  // wrote in a turn are fetched when it ends.
  let again = 0;
  function pin(t) {
    const a = readAsk(t.asked);
    if (!a) return;
    saved.filter((m) => m.question && norm(m.question) === norm(a.question) && (m.crop ? m.crop === a.crop : !!a.quote && norm(a.quote).startsWith(norm(m.quote).slice(0, 120))))
      .forEach((m) => { m.note = (m.note ? m.note + "\n\n---\n\n" : "") + `**${m.question}**\n\n${t.said}`; m.question = ""; change({ put: m }); });
  }
  const ended = ({ detail: t }) => {
    if (!alive() || !keep) return;
    pin(t);
    clearTimeout(again);
    again = setTimeout(loadMarks, 1200);
  };
  document.addEventListener("rd:turn", ended);

  // one floating element at a time: the Ask button, then the question
  let tip = null;
  function pop(html, at, cls) {
    closeTip(true);
    tip = document.createElement("div");
    tip.className = cls;
    tip.innerHTML = html;
    document.body.appendChild(tip);
    const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, at.left)) + "px";
    tip.style.top = (at.bottom + h + 8 > window.innerHeight ? Math.max(8, at.top - h - 6) : at.bottom + 6) + "px";
    return tip;
  }
  function closeTip(keepMarks) {
    tip?.remove();
    tip = null;
    if (keepMarks !== true && marks.length) setMarks([]);
  }
  const outside = (e) => { if (tip && !tip.contains(e.target)) closeTip(); };
  const esc2 = (e) => {
    if (e.key === "Escape" && (tip || boxing)) { closeTip(); setBoxing(false); }
    if ((e.key === "Delete" || e.key === "Backspace") && tip?._mark && !/^(TEXTAREA|INPUT|SELECT)$/.test(document.activeElement?.tagName || "")) {
      e.preventDefault();                                      // with a highlight's note open: remove the highlight
      const id = tip._mark.id;
      closeTip();
      change({ delete: id });
    }
  };
  const onScroll = () => { if (tip?.className === "asktip") closeTip(); };
  document.addEventListener("mousedown", outside, true);
  document.addEventListener("keydown", esc2);
  scroll.addEventListener("scroll", onScroll);

  const watch = setInterval(() => { if (!scroll.isConnected) free(); }, 3000);   // the view was closed
  function free() {
    clearInterval(watch);
    ro.disconnect();
    document.removeEventListener("mouseup", onUp);
    document.removeEventListener("mousedown", outside, true);
    document.removeEventListener("keydown", esc2);
    clearTimeout(again);
    document.removeEventListener("rd:turn", ended);
    closeTip();
    task.destroy();
  }
  return free;
}
