// The paper reader: a PDF drawn by PDF.js, so its text can be selected. Ask works on a selection, or on a box drawn
// around an equation or a figure: the passage (or a crop of the box), its page and the question go to a session, the
// way Mark & ask sends a figure (annotate.js).
import { S, $, esc, get, post, toast, icon, hooks, store, allAgents, agentLabel, markSent } from "./core.js";

const V = "/vendor/pdfjs/";
let lib = null;

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
// frees the document. `gone(folder)` is called after Delete paper moved the PDF's folder to the trash.
export async function showPdf(el, { side, path, url, gone }) {
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
  let boxing = false;

  const fit = () => { pv.currentScaleValue = "auto"; };
  if ($(".vhead #vsize", el)) {
    $(".vhead #vsize", el).insertAdjacentHTML("afterend", `<span class="pdfctl">
      <button class="btn ghost sm icon" id="pz-out" title="Zoom out">−</button><button class="btn ghost sm" id="pz-val" title="Fit the width">100%</button><button class="btn ghost sm icon" id="pz-in" title="Zoom in">+</button>
      <span class="muted" id="pg-n"></span>
      <button class="btn sm" id="pbox" title="Drag a box around an equation or a figure and ask about it. For text, select it and press Ask.">${icon("mark")} Box &amp; ask</button></span>`);
    $("#pz-out", el).onclick = () => pv.decreaseScale();
    $("#pz-in", el).onclick = () => pv.increaseScale();
    $("#pz-val", el).onclick = fit;
    $("#pbox", el).onclick = () => setBoxing(!boxing);
  }
  // A paper's folder holds the PDF beside its note.md. Delete paper moves that folder to the trash (undone with
  // `trash --restore`).
  const dir = path.split("/").slice(0, -1).join("/");
  if (side === "local" && dir && $(".vhead #vvs", el)) get("/api/tree", { project: S.route.project, side, path: dir }).then((j) => {
    if (!alive() || !j.entries.some((e) => e.name === "note.md")) return;
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
  const ro = new ResizeObserver(() => { if (auto && pv.pagesCount) fit(); });
  ro.observe(scroll);

  // ----- what is being asked about, drawn over its page (pdf.js rebuilds a page's layers when it redraws) -----
  function paint(n) {
    const pg = pv.getPageView(n - 1)?.div;
    if (!pg) return;
    pg.querySelector(".rdmarks")?.remove();
    const mine = marks.filter((m) => m.page === n);
    if (!mine.length) return;
    const layer = document.createElement("div");
    layer.className = "rdmarks";
    layer.innerHTML = mine.flatMap((m) => m.rects.map((r) => `<div class="rdmark ${m.box ? "box" : ""}" style="left:${r.l * 100}%;top:${r.t * 100}%;width:${r.w * 100}%;height:${r.h * 100}%"></div>`)).join("");
    pg.appendChild(layer);
  }
  function setMarks(list) {
    const pages = new Set([...marks, ...list].map((m) => m.page));
    marks.length = 0;
    marks.push(...list);
    pages.forEach(paint);
  }
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
  const onUp = (e) => setTimeout(() => {                       // anywhere: a drag may end outside the page
    if (boxing || !alive() || tip?.contains(e.target)) return;
    const s = selection();
    if (!s) return closeTip();
    const go = pop(`<button class="btn sm primary" id="ask-go">${icon("chat")} Ask</button>`, s.at, "asktip");
    $("#ask-go", go).onclick = () => { setMarks(s.marks); document.getSelection().removeAllRanges(); askBox(s.at, { pages: s.pages, quote: s.quote }); };
  }, 0);
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
      try { askBox(m, { pages: [n], image: await crop(n, r) }); }
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
      <div class="af"><label class="muted" for="ask-to">Ask</label><select id="ask-to">${live.map((a) => `<option value="${esc(a.pane)}" ${a === pick ? "selected" : ""}>${esc(agentLabel(a))}${a.machine ? ` · ${esc(a.machine)}` : ""}</option>`).join("")}
        <option value="">New session…</option></select><span class="grow"></span><button class="btn sm primary" id="ask-send" title="Send (⏎) · new line: ⇧⏎">Send</button></div>`, at, "askpop");
    const q = $("#ask-q", p), send = $("#ask-send", p);
    $("#ask-x", p).onclick = closeTip;
    q.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send.click(); } };
    send.onclick = async () => {
      const pane = $("#ask-to", p).value;
      send.disabled = true;
      try {
        const file = side === "server" ? `${S.data.server}:${S.data.server_root.replace(/\/$/, "")}/${path}` : `${S.data.path}/${path}`;
        let text;
        if (ctx.image) {
          const up = await post("/api/paste", { pane, b64: ctx.image.split(",")[1], name: "region.png", type: "image/png" });
          text = `A region of ${file}, ${where}, cropped here: ${up.path}\n\n${q.value.trim() || "Explain what this shows."}`;
        } else text = `From ${file}, ${where}:\n\n> ${ctx.quote.length > 6000 ? ctx.quote.slice(0, 6000) + "…" : ctx.quote}\n\n${q.value.trim() || "Explain this passage."}`;
        if (!pane) hooks.newSession(S.route.project, "custom", { text });
        else {
          await post("/api/chat/send", { pane, text });
          markSent(pane);
          hooks.openChat(pane, { focus: false });
        }
        closeTip();
      } catch (e) { toast(e.message, "err", 6000); send.disabled = false; }
    };
    setTimeout(() => q.focus(), 0);
  }

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
  const esc2 = (e) => { if (e.key === "Escape" && (tip || boxing)) { closeTip(); setBoxing(false); } };
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
    closeTip();
    task.destroy();
  }
  return free;
}
