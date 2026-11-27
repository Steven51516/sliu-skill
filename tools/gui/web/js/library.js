// A library: a project marked `library = true` in projects.toml opens as this page instead of the project overview.
// Its collections are its top-level folders (Papers, Courses, ...; /api/library). The list on the left shows one
// collection's items (a folder with its documents, or a single file); the document opens on the right, in the file
// viewer (files.js, reader.js).
import { S, $, esc, get, icon, hooks, store, toast, popMenu } from "./core.js";
import { filesState, openFile, renderViewer } from "./files.js";
import { ask } from "./dialogs.js";

const L = { project: null, cols: null, col: "", q: "", concept: "", sort: store("library.sort") || "added" };
const year = (i) => (i.date.match(/\d{4}/) || [""])[0];
const who = (i) => { const a = i.authors.split(/,| and | & /).map((x) => x.trim()).filter((x) => x && x !== "..." && x !== "…"); return !a.length ? "" : a[0].split(" ").pop() + (a.length > 1 ? " et al." : ""); };
const SORTS = { added: ["Recently added", (a, b) => b.added - a.added], date: ["Newest first", (a, b) => b.date.localeCompare(a.date)], title: ["Title", (a, b) => a.title.localeCompare(b.title)] };
const col = () => L.cols?.find((c) => c.name === L.col);
const words = (k) => k.replace(/[-_]/g, " ");
// a document's name as a reader says it: "paper.pdf" is the Paper, "lectures-01-12.md" is Lectures 01 12
const DOCS = { "paper.pdf": "Paper", "note.md": "Note", "index.md": "Overview", "README.md": "Overview" };
const docName = (p) => { const f = p.split("/").pop(), w = words(f.replace(/\.[^.]+$/, "")); return DOCS[f] || w[0].toUpperCase() + w.slice(1); };
const itemOf = (path) => L.cols?.flatMap((c) => c.items).find((i) => (i.folder ? path.startsWith(i.path + "/") : path === i.path));

export function renderLibrary(full = true) {
  const project = S.route.project;
  if (!full && $("#plist") && L.project === project) return;
  if (L.project !== project) Object.assign(L, { project, cols: null, col: store("library.col." + project) || "", q: "", concept: "" });
  $("#view").innerHTML = `<div class="page full"><div class="tabbody"><div class="files papers">
      <div class="plist" id="plist"><div class="phead">
          <div class="pline"><button class="pcol" id="pp-col" title="Switch collection: a folder of the library"><span id="pp-coln"></span><span class="n" id="pp-colc"></span>${icon("chev")}</button><span class="grow"></span>
            <button class="btn ghost sm icon" id="pp-c" title="Show one concept's items">${icon("filter")}</button>
            <button class="btn ghost sm icon" id="pp-s" title="Order">${icon("sort")}</button>
            <button class="btn sm primary" id="pp-add" title="Add to this collection">${icon("plus")}Add</button></div>
          <label class="psearch">${icon("search")}<input id="pp-q" type="search" placeholder="Search" value="${esc(L.q)}"></label>
          <div class="pchips" id="pp-on"></div></div>
        <div class="prows" id="prows"><div class="empty"><span class="spin"></span></div></div></div>
      <div class="viewer" id="viewer" data-empty="<b>Pick a document</b><span>In a PDF, select text to ask about it, or box an equation or a figure. What you ask stays on the page as a highlight.</span>"></div></div></div></div>`;
  $("#pp-col").onclick = (e) => popMenu(e.currentTarget, L.cols.map((c) => ({ label: c.name, hint: String(c.items.length || ""), on: c.name === L.col,
    run: () => { L.col = c.name; L.concept = ""; store("library.col." + project, L.col); rows(); } })), { cls: "nums" });
  $("#pp-s").onclick = (e) => popMenu(e.currentTarget, Object.entries(SORTS).map(([k, [name]]) => ({ label: name, on: k === L.sort, run: () => { L.sort = k; store("library.sort", k); rows(); } })), { right: true });
  $("#pp-c").onclick = (e) => popMenu(e.currentTarget, [{ label: "All concepts", on: !L.concept, run: () => { L.concept = ""; rows(); } }, "-",
    ...concepts().map(([k, n]) => ({ label: words(k), hint: String(n), on: k === L.concept, run: () => { L.concept = k; rows(); } }))], { right: true, cls: "nums" });
  $("#pp-q").oninput = (e) => { L.q = e.target.value; rows(); };
  $("#pp-add").onclick = async () => {                        // one per line, each in a session of its own
    const c = col();
    // A collection whose PDFs a command can highlight (its `highlight` setting): Add asks whether to, and says
    // `--no-highlights` to its command when not. The paper's own Highlight button does it later.
    const marks = c && !!c.add && !!c.highlight;
    const got = c && await ask({ title: `Add to ${c.name}`, label: c.add ? "One per line: an ID, a link, a title, or the path of a file" : "One per line: a link, a title, the path of a file, or a description",
      ok: "Add", hint: `⌘↩ adds. Each line gets a session of its own.${marks ? " Unticked, a paper comes in unmarked: Highlight this paper, on the paper, marks it later." : ""}`,
      check: marks ? { label: "Highlight the PDF: its claims, methods, results and limits", on: store("library.mark") !== false } : null });
    const what = marks ? got?.text : got, bare = marks && got && !got.checked;
    if (marks && got) store("library.mark", got.checked);
    const list = [...new Set((what || "").split("\n").map((x) => x.trim()).filter(Boolean))].map((x) => ({
      text: c.add ? `${c.add} ${x}${bare ? " --no-highlights" : ""}` : `Add this to the ${c.name} folder of ${S.data.path}, following how the items there are kept: ${x}`, label: `add ${x.split("/").pop()}` }));
    if (list.length === 1) hooks.startWith(project, list[0].text, list[0].label);
    else if (list.length && (list.length <= 5 || window.confirm(`Start ${list.length} sessions, one for each line?`))) hooks.startEach(project, list);
  };
  $("#prows").onkeydown = (e) => {                             // ↑ ↓ move through the list, ↩ opens
    const all = [...$("#prows").querySelectorAll(".prow")], at = all.indexOf(document.activeElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); (all[at + (e.key === "ArrowDown" ? 1 : -1)] || all[at])?.focus(); }
  };
  hooks.fileOpened = rows;
  hooks.libraryChanged = load;
  hooks.docTitle = (side, path) => {                           // what the viewer's header calls an open document
    const i = side === "local" && S.route.project === L.project && itemOf(path);
    return i ? { title: i.title, sub: [path.split("/")[0], i.folder ? docName(path) : ""].filter(Boolean).join(" · ") } : null;
  };
  renderViewer();
  if (L.cols) rows();
  load();
}

async function load() {
  const project = L.project;
  let r;
  try { r = await get("/api/library", { project }); }
  catch (e) { if ($("#prows")) $("#prows").innerHTML = `<div class="empty err">${esc(e.message)}</div>`; return; }
  if (L.project !== project) return;
  const first = !L.cols;
  L.cols = r.collections;
  rows();
  if (first && filesState.viewer) renderViewer();              // the open document's title comes from the list
}
document.addEventListener("rd:turn", () => { if ($("#plist") && S.route.project === L.project) load(); });   // a session may have added an item

function concepts() {
  const n = new Map();
  (col()?.items || []).forEach((i) => i.concepts.forEach((k) => n.set(k, (n.get(k) || 0) + 1)));
  return [...n].sort((a, b) => a[0].localeCompare(b[0]));
}

function rows() {
  const host = $("#prows");
  if (!host || !L.cols) return;
  const open = filesState.viewer?.path || "";
  if (!col()) L.col = (L.cols.find((c) => open.startsWith(c.name + "/")) || [...L.cols].sort((a, b) => b.items.length - a.items.length)[0] || {}).name || "";
  const c = col(), items = c ? c.items : [];
  $("#pp-coln").textContent = L.col || "Library";
  $("#pp-colc").textContent = items.length || "";
  $("#pp-q").placeholder = `Search ${L.col}`;
  const has = concepts().length > 0;
  $("#pp-c").style.display = has ? "" : "none";               // a collection whose items name no concepts has no such filter
  $("#pp-c").classList.toggle("on", !!L.concept);
  if (!has) L.concept = "";
  $("#pp-on").innerHTML = L.concept ? `<span class="pchip">${esc(words(L.concept))}<button title="Show all concepts">${icon("x")}</button></span>` : "";
  if (L.concept) $("#pp-on").querySelector("button").onclick = () => { L.concept = ""; rows(); };
  const terms = L.q.toLowerCase().split(/\s+/).filter(Boolean);
  const shown = items.filter((i) => (!L.concept || i.concepts.includes(L.concept))
    && terms.every((w) => `${i.title} ${i.authors} ${i.concepts.join(" ")} ${i.path}`.toLowerCase().includes(w))).sort((SORTS[L.sort] || SORTS.added)[1]);
  const on = (i) => (i.folder ? open.startsWith(i.path + "/") : open === i.path);
  host.innerHTML = shown.length ? shown.map((i) => {
    const meta = [year(i), who(i)].filter(Boolean).join(" · "), more = i.concepts.length - 2;
    return `<div class="prow ${on(i) ? "on" : ""}" tabindex="0" data-p="${esc(i.path)}">
      <div class="pt">${esc(i.title)}</div>
      ${meta || i.marks ? `<div class="pm"><span>${esc(meta)}</span><span class="grow"></span>${i.marks ? `<span class="pk" title="${i.marks} highlight${i.marks > 1 ? "s" : ""}">${icon("mark")}${i.marks}</span>` : ""}</div>` : ""}
      ${i.concepts.length ? `<div class="pc">${i.concepts.slice(0, 2).map((k) => `<span>${esc(words(k))}</span>`).join("")}${more > 0 ? `<span title="${esc(i.concepts.slice(2).map(words).join(", "))}">+${more}</span>` : ""}</div>` : ""}
      ${on(i) && i.docs.length > 1 ? `<div class="pd">${i.docs.map((d) => `<a class="${d === open ? "on" : ""}" data-d="${esc(d)}">${icon(d.endsWith(".pdf") ? "doc" : "file")}${esc(docName(d))}</a>`).join("")}</div>` : ""}</div>`;
  }).join("") : `<div class="empty big"><b>${items.length ? "Nothing matches" : "Nothing here yet"}</b><span>${items.length ? "Try other words, or clear the filter." : "Add to this collection with the button above."}</span></div>`;
  if (open !== rows.last) { rows.last = open; host.querySelector(".prow.on")?.scrollIntoView({ block: "nearest" }); }   // the open item, in view
  host.querySelectorAll(".prow").forEach((el) => {
    const go = () => { const i = items.find((x) => x.path === el.dataset.p); i ? openFile("local", i.main) : toast("It is no longer there", "err"); };
    el.onclick = (e) => { const d = e.target.closest("[data-d]"); d ? openFile("local", d.dataset.d) : go(); };
    el.onkeydown = (e) => { if (e.key === "Enter") go(); };
  });
}
