// A library: a project marked `library = true` in projects.toml opens as this page instead of the project overview.
// Its collections are its top-level folders (Papers, Courses, ...; /api/library). The list on the left shows one
// collection's items (a folder with its documents, or a single file); the document opens on the right, in the file
// viewer (files.js, reader.js).
import { S, $, esc, get, icon, hooks, store, toast } from "./core.js";
import { filesState, openFile, renderViewer } from "./files.js";
import { ask } from "./dialogs.js";

const L = { project: null, cols: null, col: "", q: "", concept: "", sort: store("library.sort") || "added" };
const year = (i) => (i.date.match(/\d{4}/) || [""])[0];
const who = (i) => { const a = i.authors.split(/,| and | & /).map((x) => x.trim()).filter((x) => x && x !== "..." && x !== "…"); return !a.length ? "" : a[0].split(" ").pop() + (a.length > 1 ? " et al." : ""); };
const SORT = { added: (a, b) => b.added - a.added, date: (a, b) => b.date.localeCompare(a.date), title: (a, b) => a.title.localeCompare(b.title) };
const col = () => L.cols?.find((c) => c.name === L.col);
const base = (p) => p.split("/").pop();

export function renderLibrary(full = true) {
  const project = S.route.project;
  if (!full && $("#plist") && L.project === project) return;
  if (L.project !== project) Object.assign(L, { project, cols: null, col: store("library.col." + project) || "", q: "", concept: "" });
  $("#view").innerHTML = `<div class="page full"><div class="tabbody"><div class="files papers">
      <div class="plist" id="plist"><div class="phead">
          <div class="pline"><select id="pp-col" title="Collection: a folder of the library"></select><button class="btn sm primary" id="pp-add" title="Add to this collection">${icon("plus")} Add</button></div>
          <div class="pline"><input id="pp-q" type="search" placeholder="Search…" value="${esc(L.q)}"></div>
          <div class="pline"><select id="pp-c" title="Show one concept's items"></select><select id="pp-s" title="Order: recently added, newest first, or by title">
            <option value="added">Recent</option><option value="date">Newest</option><option value="title">Title</option></select></div></div>
        <div class="prows" id="prows"><div class="empty"><span class="spin"></span></div></div></div>
      <div class="viewer" id="viewer" data-empty="Pick a document on the left.<br><span style='font-size:12px'>In a PDF, select text to ask about it, or box an equation or a figure. What you ask stays on the page as a highlight.</span>"></div></div></div></div>`;
  $("#pp-s").value = L.sort;
  $("#pp-col").onchange = (e) => { L.col = e.target.value; L.concept = ""; store("library.col." + project, L.col); rows(); };
  $("#pp-q").oninput = (e) => { L.q = e.target.value; rows(); };
  $("#pp-c").onchange = (e) => { L.concept = e.target.value; rows(); };
  $("#pp-s").onchange = (e) => { L.sort = e.target.value; store("library.sort", L.sort); rows(); };
  $("#pp-add").onclick = async () => {                        // one per line, each in a session of its own
    const c = col();
    const what = c && await ask({ title: `Add to ${c.name}`, label: c.add ? "One per line: an ID, a link, a title, or the path of a file" : "One per line: a link, a title, the path of a file, or a description",
      ok: "Add", hint: "⌘↩ adds. Each line gets a session of its own." });
    const list = [...new Set((what || "").split("\n").map((x) => x.trim()).filter(Boolean))].map((x) => ({
      text: c.add ? `${c.add} ${x}` : `Add this to the ${c.name} folder of ${S.data.path}, following how the items there are kept: ${x}`, label: `add ${x.split("/").pop()}` }));
    if (list.length === 1) hooks.startWith(project, list[0].text, list[0].label);
    else if (list.length && (list.length <= 5 || window.confirm(`Start ${list.length} sessions, one for each line?`))) hooks.startEach(project, list);
  };
  hooks.fileOpened = rows;
  hooks.libraryChanged = load;
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
  L.cols = r.collections;
  rows();
}
document.addEventListener("rd:turn", () => { if ($("#plist") && S.route.project === L.project) load(); });   // a session may have added an item

function rows() {
  const host = $("#prows");
  if (!host || !L.cols) return;
  const open = filesState.viewer?.path || "";
  if (!col()) L.col = (L.cols.find((c) => open.startsWith(c.name + "/")) || [...L.cols].sort((a, b) => b.items.length - a.items.length)[0] || {}).name || "";
  const c = col(), items = c ? c.items : [];
  $("#pp-col").innerHTML = L.cols.map((x) => `<option value="${esc(x.name)}">${esc(x.name)} (${x.items.length})</option>`).join("");
  $("#pp-col").value = L.col;
  $("#pp-q").placeholder = `Search ${items.length} in ${L.col}…`;
  const counts = new Map(), sel = $("#pp-c");
  items.forEach((i) => i.concepts.forEach((k) => counts.set(k, (counts.get(k) || 0) + 1)));
  sel.style.display = counts.size ? "" : "none";             // a collection whose items name no concepts has no such filter
  sel.innerHTML = `<option value="">All concepts</option>` + [...counts].sort((a, b) => a[0].localeCompare(b[0])).map(([k, n]) => `<option value="${esc(k)}">${esc(k.replace(/-/g, " "))} (${n})</option>`).join("");
  sel.value = counts.has(L.concept) ? L.concept : (L.concept = "");
  const words = L.q.toLowerCase().split(/\s+/).filter(Boolean);
  const shown = items.filter((i) => (!L.concept || i.concepts.includes(L.concept))
    && words.every((w) => `${i.title} ${i.authors} ${i.concepts.join(" ")} ${i.path}`.toLowerCase().includes(w))).sort(SORT[L.sort] || SORT.added);
  const on = (i) => (i.folder ? open.startsWith(i.path + "/") : open === i.path);
  host.innerHTML = shown.length ? shown.map((i) => {
    const meta = [year(i), who(i)].filter(Boolean).join(" · ");
    return `<div class="prow ${on(i) ? "on" : ""}" tabindex="0" data-p="${esc(i.path)}" title="${esc(i.title)}">
      <div class="pt">${esc(i.title)}</div>
      ${meta || i.verdict || i.marks ? `<div class="pm">${esc(meta)}${i.verdict ? `<span class="pv v-${esc(i.verdict.replace(/\W/g, ""))}">${esc(i.verdict)}</span>` : ""}${i.marks ? `<span class="pk" title="${i.marks} highlight${i.marks > 1 ? "s" : ""}">${icon("mark")}${i.marks}</span>` : ""}</div>` : ""}
      ${i.concepts.length ? `<div class="pc">${i.concepts.map((k) => `<span>${esc(k.replace(/-/g, " "))}</span>`).join("")}</div>` : ""}
      ${on(i) && i.docs.length > 1 ? `<div class="pd">${i.docs.map((d) => `<a class="${d === open ? "on" : ""}" data-d="${esc(d)}">${icon(d.endsWith(".pdf") ? "doc" : "file")}${esc(base(d))}</a>`).join("")}</div>` : ""}</div>`;
  }).join("") : `<div class="empty">${items.length ? "Nothing matches." : "Nothing here yet. Add with the button above."}</div>`;
  host.querySelectorAll(".prow").forEach((el) => {
    const go = () => { const i = items.find((x) => x.path === el.dataset.p); i ? openFile("local", i.main) : toast("It is no longer there", "err"); };
    el.onclick = (e) => { const d = e.target.closest("[data-d]"); d ? openFile("local", d.dataset.d) : go(); };
    el.onkeydown = (e) => { if (e.key === "Enter") go(); };
  });
}
