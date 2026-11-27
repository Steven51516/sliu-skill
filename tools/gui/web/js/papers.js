// The paper library: a project marked `library = true` in projects.toml opens as this page instead of the project
// overview. Its papers are on the left (a folder each: paper.pdf, note.md; /api/papers), the paper or its note on the
// right, in the file viewer (files.js, reader.js).
import { S, $, esc, get, icon, hooks, store, toast } from "./core.js";
import { filesState, openFile, renderViewer } from "./files.js";
import { ask } from "./dialogs.js";

const P = { project: null, list: null, q: "", concept: "", sort: store("papers.sort") || "added" };
const year = (p) => (p.date.match(/\d{4}/) || [""])[0];
const who = (p) => { const a = p.authors.split(/,| and /).map((x) => x.trim()).filter((x) => x && x !== "..." && x !== "…"); return !a.length ? "" : a[0].split(" ").pop() + (a.length > 1 ? " et al." : ""); };
const SORT = { added: (a, b) => b.added - a.added, date: (a, b) => b.date.localeCompare(a.date), title: (a, b) => a.title.localeCompare(b.title) };

export function renderPapers(full = true) {
  const project = S.route.project;
  if (!full && $("#plist") && P.project === project) return;
  if (P.project !== project) Object.assign(P, { project, list: null, q: "", concept: "" });
  $("#view").innerHTML = `<div class="page full"><div class="tabbody"><div class="files papers">
      <div class="plist" id="plist"><div class="phead">
          <div class="pline"><input id="pp-q" type="search" placeholder="Search ${P.list ? P.list.length + " " : ""}papers…" value="${esc(P.q)}"><button class="btn sm primary" id="pp-add" title="Read a new paper into the library">${icon("plus")} Add</button></div>
          <div class="pline"><select id="pp-c" title="Show one concept's papers"></select><select id="pp-s" title="Order: recently added, newest paper first, or by title">
            <option value="added">Recent</option><option value="date">Newest</option><option value="title">Title</option></select></div></div>
        <div class="prows" id="prows"><div class="empty"><span class="spin"></span></div></div></div>
      <div class="viewer" id="viewer" data-empty="Pick a paper on the left.<br><span style='font-size:12px'>Select text in it to ask about it, or box an equation or a figure. What you ask stays on the page as a highlight.</span>"></div></div></div></div>`;
  $("#pp-s").value = P.sort;
  $("#pp-q").oninput = (e) => { P.q = e.target.value; rows(); };
  $("#pp-c").onchange = (e) => { P.concept = e.target.value; rows(); };
  $("#pp-s").onchange = (e) => { P.sort = e.target.value; store("papers.sort", P.sort); rows(); };
  $("#pp-add").onclick = async () => {
    const what = await ask({ title: "Add a paper", label: "An arXiv ID, a DOI, a link, a title, or the path of a PDF", multiline: false, ok: "Read it" });
    if (what) hooks.startWith(project, `${S.data.add || "Read this paper into the library:"} ${what.trim()}`, `add ${what.trim().split("/").pop()}`);   // each paper in a session of its own   // `add` in the project's config: the command of a paper-reading skill
  };
  hooks.fileOpened = rows;
  hooks.papersChanged = load;
  renderViewer();
  if (P.list) rows();
  load();
}

async function load() {
  const project = P.project;
  let r;
  try { r = await get("/api/papers", { project }); }
  catch (e) { if ($("#prows")) $("#prows").innerHTML = `<div class="empty err">${esc(e.message)}</div>`; return; }
  if (P.project !== project) return;
  P.list = r.papers;
  if ($("#pp-q")) $("#pp-q").placeholder = `Search ${P.list.length} papers…`;
  rows();
}
document.addEventListener("rd:turn", () => { if ($("#plist") && S.route.project === P.project) load(); });   // a session may have added a paper

function rows() {
  const host = $("#prows"), sel = $("#pp-c");
  if (!host || !P.list) return;
  const counts = new Map();
  P.list.forEach((p) => p.concepts.forEach((c) => counts.set(c, (counts.get(c) || 0) + 1)));
  sel.innerHTML = `<option value="">All concepts</option>` + [...counts].sort((a, b) => a[0].localeCompare(b[0])).map(([c, n]) => `<option value="${esc(c)}">${esc(c.replace(/-/g, " "))} (${n})</option>`).join("");
  sel.value = counts.has(P.concept) ? P.concept : (P.concept = "");
  const words = P.q.toLowerCase().split(/\s+/).filter(Boolean);
  const shown = P.list.filter((p) => (!P.concept || p.concepts.includes(P.concept))
    && words.every((w) => `${p.title} ${p.authors} ${p.concepts.join(" ")} ${p.folder}`.toLowerCase().includes(w))).sort(SORT[P.sort] || SORT.added);
  const open = filesState.viewer?.path || "";
  host.innerHTML = shown.length ? shown.map((p) => `<div class="prow ${open.startsWith(p.folder + "/") ? "on" : ""}" tabindex="0" data-f="${esc(p.folder)}" title="${esc(p.title)}">
      <div class="pt">${esc(p.title)}</div>
      <div class="pm">${esc([year(p), who(p)].filter(Boolean).join(" · "))}${p.verdict ? `<span class="pv v-${esc(p.verdict.replace(/\W/g, ""))}">${esc(p.verdict)}</span>` : ""}${p.marks ? `<span class="pk" title="${p.marks} highlight${p.marks > 1 ? "s" : ""}">${icon("mark")}${p.marks}</span>` : ""}</div>
      ${p.concepts.length ? `<div class="pc">${p.concepts.map((c) => `<span>${esc(c.replace(/-/g, " "))}</span>`).join("")}</div>` : ""}</div>`).join("")
    : `<div class="empty">${P.list.length ? "No paper matches." : "No papers yet. Add one with the button above."}</div>`;
  host.querySelectorAll(".prow").forEach((el) => {
    const go = () => { const p = P.list.find((x) => x.folder === el.dataset.f); if (p.pdf || p.note) openFile("local", p.pdf || p.note); else toast("This folder has no PDF and no note", "err"); };
    el.onclick = go;
    el.onkeydown = (e) => { if (e.key === "Enter") go(); };
  });
}
