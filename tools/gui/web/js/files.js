// Read-only file trees (records on the Mac, code on the server) and the file viewer.
import { S, $, esc, get, post, toast, icon, fmtSize, md, resolvePath, hooks } from "./core.js";

const F = { trees: {}, viewer: null, scope: "map", focus: null };
export const filesState = F;
export function resetFiles() { F.trees = {}; F.viewer = F.pending || null; F.pending = null; }
export function openPathLater(side, path) { F.pending = { side, path }; F.viewer = { side, path }; }

const serverMapDir = (m) => `${S.data.server_maps}/${m.folder}`;
export const localMapDir = (m) => m.path.replace(/\/(map|track)\.md$/, "");
export { serverMapDir };

function roots(m) {
  const d = S.data, out = [];
  if (m && F.scope === "map") {
    out.push({ key: "L", side: "local", root: localMapDir(m), label: "Records · Mac", sub: localMapDir(m) });
    if (d.server) {
      out.push({ key: "R", side: "server", root: serverMapDir(m), label: `Code · ${d.server}`, sub: serverMapDir(m) });
      d.shared.forEach((s, i) => out.push({ key: "S" + i, side: "server", root: s, label: `Shared · ${d.server}`, sub: s }));
    }
  } else {
    out.push({ key: "L", side: "local", root: "", label: "Project · Mac", sub: d.path.replace(/^\/Users\/[^/]+/, "~") });
    if (d.server) out.push({ key: "R", side: "server", root: "", label: `Project · ${d.server}`, sub: d.server_root });
  }
  return out;
}

export function renderFiles(host, m) {
  host.innerHTML = `<div class="files"><div class="trees" id="trees"></div><div class="viewer" id="viewer"></div></div>`;
  const rs = roots(m);
  $("#trees").innerHTML = (m ? `<div class="scope"><button data-scope="map" class="${F.scope === "map" ? "on" : ""}">This map</button>
      <button data-scope="project" class="${F.scope === "project" ? "on" : ""}">Whole project</button></div>` : "")
    + (S.data.server ? "" : `<div class="terr muted">No server set for this project (Settings).</div>`)
    + rs.map((r) => `<div class="tree" id="tree-${r.key}"></div>`).join("");
  $("#trees").querySelectorAll("[data-scope]").forEach((b) => b.onclick = () => { F.scope = b.dataset.scope; F.trees = {}; renderFiles(host, m); });
  rs.forEach((r) => {
    const key = `${m ? F.scope : "project"}:${r.key}`;
    if (!F.trees[key]) F.trees[key] = { ...r, nodes: { [r.root]: { open: true } } };
    const tr = F.trees[key];
    tr.key = r.key;
    drawTree(tr);
    if (tr.side === "local") Object.keys(tr.nodes).filter((p) => tr.nodes[p].open || p === tr.root).forEach((p) => loadDir(tr, p, true));
    else loadDir(tr, r.root, false);
  });
  if (F.focus && m && F.scope === "map") {
    const f = F.focus;
    F.focus = null;
    rs.filter((r) => r.key === "L" || r.key === "R").forEach((r) => expandTo(F.trees[`map:${r.key}`], `${r.root}/${f}`));
  }
  renderViewer();
}

async function loadDir(tr, path, fresh) {
  const n = tr.nodes[path] || (tr.nodes[path] = {});
  if (n.entries && !fresh) return drawTree(tr);
  n.loading = true; drawTree(tr);
  try {
    const j = await get("/api/tree", { project: S.route.project, side: tr.side, path, ...(fresh ? { fresh: 1 } : {}) });
    n.entries = j.entries.sort((a, b) => (b.dir - a.dir) || a.name.localeCompare(b.name, undefined, { numeric: true })); n.error = null;
  } catch (e) { n.error = e.message; n.entries = null; }
  n.loading = false;
  drawTree(tr);
}

async function expandTo(tr, path) {
  if (!tr) return;
  const parts = path.split("/").filter(Boolean);
  let cur = tr.root;
  for (const p of parts.slice(tr.root.split("/").filter(Boolean).length)) {
    await loadDir(tr, cur, false);
    cur = cur ? `${cur}/${p}` : p;
    (tr.nodes[cur] = tr.nodes[cur] || {}).open = true;
  }
  await loadDir(tr, cur, false);
  if (tr.side === "local" && tr.nodes[cur].entries?.some((e) => e.name === "ticket.md")) openFile("local", `${cur}/ticket.md`);
}

function drawTree(tr) {
  const el = $(`#tree-${tr.key}`);
  if (!el) return;
  const rows = [];
  const walk = (path, depth) => {
    const n = tr.nodes[path] || {};
    if (n.loading && !n.entries) rows.push(`<div class="terr muted" style="padding-left:${28 + depth * 14}px"><span class="spin"></span></div>`);
    if (n.error) rows.push(`<div class="terr" style="padding-left:${28 + depth * 14}px">${esc(n.error)}</div>`);
    (n.entries || []).forEach((e) => {
      const p = path ? `${path}/${e.name}` : e.name, sub = tr.nodes[p], on = F.viewer && F.viewer.side === tr.side && F.viewer.path === p;
      rows.push(`<div tabindex="0" class="trow ${on ? "on" : ""}" style="padding-left:${10 + depth * 14}px" data-p="${esc(p)}" data-dir="${e.dir ? 1 : ""}">
        <span class="caret">${e.dir ? (sub && sub.open ? "▾" : "▸") : ""}</span>${icon(e.dir ? "folder" : "file", "fi" + (e.dir ? " dir" : ""))}<span class="nm">${esc(e.name)}</span>
        <span class="sz">${e.dir ? "" : fmtSize(e.size)}</span><button class="btn ghost sm icon vs" title="Open in VS Code">${icon("ext")}</button></div>`);
      if (e.dir && sub && sub.open) walk(p, depth + 1);
    });
  };
  walk(tr.root, 0);
  el.innerHTML = `<h3>${esc(tr.label)}<span class="path" title="${esc(tr.sub)}">${esc(tr.sub)}</span>
    <button class="btn ghost sm icon" data-refresh="1" title="${tr.side === "server" ? "Fetch again from the server" : "Reload"}">${icon("refresh")}</button>
    ${tr.side === "server" ? `
      <button class="btn ghost sm icon" data-ssh="1" title="Open a terminal here">${icon("term")}</button>` : ""}</h3>` + rows.join("");
  el.querySelectorAll(".trow").forEach((r) => r.onclick = (e) => {
    const p = r.dataset.p, isDir = !!r.dataset.dir;
    if (e.target.closest(".vs")) return vscode(tr.side, p, isDir);
    if (isDir) {
      const n = tr.nodes[p] || (tr.nodes[p] = {});
      n.open = !n.open;
      if (n.open) loadDir(tr, p, false); else drawTree(tr);
    } else openFile(tr.side, p);
  });
  const rb = el.querySelector("[data-refresh]");
  if (rb) rb.onclick = () => Object.keys(tr.nodes).filter((p) => tr.nodes[p].open || p === tr.root).forEach((p) => loadDir(tr, p, true));
  const sb = el.querySelector("[data-ssh]");
  if (sb) sb.onclick = () => hooks.openTerminal({ kind: "ssh", project: S.route.project, path: tr.root, server: S.data.server, label: `ssh ${S.data.server}:${tr.root.split("/").pop() || "~"}` });
}

export function openFile(side, path) {
  clearInterval(F.follow);
  F.viewer = { side, path };
  Object.values(F.trees).forEach(drawTree);
  renderViewer();
}

function renderViewer() {
  const el = $("#viewer");
  if (!el) return;
  if (!F.viewer) { el.innerHTML = `<div class="empty big">Pick a file on the left.<br><span style="font-size:12px">Folders load when opened. Server files are read-only and cached until ${icon("refresh")}.</span></div>`; return; }
  showDoc(el, F.viewer.side, F.viewer.path);
}

export async function vscode(side, path, dir) {
  try { const r = await post("/api/vscode", { project: S.route.project, side, path, dir }); toast("Opened in VS Code"); return r; }
  catch (e) { toast(e.message, "err", 6000); }
}

const LANG = { py: "python", sh: "bash", bash: "bash", zsh: "bash", js: "javascript", mjs: "javascript", ts: "typescript", json: "json", jsonl: "json",
  yaml: "yaml", yml: "yaml", toml: "ini", cfg: "ini", ini: "ini", md: "markdown", c: "c", h: "c", cpp: "cpp", cu: "cpp", rs: "rust", go: "go",
  r: "r", sql: "sql", txt: "plaintext", html: "xml", xml: "xml", css: "css", slurm: "bash", sbatch: "bash", ipynb: "json" };

export async function showDoc(el, side, path, opt = {}) {
  const name = path.split("/").pop();
  const head = opt.bare ? "" : `<div class="vhead">${icon(side === "local" ? "file" : "server")}<span class="path mono" title="${esc(path)}">${esc(side === "local" ? "" : S.data.server + ":")}${esc(path)}</span>
    <span class="muted" id="vsize"></span><button class="btn ghost sm icon" id="vref" title="Reload">${icon("refresh")}</button>
    <button class="btn sm" id="vvs">${icon("ext")} VS Code</button></div>`;
  if (!opt.quiet || !el.querySelector(".vbody")) el.innerHTML = head + `<div class="vbody"><div class="spin"></div></div>`;
  const wire = () => {
    if (opt.bare) return;
    $("#vref", el).onclick = () => showDoc(el, side, path, { ...opt, fresh: true });
    $("#vvs", el).onclick = () => vscode(side, path, false);
  };
  wire();
  const req = (el._req = (el._req || 0) + 1);
  let f;
  try { f = await get("/api/file", { project: S.route.project, side, path, ...(opt.fresh ? { fresh: 1 } : {}), ...(opt.mode ? { mode: opt.mode } : {}) }); }
  catch (e) { if (!opt.quiet && el._req === req) el.querySelector(".vbody").innerHTML = `<div class="err">${esc(e.message)}</div>`; return; }
  if (el._req !== req || !el.isConnected) return;
  const body = document.createElement("div");
  body.className = opt.bare ? "" : "vbody";
  if (f.kind === "image") body.innerHTML = `<img src="data:${esc(f.mime)};base64,${f.data}" alt="${esc(name)}">`;
  else if (f.kind === "binary") body.innerHTML = `<div class="muted">Binary file, ${fmtSize(f.size)}.</div>`;
  else if (f.kind === "too-big") body.innerHTML = `<div class="muted">Image too large to show (${fmtSize(f.size)}).</div>`;
  else if (f.kind === "markdown") {
    const dir = path.split("/").slice(0, -1).join("/");
    md(body.appendChild(document.createElement("div")), f.text, { frontMatter: opt.frontMatter, skipKeys: opt.skipKeys, dropTitle: opt.dropTitle, onLink: (h) => (opt.onLink ? opt.onLink(resolvePath(dir, h.split("#")[0]), side) : openFile(side, resolvePath(dir, h.split("#")[0]))) });
  } else if (f.kind === "csv") renderCsv(body, f.text, name.endsWith(".tsv") ? "\t" : ",");
  else {
    let text = f.text;
    const lang = LANG[name.split(".").pop().toLowerCase()] || (f.kind === "log" ? "plaintext" : null);
    if (f.kind === "json" && name.endsWith(".json")) { try { text = JSON.stringify(JSON.parse(text), null, 2); } catch (_) { /* keep as is */ } }
    const pre = document.createElement("pre");
    pre.className = "code";
    let html = esc(text);
    if (lang && hljs.getLanguage(lang) && text.length < 400000) html = hljs.highlight(text, { language: lang, ignoreIllegals: true }).value;
    pre.innerHTML = `<code class="hljs">${numberLines(html)}</code>`;
    body.appendChild(pre);
  }
  if (f.truncated) {
    const note = document.createElement("div");
    note.className = "note";
    note.innerHTML = f.tail ? `Showing the last lines. <a>Load the whole file</a>` : `Large file: showing its beginning and end.`;
    if (f.tail) note.querySelector("a").onclick = () => showDoc(el, side, path, { ...opt, mode: "full" });
    body.prepend(note);
  }
  el.innerHTML = head;
  wire();
  if (!opt.bare) $("#vsize", el).textContent = fmtSize(f.size);
  if (!opt.bare && f.kind === "log") {                 // follow: refetch every 5 s while this file stays open
    const b = document.createElement("button");
    b.className = "btn sm" + (opt.follow ? " primary" : "");
    b.innerHTML = `${icon("play")} Follow`;
    b.title = "Reload every 5 seconds";
    b.onclick = () => {
      clearInterval(F.follow);
      if (opt.follow) return showDoc(el, side, path, { ...opt, follow: false });
      showDoc(el, side, path, { ...opt, follow: true, fresh: true });
    };
    $(".vhead", el).insertBefore(b, $("#vref", el));
    clearInterval(F.follow);
    if (opt.follow) F.follow = setInterval(() => { if (!el.isConnected) return clearInterval(F.follow); showDoc(el, side, path, { ...opt, fresh: true, quiet: true }); }, 5000);
  }
  el.appendChild(body);
  if (f.tail && !opt.bare) el.scrollTop = el.scrollHeight;
}

function numberLines(html) {
  // split highlighted HTML into lines while keeping open spans balanced per line
  const out = [], open = [];
  html.split("\n").forEach((line, i) => {
    const prefix = open.join("");
    const re = /<span[^>]*>|<\/span>/g;
    let m;
    while ((m = re.exec(line))) { if (m[0] === "</span>") open.pop(); else open.push(m[0]); }
    out.push(`<span class="ln">${i + 1}</span>${prefix}${line}${"</span>".repeat(open.length)}`);
  });
  return out.join("\n");
}

function parseCsv(text, sep) {
  const rows = [];
  let row = [], cell = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else q = false; } else cell += c; }
    else if (c === '"') q = true;
    else if (c === sep) { row.push(cell); cell = ""; }
    else if (c === "\n") { row.push(cell); rows.push(row); row = []; cell = ""; if (rows.length > 5000) break; }
    else if (c !== "\r") cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows;
}

function renderCsv(el, text, sep) {
  const rows = parseCsv(text, sep);
  if (!rows.length) { el.innerHTML = `<div class="muted">Empty.</div>`; return; }
  const head = rows[0];
  let body = rows.slice(1), sortCol = -1, asc = true;
  const draw = () => {
    el.innerHTML = `<div class="muted" style="font-size:12px;margin-bottom:6px">${body.length.toLocaleString()} rows${body.length > 2000 ? ", first 2,000 shown" : ""} · click a header to sort</div>
      <table class="csv"><tr>${head.map((h, i) => `<th data-i="${i}">${esc(h)}${i === sortCol ? (asc ? " ▲" : " ▼") : ""}</th>`).join("")}</tr>
      ${body.slice(0, 2000).map((r) => `<tr>${r.map((c) => `<td class="mono">${esc(c)}</td>`).join("")}</tr>`).join("")}</table>`;
    el.querySelectorAll("th").forEach((th) => th.onclick = () => {
      const i = +th.dataset.i;
      asc = sortCol === i ? !asc : true; sortCol = i;
      body = [...body].sort((a, b) => {
        const x = a[i] ?? "", y = b[i] ?? "", nx = parseFloat(x), ny = parseFloat(y);
        const c = !isNaN(nx) && !isNaN(ny) ? nx - ny : x.localeCompare(y);
        return asc ? c : -c;
      });
      draw();
    });
  };
  draw();
}
