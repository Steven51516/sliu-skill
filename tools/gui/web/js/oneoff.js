// One-off sessions end themselves. In a library (library.js), Add and a question asked from the reader each start a
// Claude session that is rarely used again; left alone they pile up, each one a live process. After every poll:
// - an Add session (its tab is labelled "add ...") that has finished ends once an item its tools wrote into is in the
//   library; one that finished without adding anything stays open and says so once;
// - a session that holds nothing but questions asked from the reader ends when it has sat idle for the library's
//   `close_after` minutes (projects.toml: 30, 0 for never), you are not looking at it, and its document is not the
//   one open. Its replies are pinned to their highlights first;
// - a session you typed into, asked to teach, or chose to keep is a conversation: never ended here.
// Ending is /api/session-leave: the session exits by itself, or stays when a background task of its own keeps it.
import { S, get, post, toast, hooks, store } from "./core.js";
import { filesState, libraryItem } from "./files.js";
import { readAsk, pinTurns } from "./reader.js";
import { turnsOf } from "./chat.js";

const ADD_REST = 1;                        // minutes an Add session rests after its last turn before it is judged
const kept = store("oneoff.kept") || {};   // session id -> { why, at }: never ended here
const judged = new Map();                  // session id -> the turn it was judged at: one look per turn
let busy = false, last = 0, off = 0;

const limitOf = (p) => p.close_after ?? 30;
const isAdd = (a) => /^add \S/.test(a.tab_label || "");
const ours = (a, p) => !!a && !!p?.library && !p.remote && a.agent === "claude" && !a.machine && !a.role && !!a.session_id;
// nothing but questions from the reader: every message of yours is one, and no command but an exit
export const askOnly = (items) => {
  const mine = items.filter((i) => i.k === "user");
  return mine.length > 0 && mine.every((i) => readAsk(i.text || "")) && !items.some((i) => i.k === "cmd" && !/^\/exit\b/.test((i.text || "").trim()));
};
function keep(a, why, say) {
  kept[a.session_id] = { why, at: Date.now() };
  const ids = Object.keys(kept);
  if (ids.length > 300) ids.sort((x, y) => kept[x].at - kept[y].at).slice(0, ids.length - 300).forEach((k) => delete kept[k]);
  store("oneoff.kept", kept);
  if (say) toast(say, "err", 9000);
}
function openLabel(project) {              // the session of the document that is open: it may be asked again any moment
  const v = filesState.viewer, it = v && S.route.project === project && libraryItem(v.side, v.path);
  return it ? (it.folder ? it.name : it.col).slice(0, 28) : "";
}

async function leave(a, said) {
  let r;
  try { r = await post("/api/session-leave", { pane: a.pane }); }
  catch (e) {
    if (/unknown endpoint/.test(e.message)) off = Date.now() + 10 * 60000;   // a backend from before this: nothing ends until it restarts
    judged.delete(a.session_id);
    return false;
  }
  if (r.left) { toast(said, "", 6000); hooks.refresh(); return true; }
  if (r.why === "background") keep(a, "background");
  else if (!r.dry_run) judged.delete(a.session_id);            // busy: looked at again on a later poll
  return false;
}

// An Add session's item: one in the library, changed since the session's first line in view, that its tools wrote to
// or its replies name. A long session's conversation comes cut to its end (chat.cut): with no item in sight there, it
// is left open without a word, since the part that would show one is out of view.
async function added(p, a) {
  const [chat, lib] = await Promise.all([get("/api/chat", { pane: a.pane }), get("/api/library", { project: p.name })]);
  if (chat.items.filter((i) => i.k === "turn").length > 1) return keep(a, "conversation");     // you went on talking to it
  const did = chat.items.filter((i) => i.k === "tool").map((i) => `${i.summary}\n${i.input}`).join("\n");
  const said = chat.items.filter((i) => i.k === "assistant").map((i) => i.text || "").join("\n");
  const from = Date.parse(chat.items.find((i) => i.ts)?.ts || a.turn_end) / 1000 - 5;
  const item = lib.collections.flatMap((c) => c.items).filter((i) => i.added >= from && (did.includes(`${p.path}/${i.path}`) || said.includes(`${i.path}/`) || said.includes(`${p.path}/${i.path}`)))
    .sort((x, y) => (y.folder - x.folder) || (y.added - x.added))[0];      // a folder before a single file, the newest first
  if (!item) return keep(a, chat.cut ? "unsure" : "nothing added", chat.cut ? "" : `“${a.tab_label}” ended without adding anything. Its session is still open: read what it says.`);
  if (await leave(a, `Added “${item.title}”. Its session has ended.`)) hooks.libraryChanged?.();
}

async function asked(p, a) {
  const chat = await get("/api/chat", { pane: a.pane });
  if (chat.cut || !askOnly(chat.items)) return keep(a, "conversation");
  await pinTurns(p.name, p.path, turnsOf(chat.items, a.pane));
  await leave(a, `The idle session of “${a.tab_label}” has ended. Its answers are on the highlights.`);
}

export async function sweep(now = false) {
  if (busy || Date.now() < off || (!now && Date.now() - last < 20000)) return;
  last = Date.now();
  busy = true;
  try {
    for (const p of (S.summary?.projects || []).filter((p) => p.library && limitOf(p))) {
      for (const a of p.agents || []) {
        const id = a.session_id;
        if (!ours(a, p) || kept[id] || !a.turn_end || !["done", "idle"].includes(a.status) || judged.get(id) === a.turn_end) continue;
        if (a.pane === hooks.chatPane?.()) continue;                        // you are looking at it
        const add = isAdd(a), idle = (Date.now() - Date.parse(a.turn_end)) / 60000;
        if (idle < (add ? ADD_REST : limitOf(p)) || (!add && a.tab_label === openLabel(p.name))) continue;
        judged.set(id, a.turn_end);
        try { await (add ? added(p, a) : asked(p, a)); } catch { judged.delete(id); }   // the backend did not answer: next time
        if (Date.now() < off) return;
      }
    }
  } finally { busy = false; }
}

// What the chat says under the conversation of the session it shows: null for an ordinary one, else when it ends
// itself, or that you kept it. `items` is its conversation as the chat holds it.
hooks.oneOff = (a, items) => {
  const p = S.summary?.projects.find((x) => x.name === a?.project);
  if (!ours(a, p) || !limitOf(p)) return null;
  const k = kept[a.session_id];
  if (k) return k.why === "you" ? { kept: true } : null;
  if (isAdd(a)) return { text: "This session ends itself when its item is in the list. What it wrote is kept." };
  return askOnly(items) ? { text: `This session ends itself after ${limitOf(p)} min idle, once you are off its document. Its answers stay on the highlights.` } : null;
};
hooks.keepSession = (a, on) => {
  if (!a?.session_id) return;
  if (on) return keep(a, "you");
  delete kept[a.session_id];
  judged.delete(a.session_id);
  store("oneoff.kept", kept);
};
