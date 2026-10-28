#!/usr/bin/env python3
"""research-gui: a local web page over the research harness, with herdr as the runtime.

Reads each project's maps and tickets (through status.py, so it agrees with `research-status`), shows the herdr agents
working in it, browses records on the Mac and code on the server (read-only), and starts a project's team in herdr.
Projects are listed in ~/.config/research-gui/projects.toml (see projects.example.toml).

Usage:
    research-gui [--port 8765] [--no-open] [--dry-run]
      --dry-run   Start team / Start driver only report the herdr commands they would send
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
import subprocess
import sys
import threading
import time
import tomllib
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import status as tracker  # noqa: E402  (tools/status.py, the `research-status` parser)

CONFIG = os.path.expanduser("~/.config/research-gui/projects.toml")
STATIC = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
          "/app.css": ("app.css", "text/css")}
CAP = 2 << 20                 # files larger than this show their first and last HEAD_TAIL bytes
HEAD_TAIL = 200 << 10
IMAGE_CAP = 8 << 20
LOG_LINES = 600
HIDE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".ipynb_checkpoints", ".mypy_cache", ".pytest_cache"}
HIDE_EXT = (".pt", ".pth", ".ckpt", ".safetensors", ".bin", ".pyc")
HIDE_FILES = {".DS_Store"}
IMAGE_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
             ".webp": "image/webp", ".svg": "image/svg+xml"}
LOG_EXT = (".log", ".out", ".err")
LIVE_MAP = {"open", "claimed"}          # maps that get a driver on Start team
ARGS = None


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


def herdr_snapshot():
    """The live herdr session, cached for 2 s."""
    with _snap_lock:
        if time.time() - _snap["t"] > 2:
            code, out, err = run(["herdr", "api", "snapshot"], timeout=10)
            try:
                _snap["data"] = json.loads(out)["result"]["snapshot"] if code == 0 else None
                _snap["err"] = None if code == 0 else (err.strip() or "herdr not running")
            except (ValueError, KeyError):
                _snap["data"], _snap["err"] = None, "unreadable herdr snapshot"
            _snap["t"] = time.time()
        return _snap["data"], _snap["err"]


def herdr(*args, timeout=150):
    code, out, err = run(["herdr", *args], timeout=timeout)
    if code != 0:
        raise RuntimeError(f"herdr {' '.join(args[:2])}: {err.strip() or out.decode(errors='replace').strip()}")
    try:
        return json.loads(out).get("result", {})
    except ValueError:
        return {}


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


def project_agents(p):
    """herdr agents whose folder is the project, each with its role (roster line, else tab label)."""
    snap, err = herdr_snapshot()
    if not snap:
        return [], err
    root = os.path.realpath(p["path"])
    tabs = {t["tab_id"]: t for t in snap.get("tabs", [])}
    spaces = {w["workspace_id"]: w for w in snap.get("workspaces", [])}
    ros = roster(p)
    out = []
    for a in snap.get("agents", []):
        cwd = os.path.realpath(a.get("cwd") or "")
        if cwd != root and not cwd.startswith(root + os.sep):
            continue
        tab = tabs.get(a.get("tab_id"), {})
        r = ros.get(a["pane_id"], {})
        label = tab.get("label", "")
        role = r.get("role") or next((w for w in ("desk", "driver", "worker", "implementer") if w in label.lower()), "")
        out.append({"pane": a["pane_id"], "tab": a.get("tab_id"), "workspace": a.get("workspace_id"),
                    "workspace_label": spaces.get(a.get("workspace_id"), {}).get("label", ""),
                    "agent": a.get("agent"), "status": a.get("agent_status"), "title": a.get("terminal_title_stripped"),
                    "tab_label": label, "role": role, "map": r.get("map", ""), "session": r.get("session", "")})
    return out, None


def live_driver_maps(agents, maps):
    """Map folders that already have a live driver (roster map field or tab label naming the map id)."""
    found = set()
    for a in agents:
        if a["role"] != "driver":
            continue
        for m in maps:
            folder = os.path.basename(os.path.dirname(m["_path"]))
            mid = (m.get("id") or "").lower()
            if folder in a["map"] or re.search(rf"\b{re.escape(mid)}\b", a["tab_label"].lower()):
                found.add(folder)
    return found


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
    return {"id": k.get("id"), "title": k.get("title"), "type": tracker.type_of(k), "status": tracker.status_of(k),
            "status_text": k.get("status"), "blocked_by": blockers, "superseded_by": k.get("superseded_by"),
            "path": k["_path"], "folder": os.path.basename(os.path.dirname(k["_path"])),
            "answered": k["_answered"], "unblocked": all(tracker.blocker_met(b, by_id) for b in blockers),
            "holder": tracker.holder(k)}


def project_state(p, with_agents=True):
    maps = tracker.load(p["path"]) if os.path.isdir(p["path"]) else []
    problems, frontier = tracker.analyse(maps) if maps else ([], {})
    by_id = {k.get("id"): k for m in maps for k in m["_archived"]}
    by_id.update({k.get("id"): k for m in maps for k in m["_tickets"]})
    agents, herdr_err = project_agents(p) if with_agents else ([], None)
    driven = live_driver_maps(agents, maps)
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
                                "text": t["title"], "path": t["path"]})
        waiting += [{"kind": "needs", "map": m.get("id"), "map_folder": folder, "text": n} for n in m["_needs"]]
        counts = {}
        for t in tickets:
            counts[t["status"]] = counts.get(t["status"], 0) + 1
        out_maps.append({"id": m.get("id"), "title": m.get("title"), "status": tracker.status_of(m),
                         "status_text": m.get("status"), "outcome": m.get("outcome"), "updated": m.get("updated"),
                         "destination": m["_destination"], "path": m["_path"], "folder": folder,
                         "legacy": m["_legacy"], "tickets": tickets, "fog": fog(body), "counts": counts,
                         "driven": folder in driven, "holder": tracker.holder(m)})
    waiting += [{"kind": "agent", "pane": a["pane"], "text": f"{a['role'] or a['agent']} in {a['tab_label'] or a['pane']} "
                 f"is waiting at a prompt", "role": a["role"]} for a in agents if a["status"] == "blocked"]
    return {"name": p["name"], "path": p["path"], "server": p.get("server"), "server_root": p.get("server_root"),
            "server_maps": p["server_maps"], "shared": p["shared"], "maps": out_maps, "waiting": waiting,
            "problems": problems, "agents": agents, "herdr_error": herdr_err,
            "keychain": keychain_has(), "dry_run": ARGS.dry_run}


def projects_summary():
    cfg = load_config()
    out = []
    for name, p in cfg["projects"].items():
        try:
            s = project_state(p)
            out.append({"name": name, "ok": True, "waiting": len(s["waiting"]),
                        "working": sum(a["status"] == "working" for a in s["agents"]),
                        "blocked": sum(a["status"] == "blocked" for a in s["agents"]),
                        "agents": len(s["agents"]),
                        "open_maps": sum(m["status"] != "closed" for m in s["maps"])})
        except Exception as e:  # one broken project must not hide the others
            out.append({"name": name, "ok": False, "error": str(e)})
    registered = {os.path.realpath(p["path"]) for p in cfg["projects"].values()}
    found = []
    for root in cfg.get("roots", []):
        for d in sorted(glob.glob(os.path.join(os.path.expanduser(root), "*"))):
            if os.path.realpath(d) in registered or not os.path.isdir(d):
                continue
            if glob.glob(os.path.join(d, "maps", "*", "map.md")) or glob.glob(os.path.join(d, "tracks", "*", "track.md")):
                found.append({"name": os.path.basename(d), "path": d})
    return {"projects": out, "unregistered": found, "config": CONFIG}


def add_project(name, path):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name or ""):
        raise ApiError(400, "bad project name")
    if name in load_config()["projects"]:
        raise ApiError(400, f"`{name}` is already registered")
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, "a") as f:
        f.write(f'\n[projects.{name}]\npath = {json.dumps(path)}\n# server = "<ssh host>"\n'
                f'# server_root = "~/code/{name}"\n# server_maps = "tracks"\n# shared = ["common"]\n')
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


def local_tree(p, rel):
    base = os.path.join(p["path"], rel)
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
    path = os.path.join(p["path"], rel)
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
    while pos > 0 and data.count(b"\n") <= n:
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


def cached(key, fresh, fn):
    with _cache_lock:
        if not fresh and key in _cache:
            return _cache[key]
    val = fn()
    with _cache_lock:
        _cache[key] = val
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
            data = ssh(p["server"], f"tail -n {LOG_LINES} -- {f}")
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


# ---------- starting agents in herdr ----------

KEYCHAIN_SERVICE = "claude-code-oauth"
_jobs = {}


def keychain_service():
    return load_config().get("keychain_service", KEYCHAIN_SERVICE)


def keychain_has():
    code, _, _ = run(["security", "find-generic-password", "-s", keychain_service()], timeout=5)
    return code == 0


def agent_name(p, role):
    prefix = re.sub(r"[^a-z0-9-]", "-", p["name"].lower())[:16].strip("-") or "proj"
    if not prefix[0].isalpha():
        prefix = "p" + prefix
    return f"{prefix}-{role}"[:32]


def team_plan(p, only_map=None):
    """The herdr steps to start a desk and drivers, skipping roles that are already live."""
    s = project_state(p)
    cfg = load_config()
    defaults = cfg.get("defaults", {})
    claude_args = p.get("claude_args", defaults.get("claude_args", []))
    role_env = {**defaults.get("role_env", {}), **p.get("role_env", {})}
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
        steps.append({"role": "driver", "map": m["id"], "label": f"B driver {m['id']}",
                      "name": agent_name(p, f"driver-{m['id'].lower()}"),
                      "prompt": f"/team driver {m['path'].rsplit('/', 1)[0]}",
                      "env": role_env.get("driver", {})})
    if only_map is None:
        if any(a["role"] == "desk" for a in s["agents"]):
            notes.append("a desk is already live: skipped")
        else:
            steps.append({"role": "desk", "label": "A desk", "name": agent_name(p, "desk"), "prompt": "/team desk",
                          "env": role_env.get("desk", {})})
        if not drivers:
            notes.append("no open map that isn't paused: no driver started")
    if not s["keychain"]:
        notes.append(f"no `{keychain_service()}` item in the Keychain: agents start with claude's own login")
    cmds = []
    for st in steps:
        env = " ".join(f"--env {k}={v}" for k, v in st["env"].items())
        cmds.append(f"herdr tab create --workspace {ws['id'] or '<new>'} --cwd {p['path']} --label '{st['label']}' "
                    f"{env} --no-focus".replace("  ", " "))
        if s["keychain"]:
            cmds.append(f"herdr pane run <pane> 'export CLAUDE_CODE_OAUTH_TOKEN=\"$(security find-generic-password "
                        f"-s {keychain_service()} -w)\"'")
        cmds.append(f"herdr agent start {st['name']} --kind claude --pane <pane>"
                    + (f" -- {' '.join(claude_args)}" if claude_args else ""))
        cmds.append(f"herdr agent prompt {st['name']} '{st['prompt']}'")
    if not ws["id"]:
        cmds.insert(0, f"herdr workspace create --cwd {p['path']} --label {p['name']} --no-focus")
    return {"workspace": ws, "steps": steps, "notes": notes, "commands": cmds, "claude_args": claude_args,
            "keychain": s["keychain"], "dry_run": ARGS.dry_run}


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
    job = {"id": jid, "log": [], "done": False, "ok": None}
    _jobs[jid] = job
    threading.Thread(target=run_plan, args=(p, plan, job), daemon=True).start()
    return {"job": jid}


def run_plan(p, plan, job):
    say = job["log"].append
    try:
        if ARGS.dry_run:
            say("dry run: nothing sent to herdr. These commands would run:")
            for c in plan["commands"]:
                say("  " + c)
            job["ok"] = True
            return
        wid = plan["workspace"]["id"]
        if not wid:
            r = herdr("workspace", "create", "--cwd", p["path"], "--label", p["name"], "--no-focus")
            wid = r["workspace"]["workspace_id"]
            say(f"created herdr workspace {p['name']} ({wid})")
        for i, st in enumerate(plan["steps"]):
            if st["role"] == "desk" and i > 0:
                say("waiting 20 s so the drivers join the roster before the desk reads it")
                time.sleep(20)
            env = [x for k, v in st["env"].items() for x in ("--env", f"{k}={v}")]
            pane = herdr("tab", "create", "--workspace", wid, "--cwd", p["path"], "--label", st["label"], *env,
                         "--no-focus")["root_pane"]["pane_id"]
            say(f"{st['label']}: tab created, pane {pane}")
            if plan["keychain"]:
                herdr("pane", "run", pane, "export CLAUDE_CODE_OAUTH_TOKEN=\"$(security find-generic-password -s "
                      f"{keychain_service()} -w)\"")
                time.sleep(1.5)   # let the shell finish the export before claude is typed
            herdr("agent", "start", st["name"], "--kind", "claude", "--pane", pane, "--timeout", "120000",
                  *(["--", *plan["claude_args"]] if plan["claude_args"] else []), timeout=150)
            say(f"{st['label']}: claude started as {st['name']}")
            herdr("agent", "prompt", st["name"], st["prompt"])
            say(f"{st['label']}: sent `{st['prompt']}`")
        job["ok"] = True
    except Exception as e:
        say(f"failed: {e}")
        job["ok"] = False
    finally:
        job["done"] = True


def focus(pane):
    snap, err = herdr_snapshot()
    if not snap:
        raise ApiError(503, f"herdr: {err}")
    a = next((a for a in snap.get("agents", []) if a["pane_id"] == pane), None)
    if not a:
        raise ApiError(404, f"no live agent in pane {pane}")
    herdr("workspace", "focus", a["workspace_id"])
    herdr("tab", "focus", a["tab_id"])
    herdr("agent", "focus", pane)
    app = load_config().get("terminal_app")
    if app:
        run(["open", "-a", app], timeout=10)
    return {"ok": True}


# ---------- http ----------

class Handler(BaseHTTPRequestHandler):
    server_version = "research-gui"

    def log_message(self, fmt, *a):
        if ARGS.verbose:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % a))

    def allowed_host(self):
        port = self.server.server_address[1]
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
                         "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; img-src 'self' data:; "
                         "connect-src 'self'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.allowed_host():
            return self.send(403, {"error": "bad host"})
        url = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        if url.path in STATIC:
            name, ctype = STATIC[url.path]
            with open(os.path.join(HERE, name), "rb") as f:
                return self.send(200, f.read(), ctype)
        self.api(lambda: self.get_api(url.path, q))

    def do_POST(self):
        port = self.server.server_address[1]
        origin = self.headers.get("Origin")
        if not self.allowed_host() or self.headers.get("X-RG") != "1" or \
                (origin and origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")):
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
        except Exception as e:
            self.send(500, {"error": f"{type(e).__name__}: {e}"})

    def get_api(self, path, q):
        fresh = q.get("fresh") == "1"
        if path == "/api/ping":
            return {"ok": True, "app": "research-gui", "dry_run": ARGS.dry_run}
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
        raise ApiError(404, "unknown endpoint")

    def post_api(self, path, b):
        if path == "/api/start":
            p = project(b.get("project"))
            return start_job(p, team_plan(p, b.get("map") or None))
        if path == "/api/focus":
            return focus(b.get("pane"))
        if path == "/api/vscode":
            p = project(b.get("project"))
            return open_vscode(p, b.get("side"), clean_rel(b.get("path")), bool(b.get("dir")))
        if path == "/api/add-project":
            return add_project(b.get("name"), b.get("path"))
        raise ApiError(404, "unknown endpoint")


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


def main():
    global ARGS
    ap = argparse.ArgumentParser(description="research-gui: local web page over the research harness and herdr")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="Start buttons only report the herdr commands")
    ap.add_argument("--verbose", action="store_true")
    ARGS = ap.parse_args()
    port = ARGS.port or load_config().get("port", 8765)
    url = f"http://127.0.0.1:{port}/"
    live = already_running(port)
    if live:
        if bool(live.get("dry_run")) != ARGS.dry_run:
            sys.exit(f"research-gui is already running at {url} {'in' if live.get('dry_run') else 'without'} dry-run mode; "
                     f"stop it (Ctrl+C in its tab) and start again")
        print(f"research-gui is already running at {url}")
        if not ARGS.no_open:
            subprocess.run(["open", url])
        return
    if not os.path.exists(CONFIG):
        print(f"note: no {CONFIG} yet; copy {os.path.join(HERE, 'projects.example.toml')} there")
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        holder = port_holder(port)
        sys.exit(f"port {port} is taken{f' by {holder}' if holder else ''} and not answering ({e.strerror}).\n"
                 f"A research-gui suspended with Ctrl+Z still holds it: in that shell run `fg` then Ctrl+C, or `kill %1`;\n"
                 f"from anywhere: `kill {holder.split('pid ')[1].rstrip(')') if holder else '<pid>'}`. Or use --port.")
    print(f"research-gui at {url}{'  (dry run: Start buttons send nothing)' if ARGS.dry_run else ''}"
          f"  [{dt.datetime.now():%H:%M}]")
    if not ARGS.no_open:
        threading.Timer(0.5, lambda: subprocess.run(["open", url])).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
