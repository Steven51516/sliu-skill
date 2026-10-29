#!/usr/bin/env python3
"""research-gui: the backend of Research Desk, a local app over the research harness, with herdr as the runtime.

Reads each project's maps and tickets (through status.py, so it agrees with `research-status`), shows the herdr agents
working in it and lets you chat with them (their Claude Code transcripts), browses records on the Mac and code on the
server (read-only), opens terminals (attached to an agent, a shell, or ssh), reads GPUs, and starts sessions and teams.
Projects are listed in ~/.config/research-gui/projects.toml (see projects.example.toml).

Usage:
    research-gui                 open the Research Desk app if installed, else the page in a browser
    research-gui --browser       the page in a browser
    research-gui --serve         only run the backend (the app starts it this way)
      --port N  --dry-run (Start buttons only report their herdr commands)  --config PATH
Listens on 127.0.0.1 only. Pure standard library.
"""
import argparse
import base64
import datetime as dt
import glob
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import tomllib
import urllib.parse
import urllib.request
import uuid
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import status as tracker  # noqa: E402  (tools/status.py, the `research-status` parser)
import rg_chat  # noqa: E402
import rg_term  # noqa: E402

warnings.filterwarnings("ignore", message=".*fork.*", category=DeprecationWarning)   # pty.fork, child execs at once
VERSION = "2"
CONFIG = os.path.expanduser(os.environ.get("RG_CONFIG", "~/.config/research-gui/projects.toml"))
STATE = os.path.join(os.path.dirname(CONFIG), "seen.json")
APP_NAME = "Research Desk"
CAP = 2 << 20                 # files larger than this show their first and last HEAD_TAIL bytes
HEAD_TAIL = 200 << 10
IMAGE_CAP = 8 << 20
LOG_LINES = 600
TAIL_BYTES = 1 << 20          # a log tail never reads more than this (progress bars write few newlines)
CACHE_MAX = 200
HIDE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".ipynb_checkpoints", ".mypy_cache", ".pytest_cache"}
HIDE_EXT = (".pt", ".pth", ".ckpt", ".safetensors", ".bin", ".pyc")
HIDE_FILES = {".DS_Store"}
IMAGE_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
             ".webp": "image/webp", ".svg": "image/svg+xml"}
LOG_EXT = (".log", ".out", ".err")
LIVE_MAP = {"open", "claimed"}          # maps that get a driver on Start team
KEYS = {str(i) for i in range(1, 10)} | {"up", "down", "left", "right", "enter", "esc", "tab", "shift+tab", "space",
                                         "backspace", "y", "n"}
ARGS = None
TOKEN = uuid.uuid4().hex     # per launch; the page reads it from /api/token (other origins can't read responses)


# ---------- config ----------

def load_config():
    if not os.path.exists(CONFIG):
        return {"projects": {}}
    with open(CONFIG, "rb") as f:
        cfg = tomllib.load(f)
    cfg.setdefault("projects", {})
    for name, p in cfg["projects"].items():
        p["name"] = name
        p["path"] = os.path.expanduser(p["path"])
        p.setdefault("shared", [])
        p.setdefault("server_maps", "maps")
    return cfg


def project(name):
    p = load_config()["projects"].get(name)
    if not p:
        raise ApiError(404, f"no project `{name}` in {CONFIG}")
    return p


class ApiError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def run(cmd, timeout=30, input=None):
    """Run argv, return (code, stdout bytes, stderr text)."""
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, input=input)
    except subprocess.TimeoutExpired:
        return 124, b"", f"timed out after {timeout}s"
    except FileNotFoundError as e:
        return 127, b"", str(e)
    return r.returncode, r.stdout, r.stderr.decode(errors="replace")


# ---------- herdr ----------

_snap = {"t": 0, "data": None, "err": None}
_snap_lock = threading.Lock()


def herdr_snapshot(max_age=1.5):
    """The live herdr session, cached briefly."""
    with _snap_lock:
        if time.time() - _snap["t"] > max_age:
            code, out, err = run(["herdr", "api", "snapshot"], timeout=10)
            try:
                _snap["data"] = json.loads(out)["result"]["snapshot"] if code == 0 else None
                _snap["err"] = None if code == 0 else (err.strip() or "herdr not running")
            except (ValueError, KeyError):
                _snap["data"], _snap["err"] = None, "unreadable herdr snapshot"
            _snap["t"] = time.time()
        return _snap["data"], _snap["err"]


class HerdrError(RuntimeError):
    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code


def herdr(*args, timeout=150):
    code, out, err = run(["herdr", *args], timeout=timeout)
    if code != 0:
        ecode = None
        try:
            e = json.loads(err or out)["error"]
            ecode, msg = e.get("code"), e.get("message")
        except (ValueError, KeyError, TypeError):
            msg = err.strip() or out.decode(errors="replace").strip()
        raise HerdrError(f"herdr {' '.join(args[:2])}: {msg}", ecode)
    try:
        return json.loads(out).get("result", {})
    except ValueError:
        return {}


_names = {"t": 0, "map": {}}


def agent_names():
    """pane -> herdr agent name (the snapshot has no names), cached briefly."""
    with _snap_lock:
        if time.time() - _names["t"] > 1.5:
            code, out, _ = run(["herdr", "agent", "list"], timeout=10)
            try:
                _names["map"] = {a["pane_id"]: a.get("name") for a in json.loads(out)["result"]["agents"]} if code == 0 else {}
            except (ValueError, KeyError):
                _names["map"] = {}
            _names["t"] = time.time()
        return _names["map"]


def live_agent(pane):
    snap, err = herdr_snapshot()
    if not snap:
        raise ApiError(503, f"herdr: {err}")
    a = next((a for a in snap.get("agents", []) if a["pane_id"] == pane), None)
    if not a:
        raise ApiError(404, f"no live agent in pane {pane}")
    return a, snap


def roster(p):
    """scratch/agents/roster.md: the latest line per herdr pane (pane and session columns found by shape, either order)."""
    path = os.path.join(p["path"], "scratch", "agents", "roster.md")
    rows = {}
    if os.path.exists(path):
        for line in open(path):
            cells = [c.strip() for c in line.split("|")]
            if len(cells) < 6 or cells[0] not in ("desk", "driver", "implementer", "worker"):
                continue
            pane = next((c for c in cells[2:4] if re.fullmatch(r"w\d+:p\d+", c)), None)
            if pane:
                session = cells[3] if cells[2] == pane else cells[2]
                rows[pane] = {"role": cells[0], "agent": cells[1], "pane": pane, "session": session,
                              "time": cells[4], "map": cells[5]}
    return rows


def in_folder(cwd, root):
    cwd, root = os.path.realpath(cwd or ""), os.path.realpath(root)
    return cwd == root or cwd.startswith(root + os.sep)


def agent_view(a, snap, ros):
    tabs = {t["tab_id"]: t for t in snap.get("tabs", [])}
    spaces = {w["workspace_id"]: w for w in snap.get("workspaces", [])}
    tab = tabs.get(a.get("tab_id"), {})
    r = ros.get(a["pane_id"], {})
    label = tab.get("label", "")
    role = r.get("role") or next((w for w in ("desk", "driver", "worker", "implementer") if w in label.lower()), "")
    return {"pane": a["pane_id"], "tab": a.get("tab_id"), "workspace": a.get("workspace_id"), "name": agent_names().get(a["pane_id"]),
            "workspace_label": spaces.get(a.get("workspace_id"), {}).get("label", ""),
            "agent": a.get("agent"), "status": a.get("agent_status"), "title": a.get("terminal_title_stripped"),
            "tab_label": label, "role": role, "map": r.get("map", ""), "session": r.get("session", ""),
            "cwd": a.get("cwd"), "transcript": bool((a.get("agent_session") or {}).get("value")), "safeguard": guard_of(a)}


def guard_of(a):
    """The agent's latest Opus-safeguard event, if any (Claude sessions only)."""
    if a.get("agent") != "claude":
        return None
    path = rg_chat.transcript_path((a.get("agent_session") or {}).get("value"))
    return rg_chat.last_safeguard(path) if path else None


def project_agents(p):
    """herdr agents whose folder is the project, each with its role (roster line, else tab label)."""
    snap, err = herdr_snapshot()
    if not snap:
        return [], err
    ros = roster(p)
    out = [agent_view(a, snap, ros) for a in snap.get("agents", []) if in_folder(a.get("cwd"), p["path"])]
    order = {"desk": 0, "driver": 1, "worker": 2, "implementer": 2}
    out.sort(key=lambda a: (order.get(a["role"], 3), a["tab_label"]))
    return out, None


def live_driver_maps(agents, maps):
    """Map folder -> the pane of its live driver (roster map field, or a tab label naming the map id)."""
    found = {}
    for a in agents:
        if a["role"] != "driver":
            continue
        for m in maps:
            folder = os.path.basename(os.path.dirname(m["_path"]))
            mid = (m.get("id") or "").lower()
            if re.search(rf"(^|/){re.escape(folder)}(/|$|\s)", a["map"]) or re.search(rf"\b{re.escape(mid)}\b(?!-)", a["tab_label"].lower()):
                found.setdefault(folder, a["pane"])
    return found


_codex = {"t": 0, "runs": []}


def etime_seconds(s):
    """ps etime ([[dd-]hh:]mm:ss) -> seconds."""
    days, _, rest = s.strip().rpartition("-")
    parts = [int(x) for x in rest.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return (int(days) if days else 0) * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]


def codex_runs():
    """Running `codex exec` jobs (codex-run detaches them, so no pane shows them): folder, run dir, age; cached 3 s."""
    if time.time() - _codex["t"] > 3:
        code, out, _ = run(["ps", "-axo", "pid=,etime=,args="], timeout=10)
        runs = []
        for line in out.decode(errors="replace").splitlines() if code == 0 else []:
            m = re.match(r"\s*(\d+)\s+(\S+)\s+(.*)$", line)
            if not m or not re.search(r"(^|/)codex exec\b", m.group(3)):
                continue
            args = m.group(3)
            cwd = re.search(r"(?:^|\s)-C\s+(\S+)", args)
            outp = re.search(r"(?:^|\s)-o\s+(\S+)", args)
            run_dir = os.path.dirname(outp.group(1)) if outp else ""
            runs.append({"pid": int(m.group(1)), "seconds": etime_seconds(m.group(2)), "cwd": cwd.group(1) if cwd else "",
                         "run": run_dir, "name": os.path.basename(run_dir) if run_dir else "codex exec"})
        _codex.update(t=time.time(), runs=runs)
    return _codex["runs"]


def mark_codex(p, agents, maps):
    """Codex runs in this project, each tied to its ticket (an id in the run's name) and to that ticket's worker; an
    agent whose Codex run is still going is working, whatever its own screen says."""
    ids = {str(k.get("id")).lower(): k.get("id") for m in maps for k in m["_tickets"] if k.get("id")}
    runs = []
    for r in codex_runs():
        if not r["cwd"] or not in_folder(r["cwd"], p["path"]):
            continue
        r = dict(r, ticket=None, pane=None)
        for low, tid in ids.items():
            if re.search(rf"(^|[^a-z0-9]){re.escape(low)}([^0-9]|$)", r["name"].lower()):
                r["ticket"] = tid
                break
        owner = next((a for a in agents if r["ticket"] and a.get("ticket") == r["ticket"]), None)
        if owner:
            r["pane"] = owner["pane"]
            owner.setdefault("codex", []).append(r)
            if owner["status"] in ("idle", "done", "unknown"):
                owner["status_raw"], owner["status"] = owner["status"], "working"
        runs.append(r)
    return runs


def mark_workers(agents, maps, drivers):
    """A worker is the session a driver opened for one ticket: its tab label or herdr name is the ticket id
    (TEAM-PROTOCOL, Workers). It is filed under the driver of that ticket's map."""
    tickets = {}
    for m in maps:
        folder = os.path.basename(os.path.dirname(m["_path"]))
        for k in m["_tickets"]:
            if k.get("id"):
                tickets[str(k["id"]).lower()] = (k, folder)
    for a in agents:
        if a["role"] in ("desk", "driver"):
            continue
        for key in (a.get("name"), a["tab_label"]):
            hit = tickets.get((key or "").strip().lower())
            if hit:
                k, folder = hit
                a.update(role="worker", ticket=k.get("id"), ticket_title=k.get("title"), map_folder=folder,
                         ticket_folder=os.path.basename(os.path.dirname(k["_path"])), driver=drivers.get(folder))
                break


# ---------- tracker ----------

def fog(body):
    """Bold titles of the `## Not yet specified` items."""
    clean = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    items = []
    for line in tracker.section(clean, "Not yet specified"):
        m = re.match(r"- \*\*(.+?)\*\*", line)
        if m:
            items.append(m.group(1).rstrip(":").strip())
        elif line.startswith("- ") and line.strip() != "-":
            items.append(line[2:].strip()[:80])
    return items


def ticket_view(k, by_id):
    blockers = k.get("blocked_by") or []
    blockers = [blockers] if isinstance(blockers, str) else blockers
    jobs = k.get("jobs") or []
    return {"id": k.get("id"), "title": k.get("title"), "type": tracker.type_of(k), "status": tracker.status_of(k),
            "status_text": k.get("status"), "blocked_by": blockers, "superseded_by": k.get("superseded_by"),
            "path": k["_path"], "folder": os.path.basename(os.path.dirname(k["_path"])),
            "answered": k["_answered"], "unblocked": all(tracker.blocker_met(b, by_id) for b in blockers),
            "holder": tracker.holder(k), "jobs": jobs if isinstance(jobs, list) else [jobs],
            "cost_cap": k.get("cost_cap"), "verdict": k.get("verdict"), "updated": k.get("updated")}


def project_state(p, with_agents=True):
    maps = tracker.load(p["path"]) if os.path.isdir(p["path"]) else []
    problems, frontier = tracker.analyse(maps) if maps else ([], {})
    by_id = {k.get("id"): k for m in maps for k in m["_archived"]}
    by_id.update({k.get("id"): k for m in maps for k in m["_tickets"]})
    agents, herdr_err = project_agents(p) if with_agents else ([], None)
    driven = live_driver_maps(agents, maps)
    mark_workers(agents, maps, driven)
    codex = mark_codex(p, agents, maps)
    out_maps, waiting = [], []
    for m in maps:
        folder = os.path.basename(os.path.dirname(m["_path"]))
        _, body = tracker.parse_front_matter(os.path.join(p["path"], m["_path"]))
        tickets = [ticket_view(k, by_id) for k in m["_tickets"]]
        fr = {k.get("id") for k in frontier.get(m.get("id")) or []}
        for t in tickets:
            t["frontier"] = t["id"] in fr
            t["waiting"] = t["type"] in tracker.HITL and t["status"] not in tracker.CLOSED
            if t["waiting"]:
                waiting.append({"kind": "ticket", "map": m.get("id"), "map_folder": folder, "id": t["id"],
                                "text": t["title"], "path": t["path"], "folder": t["folder"]})
        waiting += [{"kind": "needs", "map": m.get("id"), "map_folder": folder, "text": n} for n in m["_needs"]]
        counts = {}
        for t in tickets:
            counts[t["status"]] = counts.get(t["status"], 0) + 1
        out_maps.append({"id": m.get("id"), "title": m.get("title"), "status": tracker.status_of(m),
                         "status_text": m.get("status"), "outcome": m.get("outcome"), "updated": m.get("updated"),
                         "destination": m["_destination"], "path": m["_path"], "folder": folder,
                         "legacy": m["_legacy"], "tickets": tickets, "fog": fog(body), "counts": counts,
                         "driven": folder in driven, "holder": tracker.holder(m)})
    waiting += [{"kind": "agent", "pane": a["pane"], "role": a["role"], "label": a["tab_label"],
                 "text": f"{a['role'] or a['agent']} ({a['tab_label'] or a['pane']}) is waiting at a prompt"}
                for a in agents if a["status"] == "blocked"]
    return {"name": p["name"], "path": p["path"], "server": p.get("server"), "server_root": p.get("server_root"),
            "server_maps": p["server_maps"], "shared": p["shared"], "maps": out_maps, "waiting": waiting,
            "problems": problems, "agents": agents, "herdr_error": herdr_err, "changes": changes_since(p, out_maps), "codex": codex,
            "keychain": keychain_has(), "dry_run": ARGS.dry_run}


def projects_summary():
    cfg = load_config()
    out = []
    for name, p in cfg["projects"].items():
        try:
            s = project_state(p)
            states = {f"map:{m['id']}": [m["status"], m["title"], m["folder"], None] for m in s["maps"]}
            states.update({t["id"]: [t["status"], t["title"], m["folder"], t["folder"]] for m in s["maps"] for t in m["tickets"]})
            out.append({"name": name, "ok": True, "waiting": s["waiting"], "agents": s["agents"], "states": states,
                        "open_maps": sum(m["status"] != "closed" for m in s["maps"]),
                        "running": sum(t["status"] in ("running", "claimed") for m in s["maps"] for t in m["tickets"]),
                        "changes": len(s["changes"]["items"]), "server": p.get("server")})
        except Exception as e:  # one broken project must not hide the others
            out.append({"name": name, "ok": False, "error": str(e), "waiting": [], "agents": []})
    registered = {os.path.realpath(p["path"]) for p in cfg["projects"].values()}
    found = []
    for root in cfg.get("roots", []):
        for d in sorted(glob.glob(os.path.join(os.path.expanduser(root), "*"))):
            if os.path.realpath(d) in registered or not os.path.isdir(d):
                continue
            if glob.glob(os.path.join(d, "maps", "*", "map.md")) or glob.glob(os.path.join(d, "tracks", "*", "track.md")):
                found.append({"name": os.path.basename(d), "path": d})
    snap, err = herdr_snapshot()
    others = []
    if snap:
        for a in snap.get("agents", []):
            if not any(in_folder(a.get("cwd"), p["path"]) for p in cfg["projects"].values()):
                others.append(agent_view(a, snap, {}))
    return {"projects": out, "unregistered": found, "config": CONFIG, "other_agents": others, "herdr_error": err,
            "dry_run": ARGS.dry_run, "version": VERSION}


def add_project(b):
    name, path = b.get("name"), b.get("path")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name or ""):
        raise ApiError(400, "bad project name")
    if name in load_config()["projects"]:
        raise ApiError(400, f"`{name}` is already registered")
    if not os.path.isdir(os.path.expanduser(path or "")):
        raise ApiError(400, f"no folder {path}")
    q = lambda v: json.dumps(str(v), ensure_ascii=False)
    lines = [f"\n[projects.{name}]", f"path = {q(path)}"]
    for key in ("server", "server_root", "server_maps"):
        if isinstance(b.get(key), str) and b[key].strip():
            lines.append(f"{key} = {q(b[key].strip())}")
    shared = [str(s) for s in (b.get("shared") or []) if isinstance(s, str) and s.strip()]
    lines.append(f"shared = [{', '.join(q(s) for s in shared)}]")
    text = (open(CONFIG).read() if os.path.exists(CONFIG) else "") + "\n".join(lines) + "\n"
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ApiError(400, f"that would not be valid TOML: {e}")
    return save_config(text)


# ---------- what changed since the human last looked ----------

_state_lock = threading.Lock()


def load_seen():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def snapshot_states(maps):
    out = {}
    for m in maps:
        out[f"map:{m['id']}"] = m["status"]
        for t in m["tickets"]:
            out[t["id"]] = t["status"]
    return out


def changes_since(p, maps):
    seen = load_seen().get(p["name"])
    now = snapshot_states(maps)
    if not seen:
        return {"since": None, "items": []}
    titles = {t["id"]: (t["title"], m["id"], m["folder"], t["folder"]) for m in maps for t in m["tickets"]}
    titles.update({f"map:{m['id']}": (m["title"], m["id"], m["folder"], None) for m in maps})
    items = []
    for key, st in now.items():
        old = seen["states"].get(key)
        if old != st:
            title, mid, mfolder, tfolder = titles.get(key, ("", "", "", None))
            items.append({"id": key.replace("map:", ""), "map": mid, "map_folder": mfolder, "folder": tfolder,
                          "title": title, "from": old, "to": st, "is_map": key.startswith("map:")})
    return {"since": seen.get("at"), "items": items}


def mark_seen(name):
    p = project(name)
    maps = project_state(p, with_agents=False)["maps"]
    with _state_lock:
        s = load_seen()
        s[name] = {"at": dt.datetime.now().isoformat(timespec="minutes"), "states": snapshot_states(maps)}
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE + ".tmp", "w") as f:
            json.dump(s, f)
        os.replace(STATE + ".tmp", STATE)
    return {"ok": True}


# ---------- files: local and server, read-only ----------

def clean_rel(rel):
    rel = (rel or "").strip().lstrip("/")
    parts = [x for x in rel.split("/") if x not in ("", ".")]
    if any(x == ".." for x in parts):
        raise ApiError(400, "path may not contain ..")
    return "/".join(parts)


def hidden(name, is_dir):
    if is_dir:
        return name in HIDE_DIRS
    return name in HIDE_FILES or name.endswith(HIDE_EXT)


def classify(name):
    ext = os.path.splitext(name)[1].lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in (".md", ".markdown"):
        return "markdown"
    if ext in (".csv", ".tsv"):
        return "csv"
    if ext in (".json", ".jsonl"):
        return "json"
    if ext in LOG_EXT:
        return "log"
    return "text"


def inside(p, rel):
    """The real path of rel under the project, refusing symlinks that lead out of it."""
    root = os.path.realpath(p["path"])
    full = os.path.realpath(os.path.join(root, rel))
    if os.path.commonpath([root, full]) != root:
        raise ApiError(403, f"{rel} leads outside the project")
    return full


def local_tree(p, rel):
    base = inside(p, rel)
    if not os.path.isdir(base):
        raise ApiError(404, f"no folder {rel or '.'} on the Mac")
    entries = []
    for e in os.scandir(base):
        try:
            is_dir = e.is_dir()
            st = e.stat()
        except OSError:
            continue
        if hidden(e.name, is_dir):
            continue
        entries.append({"name": e.name, "dir": is_dir, "size": None if is_dir else st.st_size, "mtime": st.st_mtime})
    return entries


def local_read(p, rel, mode):
    path = inside(p, rel)
    if not os.path.isfile(path):
        raise ApiError(404, f"no file {rel} on the Mac")
    size = os.path.getsize(path)
    kind = classify(path)
    with open(path, "rb") as f:
        if kind == "image":
            if size > IMAGE_CAP:
                return {"kind": "too-big", "size": size}
            return {"kind": "image", "size": size, "mime": IMAGE_EXT[os.path.splitext(path)[1].lower()],
                    "data": base64.b64encode(f.read()).decode()}
        if kind == "log" and mode != "full":
            data = tail_lines(f, LOG_LINES)
            return text_result(kind, size, data, truncated=size > len(data), tail=True)
        if size <= CAP:
            return text_result(kind, size, f.read())
        head = f.read(HEAD_TAIL)
        f.seek(-HEAD_TAIL, os.SEEK_END)
        return text_result(kind, size, head, tail_bytes=f.read(), truncated=True)


def tail_lines(f, n):
    f.seek(0, os.SEEK_END)
    end = f.tell()
    pos, chunk, data = end, 64 << 10, b""
    while pos > 0 and data.count(b"\n") <= n and len(data) < TAIL_BYTES:
        step = min(chunk, pos)
        pos -= step
        f.seek(pos)
        data = f.read(step) + data
    return b"\n".join(data.split(b"\n")[-n - 1:])


def text_result(kind, size, data, tail_bytes=None, truncated=False, tail=False):
    if b"\0" in data[:8192]:
        return {"kind": "binary", "size": size}
    text = data.decode(errors="replace")
    if tail_bytes is not None:
        text += f"\n\n… {size - len(data) - len(tail_bytes):,} bytes not shown …\n\n" + tail_bytes.decode(errors="replace")
    return {"kind": kind, "size": size, "text": text, "truncated": truncated, "tail": tail}


SSH_OPTS = ["-o", "ClearAllForwardings=yes", "-o", "ControlMaster=auto", "-o", "ControlPath=~/.ssh/rg-%C",
            "-o", "ControlPersist=15m", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes"]
_cache, _cache_lock, _homes = {}, threading.Lock(), {}


def ssh(host, cmd, timeout=40):
    code, out, err = run(["ssh", *SSH_OPTS, host, cmd], timeout=timeout)
    if code != 0:
        raise ApiError(502, f"ssh {host}: {err.strip() or f'exit {code}'}")
    return out


def remote_path(p, rel):
    """Shell word for <server_root>/<rel>; a leading ~/ stays expandable."""
    if not p.get("server") or not p.get("server_root"):
        raise ApiError(400, f"project `{p['name']}` has no server/server_root in {CONFIG}")
    root = p["server_root"].rstrip("/")
    full = f"{root}/{rel}" if rel else root
    if full == "~" or full.startswith("~/"):
        return '"$HOME"' + (shlex.quote(full[1:]) if len(full) > 1 else "")
    return shlex.quote(full)


def cached(key, fresh, fn, ttl=None):
    with _cache_lock:
        hit = _cache.get(key)
        if not fresh and hit and (ttl is None or time.time() - hit[0] < ttl):
            return hit[1]
    val = fn()
    with _cache_lock:
        _cache[key] = (time.time(), val)
        if len(_cache) > CACHE_MAX:              # drop the oldest third
            for k, _ in sorted(_cache.items(), key=lambda kv: kv[1][0])[:CACHE_MAX // 3]:
                _cache.pop(k, None)
    return val


def server_tree(p, rel, fresh):
    def fetch():
        target = remote_path(p, rel)
        out = ssh(p["server"], f"cd -- {target} 2>/dev/null || {{ echo RG-MISSING; exit 0; }}; "
                               f"find . -mindepth 1 -maxdepth 1 -printf '%Y\\t%s\\t%T@\\t%f\\n'")
        text = out.decode(errors="replace")
        if text.startswith("RG-MISSING"):
            raise ApiError(404, f"nothing on {p['server']} yet: {p['server_root']}/{rel} doesn't exist (a map's server "
                                f"folder appears when its first ticket's code is written there)")
        entries = []
        for line in text.splitlines():
            parts = line.split("\t", 3)
            if len(parts) != 4:
                continue
            typ, size, mtime, name = parts
            is_dir = typ == "d"
            if hidden(name, is_dir):
                continue
            entries.append({"name": name, "dir": is_dir, "size": None if is_dir else int(size or 0),
                            "mtime": float(mtime or 0)})
        return entries
    return cached((p["server"], "tree", p["server_root"], rel), fresh, fetch)


def server_read(p, rel, mode, fresh):
    def fetch():
        f = remote_path(p, rel)
        kind = classify(rel)
        size_out = ssh(p["server"], f"stat -L -c %s -- {f} 2>/dev/null || echo RG-MISSING").decode().strip()
        if size_out == "RG-MISSING" or not size_out.isdigit():
            raise ApiError(404, f"no file {rel} on {p['server']}")
        size = int(size_out)
        if kind == "image":
            if size > IMAGE_CAP:
                return {"kind": "too-big", "size": size}
            data = ssh(p["server"], f"cat -- {f}", timeout=90)
            return {"kind": "image", "size": size, "mime": IMAGE_EXT[os.path.splitext(rel)[1].lower()],
                    "data": base64.b64encode(data).decode()}
        if kind == "log" and mode != "full":
            data = ssh(p["server"], f"tail -c {TAIL_BYTES} -- {f} | tail -n {LOG_LINES}")
            return text_result(kind, size, data, truncated=size > len(data), tail=True)
        if size <= CAP:
            return text_result(kind, size, ssh(p["server"], f"cat -- {f}", timeout=90))
        head = ssh(p["server"], f"head -c {HEAD_TAIL} -- {f}")
        tail = ssh(p["server"], f"tail -c {HEAD_TAIL} -- {f}")
        return text_result(kind, size, head, tail_bytes=tail, truncated=True)
    return cached((p["server"], "read", p["server_root"], rel, mode), fresh, fetch)


def server_home(host):
    if host not in _homes:
        _homes[host] = ssh(host, 'printf %s "$HOME"').decode().strip()
    return _homes[host]


def open_vscode(p, side, rel, is_dir):
    if side == "local":
        cmd = ["code", os.path.join(p["path"], rel)]
    else:
        root = p["server_root"].rstrip("/")
        if root == "~" or root.startswith("~/"):
            root = server_home(p["server"]) + root[1:]
        uri = f"vscode-remote://ssh-remote+{p['server']}{root}/{rel}".rstrip("/")
        cmd = ["code", "--folder-uri" if is_dir else "--file-uri", uri]
    code, _, err = run(cmd, timeout=20)
    if code != 0:
        raise ApiError(500, f"{' '.join(cmd)}: {err.strip()}")
    return {"ok": True, "cmd": " ".join(cmd)}


def reveal(p, rel):
    run(["open", "-R", inside(p, rel)], timeout=10)
    return {"ok": True}


# ---------- GPUs ----------

GPU_CMD = ("nvidia-smi --query-gpu=index,uuid,name,utilization.gpu,memory.used,memory.total,temperature.gpu "
           "--format=csv,noheader,nounits; echo RG-APPS; nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory "
           "--format=csv,noheader,nounits; echo RG-USERS; for p in $(nvidia-smi --query-compute-apps=pid "
           "--format=csv,noheader 2>/dev/null); do ps -o pid=,user= -p $p 2>/dev/null; done; echo RG-ME; id -un")


def gpu_hosts():
    cfg = load_config()
    hosts = cfg.get("gpu_hosts") or []
    for p in cfg["projects"].values():
        if p.get("server") and p["server"] not in hosts:
            hosts.append(p["server"])
    return hosts


def gpus(host, fresh):
    if host not in gpu_hosts():
        raise ApiError(400, f"{host} is not a project server or in gpu_hosts")

    def fetch():
        text = ssh(host, GPU_CMD, timeout=30).decode(errors="replace")
        gpu_part, rest = text.split("RG-APPS", 1)
        apps_part, rest = rest.split("RG-USERS", 1)
        users_part, me = rest.split("RG-ME", 1)
        me = me.strip()
        users = {}
        for line in users_part.split("\n"):
            bits = line.split()
            if len(bits) == 2:
                users[bits[0]] = bits[1]
        procs = {}
        for line in apps_part.strip().splitlines():
            bits = [b.strip() for b in line.split(",")]
            if len(bits) == 3:
                procs.setdefault(bits[0], []).append({"pid": bits[1], "mem": int(float(bits[2] or 0)),
                                                      "user": users.get(bits[1], "?")})
        out = []
        for line in gpu_part.strip().splitlines():
            b = [x.strip() for x in line.split(",")]
            if len(b) < 7:
                continue
            ps = procs.get(b[1], [])
            out.append({"index": int(b[0]), "name": b[2], "util": int(float(b[3] or 0)), "mem": int(float(b[4] or 0)),
                        "total": int(float(b[5] or 0)), "temp": int(float(b[6] or 0)), "procs": ps,
                        "mine": sum(1 for x in ps if x["user"] == me)})
        return {"host": host, "gpus": out, "me": me, "at": time.time()}
    return cached(("gpus", host), fresh, fetch, ttl=20)


# ---------- jobs: tmux sessions on the servers ----------

def ssh_hosts():
    """Host aliases from ~/.ssh/config (no wildcards): the only hosts a job may name."""
    hosts = set()
    try:
        for line in open(os.path.expanduser("~/.ssh/config")):
            parts = line.split()
            if len(parts) >= 2 and parts[0].lower() == "host":
                hosts.update(h for h in parts[1:] if not any(c in h for c in "*?!"))
    except OSError:
        pass
    return hosts | set(gpu_hosts())


def check_job(host, session):
    if host not in ssh_hosts():
        raise ApiError(400, f"{host} is not a host in ~/.ssh/config")
    if not re.fullmatch(r"[\w.:-]{1,64}", session or ""):
        raise ApiError(400, "bad tmux session name")


def tmux_peek(host, session, lines=200):
    check_job(host, session)
    out = ssh(host, f"tmux capture-pane -p -J -t {shlex.quote(session)} -S -{int(lines)} 2>&1 || echo RG-NO-SESSION; "
                    f"tmux list-sessions -F '#{{session_name}}' 2>/dev/null | head -50", timeout=30).decode(errors="replace")
    gone = "RG-NO-SESSION" in out or "can't find" in out
    text = out.split("RG-NO-SESSION")[0] if gone else out
    return {"host": host, "session": session, "alive": not gone, "text": text.rstrip()[-60000:]}


# ---------- skills (for the composer's / menu) ----------

BUILTIN = [("clear", "Start a fresh conversation"), ("compact", "Summarize the conversation to free context"),
           ("loop", "Run a prompt or command on an interval"), ("model", "Switch the model"),
           ("context", "Show context usage"), ("resume", "Resume an earlier conversation")]


def skills():
    out = []
    for path in sorted(glob.glob(os.path.expanduser("~/.claude/skills/*/SKILL.md"))):
        try:
            meta, _ = tracker.parse_front_matter(path)
        except OSError:
            continue
        name = meta.get("name") or os.path.basename(os.path.dirname(path))
        out.append({"name": name, "description": (meta.get("description") or "")[:300],
                    "hint": meta.get("argument-hint") or "", "kind": "skill"})
    out += [{"name": n, "description": d, "hint": "", "kind": "builtin"} for n, d in BUILTIN]
    return {"skills": out}


# ---------- chat ----------

def chat(pane, after, session):
    a, snap = live_agent(pane)
    sess = (a.get("agent_session") or {}).get("value")
    out = {"pane": pane, "agent": a.get("agent"), "status": a.get("agent_status"),
           "title": a.get("terminal_title_stripped"), "session": sess, "cwd": a.get("cwd")}
    path = rg_chat.transcript_path(sess, a.get("agent")) if a.get("agent") in ("claude", "codex") else None
    if path:
        if session != sess:
            after = None
        items, offset, cut = rg_chat.read(path, after)
        name_role(items, a.get("cwd"))
        out.update({"items": items, "offset": offset, "cut": cut, "transcript": path})
    else:
        out["items"], out["offset"] = [], 0
        out["fallback"] = screen(pane, "recent-unwrapped", 300)
    if a.get("agent_status") == "blocked":
        out["screen"] = screen(pane, "visible")
    return out


def name_role(items, cwd):
    """Messages from another session carry its session name; say which role that is (from the project's roster)."""
    froms = [it for it in items if it["k"] == "from"]
    if not froms:
        return
    p = next((p for p in load_config()["projects"].values() if in_folder(cwd, p["path"])), None)
    if not p:
        return
    by_session = {r["session"]: r for r in roster(p).values()}
    for it in froms:
        r = by_session.get(it["who"])
        if r:
            m = re.search(r"\b(T\d+)\b", r["map"] or "")
            it["role"] = r["role"] + (f" · {m.group(1)}" if m else "")


def screen(pane, source, lines=None):
    args = ["agent", "read", pane, "--source", source] + (["--lines", str(lines)] if lines else [])
    code, out, err = run(["herdr", *args], timeout=15)
    text = out.decode(errors="replace") if code == 0 else f"(could not read the screen: {err.strip()})"
    return "\n".join(l.rstrip() for l in text.splitlines()).strip("\n")


def chat_send(b):
    pane, text = b.get("pane"), (b.get("text") or "").strip()
    if not text:
        raise ApiError(400, "empty message")
    a, _ = live_agent(pane)
    if a.get("agent_status") == "blocked":
        raise ApiError(409, "the agent is waiting at a prompt: answer it first")
    try:
        herdr("agent", "prompt", pane, text, timeout=30)
    except HerdrError as e:
        raise ApiError(409 if e.code == "agent_blocked" else 502, str(e))
    _snap["t"] = 0
    return {"ok": True}


def chat_keys(b):
    keys = b.get("keys") or []
    if not keys or any(k not in KEYS for k in keys):
        raise ApiError(400, f"keys must be among {sorted(KEYS)}")
    live_agent(b.get("pane"))
    herdr("agent", "send-keys", b["pane"], *keys, timeout=15)
    _snap["t"] = 0
    return {"ok": True}


def chat_text(b):
    a, _ = live_agent(b.get("pane"))
    text = b.get("text") or ""
    if a.get("agent_status") != "blocked":
        raise ApiError(409, "typing into the screen is only for answering a prompt; send a message instead")
    if len(text) > 2000 or re.search(r"[\x00-\x1f\x7f]", text):
        raise ApiError(400, "answers are one line of plain text (at most 2000 characters)")
    herdr("pane", "send-text", b["pane"], text, timeout=15)
    return {"ok": True}


# ---------- starting agents in herdr ----------

KEYCHAIN_SERVICE = "claude-code-oauth"
_jobs = {}


def keychain_service():
    return load_config().get("keychain_service", KEYCHAIN_SERVICE)


_kc = {"t": 0, "v": False}


def keychain_has():
    if time.time() - _kc["t"] > 60:
        code, _, _ = run(["security", "find-generic-password", "-s", keychain_service()], timeout=5)
        _kc.update(t=time.time(), v=code == 0)
    return _kc["v"]


def slug(s, n=16):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9-]", "-", s.lower())).strip("-")[:n].strip("-")


def agent_name(p, role):
    prefix = slug(p["name"]) or "proj"
    if not prefix[0].isalpha():
        prefix = "p" + prefix
    return f"{prefix}-{role}"[:32]


def unique_name(name):
    code, out, _ = run(["herdr", "agent", "list"], timeout=10)
    try:
        names = {a.get("name") for a in json.loads(out)["result"]["agents"]} if code == 0 else set()
    except (ValueError, KeyError):
        names = set()
    if name not in names:
        return name
    for i in range(2, 100):
        cand = f"{name[:29]}-{i}"
        if cand not in names:
            return cand
    return f"{name[:24]}-{uuid.uuid4().hex[:6]}"


def role_settings(p):
    cfg = load_config()
    defaults = cfg.get("defaults", {})
    return (p.get("claude_args", defaults.get("claude_args", [])), p.get("codex_args", defaults.get("codex_args", [])),
            {**defaults.get("role_env", {}), **p.get("role_env", {})})


def team_plan(p, only_map=None):
    """The herdr steps to start a desk and drivers, skipping roles that are already live."""
    s = project_state(p)
    claude_args, _, role_env = role_settings(p)
    drivers = [m for m in s["maps"] if (m["folder"] == only_map if only_map else m["status"] in LIVE_MAP)]
    steps, notes = [], []
    if s["herdr_error"]:
        raise ApiError(503, f"herdr: {s['herdr_error']}")
    ws = workspace_for(p, s["agents"])
    for m in drivers:
        if m["driven"]:
            notes.append(f"{m['id']} already has a live driver: skipped")
            continue
        if m["status"] == "closed":
            notes.append(f"{m['id']} is closed: skipped")
            continue
        steps.append({"role": "driver", "kind": "claude", "map": m["id"], "label": f"B driver {m['id']}",
                      "name": agent_name(p, f"driver-{m['id'].lower()}"), "args": claude_args,
                      "prompt": f"/team driver {m['path'].rsplit('/', 1)[0]}", "env": role_env.get("driver", {})})
    if only_map is None:
        if any(a["role"] == "desk" for a in s["agents"]):
            notes.append("a desk is already live: skipped")
        else:
            steps.append({"role": "desk", "kind": "claude", "label": "A desk", "name": agent_name(p, "desk"),
                          "args": claude_args, "prompt": "/team desk", "env": role_env.get("desk", {})})
        if not drivers:
            notes.append("no open map that isn't paused: no driver started")
    return finish_plan(p, ws, steps, notes, s["keychain"])


def session_plan(p, b):
    """One new session in the project's herdr workspace: claude or codex (optionally with a first prompt), or a shell."""
    s = project_state(p)
    if s["herdr_error"]:
        raise ApiError(503, f"herdr: {s['herdr_error']}")
    claude_args, codex_args, role_env = role_settings(p)
    kind = b.get("kind") or "claude"
    if kind not in ("claude", "codex", "shell"):
        raise ApiError(400, "kind is claude, codex or shell")
    prompt = (b.get("prompt") or "").strip()
    label = (b.get("label") or "").strip() or (re.sub(r"^/", "", prompt)[:28] if prompt else kind)
    role = b.get("role") or ""
    st = {"role": role or kind, "kind": kind, "label": label, "prompt": prompt,
          "name": agent_name(p, slug(label, 14) or kind), "env": role_env.get(role, {}) if role else {},
          "args": claude_args if kind == "claude" else codex_args if kind == "codex" else [],
          "command": b.get("command") if kind == "shell" else None}
    return finish_plan(p, workspace_for(p, s["agents"]), [st], [], s["keychain"])


def finish_plan(p, ws, steps, notes, keychain):
    if any(st["kind"] == "claude" for st in steps) and not keychain:
        notes.append(f"no `{keychain_service()}` item in the Keychain: agents start with claude's own login")
    cmds = [] if ws["id"] else [f"herdr workspace create --cwd {p['path']} --label {p['name']} --no-focus"]
    for st in steps:
        env = "".join(f" --env {k}={v}" for k, v in st["env"].items())
        cmds.append(f"herdr tab create --workspace {ws['id'] or '<new>'} --cwd {p['path']} --label '{st['label']}'{env} --no-focus")
        if st["kind"] == "claude" and keychain:
            cmds.append(f"herdr pane run <pane> 'export CLAUDE_CODE_OAUTH_TOKEN=\"$(security find-generic-password "
                        f"-s {keychain_service()} -w)\"'")
        if st["kind"] in ("claude", "codex"):
            cmds.append(f"herdr agent start {st['name']} --kind {st['kind']} --pane <pane>"
                        + (f" -- {' '.join(st['args'])}" if st["args"] else ""))
        elif st.get("command"):
            cmds.append(f"herdr pane run <pane> {shlex.quote(st['command'])}")
        if st.get("prompt"):
            cmds.append(f"herdr agent prompt {st['name']} {shlex.quote(st['prompt'])}")
    return {"workspace": ws, "steps": steps, "notes": notes, "commands": cmds, "keychain": keychain,
            "dry_run": ARGS.dry_run}


def workspace_for(p, agents):
    """The herdr workspace holding the project's agents, else one labelled with its name."""
    if agents:
        counts = {}
        for a in agents:
            counts[a["workspace"]] = counts.get(a["workspace"], 0) + 1
        wid = max(counts, key=counts.get)
        return {"id": wid, "label": next(a["workspace_label"] for a in agents if a["workspace"] == wid)}
    snap, _ = herdr_snapshot()
    for w in (snap or {}).get("workspaces", []):
        if w.get("label") == p["name"]:
            return {"id": w["workspace_id"], "label": w["label"]}
    return {"id": None, "label": p["name"]}


def start_job(p, plan):
    jid = uuid.uuid4().hex[:8]
    job = {"id": jid, "log": [], "done": False, "ok": None, "panes": []}
    _jobs[jid] = job
    threading.Thread(target=run_plan, args=(p, plan, job), daemon=True).start()
    return {"job": jid}


def prompt_when_ready(name, prompt, say):
    """An agent stopped at a startup prompt (folder trust, login): send its first prompt once the human answered."""
    try:
        herdr("agent", "wait", name, "--until", "idle", "--timeout", "1800000", timeout=1850)
        herdr("agent", "prompt", name, prompt)
        say(f"{name}: startup prompt answered; sent `{prompt}`")
    except Exception as e:
        say(f"{name}: never got past its startup prompt ({e}); send `{prompt}` yourself")


def run_plan(p, plan, job):
    say = job["log"].append
    try:
        if ARGS.dry_run:
            say("dry run: nothing sent to herdr. These commands would run:")
            for c in plan["commands"]:
                say("  " + c)
            job["ok"] = True
            return
        wid, spare = plan["workspace"]["id"], None
        if not wid:
            r = herdr("workspace", "create", "--cwd", p["path"], "--label", p["name"], "--no-focus")
            wid, spare = r["workspace"]["workspace_id"], (r["tab"]["tab_id"], r["root_pane"]["pane_id"])
            say(f"created herdr workspace {p['name']} ({wid})")
        for i, st in enumerate(plan["steps"]):
            if st["role"] == "desk" and i > 0:
                say("waiting 20 s so the drivers join the roster before the desk reads it")
                time.sleep(20)
            if spare:                              # the new workspace's own first tab, instead of an empty extra one
                (tab, pane), spare = spare, None
                herdr("tab", "rename", tab, st["label"])
                if st["env"]:
                    time.sleep(0.8)
                    herdr("pane", "run", pane, "export " + " ".join(f"{k}={shlex.quote(str(v))}" for k, v in st["env"].items()))
            else:
                env = [x for k, v in st["env"].items() for x in ("--env", f"{k}={v}")]
                pane = herdr("tab", "create", "--workspace", wid, "--cwd", p["path"], "--label", st["label"], *env,
                             "--no-focus")["root_pane"]["pane_id"]
            job["panes"].append(pane)
            say(f"{st['label']}: tab created, pane {pane}")
            if st["kind"] == "shell":
                if st.get("command"):
                    time.sleep(1)
                    herdr("pane", "run", pane, st["command"])
                    say(f"{st['label']}: ran {st['command']}")
                continue
            if st["kind"] == "claude" and plan["keychain"]:
                time.sleep(0.8)
                herdr("pane", "run", pane, "export CLAUDE_CODE_OAUTH_TOKEN=\"$(security find-generic-password -s "
                      f"{shlex.quote(keychain_service())} -w)\"")
                time.sleep(1.5)   # let the shell finish the export before claude is typed
            name = unique_name(st["name"])
            try:
                herdr("agent", "start", name, "--kind", st["kind"], "--pane", pane, "--timeout", "120000",
                      *(["--", *st["args"]] if st["args"] else []), timeout=150)
                say(f"{st['label']}: {st['kind']} started as {name}")
            except HerdrError as e:
                if e.code != "agent_not_ready":
                    raise
                say(f"{st['label']}: {name} is waiting at a startup prompt; answer it in the chat")
                if st.get("prompt"):
                    threading.Thread(target=prompt_when_ready, args=(name, st["prompt"], say), daemon=True).start()
                continue
            if st.get("prompt"):
                herdr("agent", "prompt", name, st["prompt"])
                say(f"{st['label']}: sent `{st['prompt']}`")
        job["ok"] = True
    except Exception as e:
        say(f"failed: {e}")
        job["ok"] = False
    finally:
        job["done"] = True
        _snap["t"] = 0


def focus(pane):
    a, _ = live_agent(pane)
    herdr("workspace", "focus", a["workspace_id"])
    herdr("tab", "focus", a["tab_id"])
    herdr("agent", "focus", pane)
    app = load_config().get("terminal_app")
    if app:
        run(["open", "-a", app], timeout=10)
    return {"ok": True}


# ---------- settings ----------

def config_text():
    text = open(CONFIG).read() if os.path.exists(CONFIG) else open(os.path.join(HERE, "projects.example.toml")).read()
    return {"path": CONFIG, "text": text, "exists": os.path.exists(CONFIG)}


def save_config(text):
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ApiError(400, f"not valid TOML: {e}")
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    if os.path.exists(CONFIG):
        shutil.copy2(CONFIG, CONFIG + ".bak")
    with open(CONFIG + ".tmp", "w") as f:
        f.write(text)
    os.replace(CONFIG + ".tmp", CONFIG)
    return {"ok": True}


# ---------- terminals ----------

def term_argv(q):
    """argv, cwd and the bytes that detach cleanly, for a terminal of kind attach / shell / ssh."""
    kind = q.get("kind")
    if kind == "attach":
        a, _ = live_agent(q.get("pane"))
        return ["herdr", "agent", "attach", a["pane_id"]], a.get("cwd") or os.path.expanduser("~"), b"\x02q"
    p = project(q.get("project"))
    if kind == "shell":
        return [os.environ.get("SHELL", "/bin/zsh"), "-l"], p["path"], b""
    if kind == "tmux":
        check_job(q.get("host"), q.get("session"))
        return (["ssh", "-t", "-o", "ClearAllForwardings=yes", q["host"], f"tmux attach -t {shlex.quote(q['session'])}"],
                os.path.expanduser("~"), b"")
    if kind == "ssh":
        target = remote_path(p, clean_rel(q.get("path")))
        return (["ssh", "-t", "-o", "ClearAllForwardings=yes", p["server"],
                 f"cd {target} 2>/dev/null || cd {remote_path(p, '')}; exec $SHELL -l"], p["path"], b"")
    raise ApiError(400, "kind is attach, shell, ssh or tmux")


def term_env():
    env = {k: v for k, v in os.environ.items() if k not in ("HERDR_ENV", "HERDR_PANE_ID", "HERDR_TAB_ID", "HERDR_WORKSPACE_ID",
                                                           "CLAUDE_CODE_OAUTH_TOKEN")}
    env.update(TERM="xterm-256color", COLORTERM="truecolor")
    return env


# ---------- http ----------

STATIC_TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml",
                ".png": "image/png", ".woff2": "font/woff2", ".map": "application/json"}


class Handler(BaseHTTPRequestHandler):
    server_version = "research-gui"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        if ARGS.verbose:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % a))

    def origins(self):
        port = self.server.server_address[1]
        return (f"http://127.0.0.1:{port}", f"http://localhost:{port}")

    def allowed_host(self):
        port = self.server.server_address[1]
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.close_connection = True          # one request per connection: no request can hide in a rejected body
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                         "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' ws://127.0.0.1:* ws://localhost:*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.allowed_host():
            return self.send(403, {"error": "bad host"})
        url = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        if url.path.startswith("/ws/"):
            return self.websocket(url.path, q)
        if not url.path.startswith("/api/"):
            return self.static(url.path)
        if url.path == "/api/token":
            return self.send(200, {"token": TOKEN})
        if url.path != "/api/ping" and self.headers.get("X-RG-Token") != TOKEN:
            return self.send(403, {"error": "missing or stale token: reload the page"})
        self.api(lambda: self.get_api(url.path, q))

    def static(self, path):
        rel = "index.html" if path in ("/", "") else clean_rel(path)
        full = os.path.realpath(os.path.join(HERE, "web", rel))
        if not full.startswith(os.path.join(HERE, "web") + os.sep) or not os.path.isfile(full):
            return self.send(404, {"error": "not found"})
        with open(full, "rb") as f:
            self.send(200, f.read(), STATIC_TYPES.get(os.path.splitext(full)[1], "application/octet-stream"))

    def websocket(self, path, q):
        if self.headers.get("Origin") not in self.origins() or "websocket" not in (self.headers.get("Upgrade") or "").lower() \
                or q.get("token") != TOKEN:
            return self.send(403, {"error": "forbidden"})
        try:
            argv, cwd, detach = term_argv(q)
        except ApiError as e:
            return self.send(e.code, {"error": str(e)})
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", rg_term.accept_key(self.headers.get("Sec-WebSocket-Key", "")))
        self.end_headers()
        self.close_connection = True
        rg_term.serve(self, argv, cwd, term_env(), detach)

    def do_POST(self):
        origin = self.headers.get("Origin")
        if not self.allowed_host() or self.headers.get("X-RG") != "1" or (origin and origin not in self.origins()) \
                or self.headers.get("X-RG-Token") != TOKEN:
            return self.send(403, {"error": "forbidden"})
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self.send(400, {"error": "bad json"})
        self.api(lambda: self.post_api(urllib.parse.urlparse(self.path).path, body))

    def api(self, fn):
        try:
            self.send(200, fn())
        except ApiError as e:
            self.send(e.code, {"error": str(e)})
        except HerdrError as e:
            self.send(502, {"error": str(e)})
        except Exception as e:
            self.send(500, {"error": f"{type(e).__name__}: {e}"})

    def get_api(self, path, q):
        fresh = q.get("fresh") == "1"
        if path == "/api/ping":
            return {"ok": True, "app": "research-gui", "dry_run": ARGS.dry_run, "version": VERSION, "pid": os.getpid()}
        if path == "/api/projects":
            return projects_summary()
        if path == "/api/project":
            return project_state(project(q.get("name")))
        if path == "/api/tree":
            p, rel = project(q.get("project")), clean_rel(q.get("path"))
            return {"entries": local_tree(p, rel) if q.get("side") == "local" else server_tree(p, rel, fresh)}
        if path == "/api/file":
            p, rel = project(q.get("project")), clean_rel(q.get("path"))
            if q.get("side") == "local":
                return local_read(p, rel, q.get("mode"))
            return server_read(p, rel, q.get("mode"), fresh)
        if path == "/api/plan":
            return team_plan(project(q.get("project")), q.get("map") or None)
        if path == "/api/job":
            job = _jobs.get(q.get("id"))
            if not job:
                raise ApiError(404, "no such job")
            return job
        if path == "/api/chat":
            after = q.get("after")
            return chat(q.get("pane"), int(after) if after and after.isdigit() else None, q.get("session"))
        if path == "/api/skills":
            return skills()
        if path == "/api/gpus":
            return gpus(q.get("host"), fresh)
        if path == "/api/tmux":
            return tmux_peek(q.get("host"), q.get("session"))
        if path == "/api/gpu-hosts":
            return {"hosts": gpu_hosts()}
        if path == "/api/config":
            return config_text()
        raise ApiError(404, "unknown endpoint")

    def post_api(self, path, b):
        if path == "/api/start":
            p = project(b.get("project"))
            return start_job(p, team_plan(p, b.get("map") or None))
        if path == "/api/session":
            p = project(b.get("project"))
            return start_job(p, session_plan(p, b))
        if path == "/api/session-plan":
            return session_plan(project(b.get("project")), b)
        if path == "/api/focus":
            return focus(b.get("pane"))
        if path == "/api/vscode":
            p = project(b.get("project"))
            return open_vscode(p, b.get("side"), clean_rel(b.get("path")), bool(b.get("dir")))
        if path == "/api/reveal":
            return reveal(project(b.get("project")), clean_rel(b.get("path")))
        if path == "/api/add-project":
            return add_project(b)
        if path == "/api/chat/send":
            return chat_send(b)
        if path == "/api/chat/keys":
            return chat_keys(b)
        if path == "/api/chat/text":
            return chat_text(b)
        if path == "/api/seen":
            return mark_seen(b.get("project"))
        if path == "/api/config":
            return save_config(b.get("text") or "")
        raise ApiError(404, "unknown endpoint")


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def already_running(port):
    """The running research-gui's ping ({app, dry_run}), else None."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=2) as r:
            j = json.load(r)
            return j if j.get("app") == "research-gui" else None
    except Exception:
        return None


def port_holder(port):
    code, out, _ = run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fpc"], timeout=5)
    fields = dict((l[0], l[1:]) for l in out.decode().splitlines() if l)
    return f"{fields.get('c', '?')} (pid {fields['p']})" if "p" in fields else None


def app_installed():
    for d in ("~/Applications", "/Applications"):
        path = os.path.expanduser(f"{d}/{APP_NAME}.app")
        if os.path.isdir(path):
            return path
    return None


def main():
    global ARGS, CONFIG, STATE
    ap = argparse.ArgumentParser(description="research-gui: Research Desk's backend (a local app over the harness and herdr)")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--serve", action="store_true", help="only run the backend (what the app does)")
    ap.add_argument("--browser", action="store_true", help="open the page in a browser instead of the app")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="Start buttons only report the herdr commands")
    ap.add_argument("--config", help="projects file (default ~/.config/research-gui/projects.toml)")
    ap.add_argument("--verbose", action="store_true")
    ARGS = ap.parse_args()
    if ARGS.config:
        CONFIG = os.path.abspath(os.path.expanduser(ARGS.config))
        STATE = os.path.join(os.path.dirname(CONFIG), "seen.json")
    app = app_installed()
    if app and not (ARGS.serve or ARGS.browser or ARGS.no_open or ARGS.dry_run or ARGS.port or ARGS.config):
        subprocess.run(["open", app])          # the app starts (or reuses) the backend itself
        print(f"opening {APP_NAME} (its backend runs in the herdr workspace research-desk; --browser for a browser tab)")
        return
    port = ARGS.port or load_config().get("port", 8765)
    url = f"http://127.0.0.1:{port}/"
    live = already_running(port)
    if live:
        if bool(live.get("dry_run")) != ARGS.dry_run:
            sys.exit(f"research-gui is already running at {url} {'in' if live.get('dry_run') else 'without'} dry-run mode; "
                     f"stop it (Ctrl+C in its tab) and start again")
        print(f"research-gui is already running at {url}")
        if not (ARGS.no_open or ARGS.serve):
            subprocess.run(["open", url])
        return
    if not os.path.exists(CONFIG):
        print(f"note: no {CONFIG} yet; copy {os.path.join(HERE, 'projects.example.toml')} there")
    try:
        srv = Server(("127.0.0.1", port), Handler)
    except OSError as e:
        holder = port_holder(port)
        sys.exit(f"port {port} is taken{f' by {holder}' if holder else ''} and not answering ({e.strerror}).\n"
                 f"A research-gui suspended with Ctrl+Z still holds it: in that shell run `fg` then Ctrl+C, or `kill %1`;\n"
                 f"from anywhere: `kill {holder.split('pid ')[1].rstrip(')') if holder else '<pid>'}`. Or use --port.")
    signal.signal(signal.SIGTERM, lambda *_: os._exit(0))   # the app quitting: drop open terminals with us
    print(f"research-gui at {url}{'  (dry run: Start buttons send nothing)' if ARGS.dry_run else ''}"
          f"  [{dt.datetime.now():%H:%M}]", flush=True)
    if not (ARGS.no_open or ARGS.serve):
        threading.Timer(0.5, lambda: subprocess.run(["open", url])).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
