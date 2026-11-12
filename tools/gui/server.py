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
import rg_notify  # noqa: E402

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
        if p.get("host"):          # a project on another machine: its records are mirrored here (sync_remote)
            p["remote_host"], p["remote_path"] = p["host"], p["path"]
            p["path"] = os.path.join(REMOTE_CACHE, name)
            p.setdefault("server", p["host"])
            p.setdefault("server_root", p["remote_path"])
        p["path"] = os.path.expanduser(p["path"])
        p.setdefault("shared", [])
        p.setdefault("server_maps", "maps")
        p["muted"] = p.get("inbox") is False       # inbox = false: its tickets stay out of the Inbox and alerts
    return cfg


# ---------- remote projects: records on another machine (e.g. engaging), mirrored here read-only ----------

REMOTE_CACHE = os.path.expanduser("~/Library/Caches/research-gui/remote")
REMOTE_SKIP = [".git/", "artifacts/", "data/", "checkpoints/", "unsloth_compiled_cache/", "wandb/", "lit/", "node_modules/",
               "__pycache__/", ".venv/", "envs/", "outputs/", "results/raw/"]
REMOTE_KEEP = ["*.md", "*.json", "*.jsonl", "*.csv", "*.tsv", "*.yaml", "*.yml", "*.toml", "*.txt", "*.log", "*.png", "*.svg"]
REMOTE_SESSIONS = os.path.join(REMOTE_CACHE, ".sessions")   # <project>/<encoded dir>/<session>.jsonl, read-only
SESSION_HOURS = 24                                          # conversations written to in the last day are shown
rg_chat.EXTRA_DIRS.append(REMOTE_SESSIONS)

# How the app reaches a remote host. It once flooded Engaging's login008: a check every few seconds, each a new ssh
# through a ProxyCommand hop, none waiting for the last, a timeout that didn't cover the hop, abandoned hops left
# running; when the link stalled, connections piled up until sshd refused everyone. Now every call goes through
# host_call: one at a time per host, only over the shared connection (ssh's ControlMaster, opened by a person, since
# Engaging needs Duo), a hard deadline that kills the call's whole process group, and back-off after a failure.
# tests/remote_calls_test.py holds it to that (run by scripts/check.py).
REMOTE_EVERY = 300          # records and conversations: every 5 min, and on opening a project or Sync now
HERDR_EVERY = 20            # live sessions' status: only while a project or chat of that host was open lately
DEMAND = 180                # "open lately": the last 3 minutes
PULL_EVERY = 15             # the conversation open in the chat
CALL_LIMIT = 30             # seconds for an ssh call, whatever it went through
RSYNC_LIMIT = 120           # seconds for an rsync (a first mirror of a project's records)
BACKOFF = [30, 60, 120, 240, 480, 900]
SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ClearAllForwardings=yes",
            "-o", "ControlMaster=no", "-o", "ControlPersist=no"]   # use the shared connection, never become one
SSH_BATCH = "ssh " + " ".join(SSH_OPTS)
LINK_FAIL = re.compile(r"Permission denied|Connection (refused|reset|closed|timed out)|timed out|Broken pipe|Could not "
                       r"resolve|No route|kex_exchange|banner exchange|Control socket|mux_client|no answer within")
PAUSE_FILE = os.path.expanduser("~/.config/research-gui/remote-paused")   # hosts the app must not contact, one per line
_hosts, _hosts_lock = {}, threading.Lock()


def paused(host):
    """A host the person told the app not to contact (listed in PAUSE_FILE) gets no call at all, not even ssh -O check."""
    try:
        with open(PAUSE_FILE) as f:
            return host in f.read().split()
    except OSError:
        return False
_remote = {}


def host_state(host):
    with _hosts_lock:
        return _hosts.setdefault(host, {"lock": threading.Lock(), "fails": 0, "until": 0.0, "state": "unknown",
                                        "error": None, "demand": 0.0, "calls": 0})


def run_group(cmd, timeout, input=None):
    """Run argv in a process group of its own; at the deadline kill the whole group (ssh, a ProxyCommand hop, rsync's
    ssh), so a call that never gets an answer leaves nothing behind. (code, stdout bytes, stderr text); 124 on timeout."""
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = p.communicate(input, timeout=timeout)
        return p.returncode, out, err.decode(errors="replace")
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        p.communicate()
        return 124, b"", f"no answer within {timeout} s"


def link_up(host):
    """Is the host's shared connection open? A local question to ssh's control socket; nothing goes on the network."""
    return run_group(["ssh", "-O", "check", host], 5)[0] == 0


def host_call(host, cmd, timeout=None, input=None, wait=0.0, force=False):
    """The one way the app reaches a remote host (ssh or rsync over ssh). A background check skips when a call to the
    host is running (wait=0); a person's action waits up to `wait` s and goes even in back-off (force). Raises ApiError
    when it can't call: 409 busy, 503 not connected or unreachable (then nothing is tried for 30 s, 1, 2, 4, 8, 15 min)."""
    st, timeout = host_state(host), timeout or CALL_LIMIT
    if paused(host):
        st.update(state="paused", error=f"paused: the app doesn't contact {host} until you resume it ({PAUSE_FILE})")
        raise ApiError(503, st["error"])
    left = st["until"] - time.time()
    if left > 0 and not force:
        raise ApiError(503, f"{host} unreachable ({st['error']}); next try in {int(left)} s")
    if not (st["lock"].acquire(timeout=wait) if wait else st["lock"].acquire(blocking=False)):
        raise ApiError(409, f"{host} is busy with another call; try again in a moment")
    try:
        if not link_up(host):
            st.update(state="no-link", error=f"not connected: log in to {host} once in a terminal (Duo), then Sync now")
            raise ApiError(503, st["error"])
        st["calls"] += 1
        code, out, err = run_group(cmd, timeout, input)
        if code == 124 or (code != 0 and LINK_FAIL.search(err or "")):
            st["fails"] += 1
            lines = [l for l in (err or "").strip().splitlines() if l.strip()]
            st.update(state="down", error=(lines[-1] if lines else f"exit {code}")[:200],
                      until=time.time() + BACKOFF[min(st["fails"], len(BACKOFF)) - 1])
            raise ApiError(503, f"{host} unreachable: {st['error']}")
        st.update(state="ok", fails=0, until=0.0, error=None)
        return code, out, err
    finally:
        st["lock"].release()


def remote_ssh(host, command, **kw):
    return host_call(host, ["ssh", *SSH_OPTS, host, command], **kw)


def want(host):
    host_state(host)["demand"] = time.time()


def wanted(host):
    return time.time() - host_state(host)["demand"] < DEMAND


def remote_hosts():
    return sorted({p["remote_host"] for p in load_config()["projects"].values() if p.get("remote_host")})


def synced_at(p):
    """When the project was last mirrored: this run's sync, else the stamp a previous run left on disk."""
    at = (_remote.get(p["name"]) or {}).get("at")
    if at:
        return at
    try:
        with open(os.path.join(REMOTE_CACHE, f".{p['name']}.synced")) as f:
            return float(f.read().strip())
    except (OSError, ValueError):
        return None


def sync_remote(p, wait=0.0, force=False):
    """Mirror a remote project's records (text and small figures, under 2 MB each) and its recent conversations over the
    shared connection; agents and code stay there. Returns {at, error}: the last good sync and the last failure."""
    st = _remote.setdefault(p["name"], {"at": 0, "error": None})
    if not os.path.realpath(p["path"]).startswith(os.path.realpath(REMOTE_CACHE) + os.sep):
        raise ApiError(500, "remote mirror outside the cache")             # --delete must never touch anything else
    os.makedirs(p["path"], exist_ok=True)
    cmd = ["rsync", "-rtzm", "--delete", "--max-size=2m", "-e", SSH_BATCH]
    cmd += [f"--exclude={x}" for x in REMOTE_SKIP] + ["--include=*/"] + [f"--include={x}" for x in REMOTE_KEEP]
    cmd += ["--exclude=*", f"{p['remote_host']}:{p['remote_path'].rstrip('/')}/", p["path"] + "/"]
    try:
        code, _, err = host_call(p["remote_host"], cmd, RSYNC_LIMIT, wait=wait, force=force)
    except ApiError as e:
        if e.code != 409:
            st["error"] = str(e)
        return st
    if code != 0:
        lines = [l for l in err.strip().splitlines() if l.strip()]
        st["error"] = (lines[-1] if lines else f"rsync exit {code}")[:300]
        return st
    st.update(at=time.time(), error=None)
    with open(os.path.join(REMOTE_CACHE, f".{p['name']}.synced"), "w") as f:   # outside the mirror: --delete keeps off it
        f.write(str(st["at"]))
    try:
        sync_remote_sessions(p, wait=wait)
    except ApiError:
        pass
    return st


def sync_remote_sessions(p, wait=0.0):
    """Copy the project's Claude conversations written to in the last day (from ~/.claude/projects there, any folder
    whose name ends in the project's) beside the mirror, so the app can list and show them; rsync sends only what grew."""
    enc = re.sub(r"[^A-Za-z0-9]", "-", "/".join(p["remote_path"].rstrip("/").split("/")[-2:]))
    find = (f"cd ~/.claude/projects 2>/dev/null && find . -maxdepth 2 -name '*.jsonl' -mmin -{SESSION_HOURS * 60} -size -80M "
            f"| grep -E '^\\./[^/]*{enc}(-[^/]*)?/' || true")
    code, out, _ = remote_ssh(p["remote_host"], find, wait=wait)
    if code != 0:
        return
    files = [l.strip()[2:] for l in out.decode(errors="replace").splitlines() if l.strip().startswith("./")]
    dest = os.path.join(REMOTE_SESSIONS, p["name"])
    os.makedirs(dest, exist_ok=True)
    if files:
        host_call(p["remote_host"], ["rsync", "-tz", "--files-from=-", "-e", SSH_BATCH, f"{p['remote_host']}:~/.claude/projects/",
                                     dest + "/"], RSYNC_LIMIT, input="\n".join(files).encode(), wait=wait)
    keep = {os.path.join(dest, f) for f in files}
    for f in glob.glob(os.path.join(dest, "*", "*.jsonl")):                # older than a day there: drop the copy
        if f not in keep:
            os.remove(f)


REMOTE_HERDR = 'H=$(command -v herdr || echo ~/.local/bin/herdr); "$H"'
_rsnap = {}        # host -> {"t", "agents", "snap", "error"}: its herdr, while someone looks


def remote_herdr(host, *args, timeout=None, wait=20.0):
    """Run herdr on a remote host (a person's action: it waits for a running call); its JSON result."""
    code, out, err = remote_ssh(host, REMOTE_HERDR + " " + " ".join(shlex.quote(a) for a in args), timeout=timeout,
                                wait=wait, force=True)
    try:
        d = json.loads(out or err)                  # herdr prints its errors as JSON on stderr
    except ValueError:
        raise ApiError(502, f"herdr on {host}: {(err or out.decode(errors='replace')).strip()[:200] or f'exit {code}'}")
    if "error" in d:
        raise ApiError(502, f"herdr on {host}: {d['error'].get('message')}")
    return d.get("result", d)


def refresh_remote_herdr(host, wait=0.0, force=False):
    """The host's live sessions and tabs, in one call (herdr agent list, then api snapshot)."""
    sep = "@@research-desk@@"
    try:
        code, out, err = remote_ssh(host, f"{REMOTE_HERDR} agent list; echo {sep}; {REMOTE_HERDR} api snapshot",
                                    wait=wait, force=force)
        a, _, b = out.decode(errors="replace").partition(sep)
        names = (json.loads(a).get("result") or {}).get("agents", [])
        snap = (json.loads(b).get("result") or {}).get("snapshot", {})
        _rsnap[host] = {"t": time.time(), "agents": names, "snap": snap, "error": None}
    except ApiError as e:
        if e.code != 409:                             # busy: keep what we have
            _rsnap[host] = dict(_rsnap.get(host) or {}, t=time.time(), error=str(e))
    except ValueError:
        _rsnap[host] = dict(_rsnap.get(host) or {}, t=time.time(), error=f"herdr on {host}: no readable answer")


def remote_herdr_loop():
    while True:
        for host in remote_hosts():
            if wanted(host):
                refresh_remote_herdr(host)
        time.sleep(HERDR_EVERY)


def remote_agent(p, pane, sid, path, **kw):
    """A remote session shaped like the app's agents (agent_view), its conversation read from the mirror."""
    return {"pane": f"remote:{p['name']}:{pane}", "tab": None, "workspace": None, "workspace_label": p["remote_host"],
            "agent": "claude", "cwd": None, "transcript": bool(path), "session_id": sid, "session": "", "map": "",
            "safeguard": rg_chat.last_safeguard(path) if path else None, "turn_end": rg_chat.last_turn_end(path) if path else None,
            "loop": rg_chat.loop_state(path) if path else None, "api_error": rg_chat.last_api_error(path) if path else None,
            "model": rg_chat.last_model(path) if path else None, "effort": rg_chat.last_effort(path) if path else None,
            "remote": p["remote_host"],
            "last_active": os.path.getmtime(path) if path else None, **kw}


def remote_sessions(p):
    """The project's sessions on its host. With its herdr reachable: the live ones, with their real status, and the app
    can type into them (remote_send). Otherwise the conversations written to in the last day, read-only."""
    mirrored = {os.path.basename(f)[:-6]: f for f in glob.glob(os.path.join(REMOTE_SESSIONS, p["name"], "*", "*.jsonl"))}
    rs = _rsnap.get(p["remote_host"]) or {}
    if rs.get("agents") is not None and not rs.get("error") and time.time() - rs.get("t", 0) < 2 * DEMAND:
        tail = "/" + "/".join(p["remote_path"].rstrip("/").split("/")[-2:]) + "/"
        ros = roster(p)
        tabs = {t["tab_id"]: t for t in (rs.get("snap") or {}).get("tabs", [])}
        out = []
        for a in rs["agents"]:
            if tail not in (a.get("cwd") or "") + "/" and a["pane_id"] not in ros:
                continue
            sid = (a.get("agent_session") or {}).get("value")
            path = mirrored.get(sid)
            name, label = a.get("name") or "", tabs.get(a.get("tab_id"), {}).get("label", "")
            r = ros.get(a["pane_id"], {})
            role = r.get("role") or next((w for w in ("desk", "driver", "worker") if w in f"{label} {name}".lower()), "")
            kw = dict(status=a.get("agent_status"), live=True, name=name, role=role, map=r.get("map", ""),
                      title=(rg_chat.title_of(path) if path else None) or a.get("terminal_title_stripped") or name,
                      tab_label=label or name, session=r.get("session", ""), remote_pane=a["pane_id"])
            kw.update(btw_fields(f"remote:{p['name']}:{a['pane_id']}"))
            out.append(remote_agent(p, a["pane_id"], sid, path, **kw))
        order = {"desk": 0, "driver": 1, "worker": 2}
        return sorted(out, key=lambda a: (order.get(a["role"], 3), a["tab_label"]))
    out = []
    for sid, f in mirrored.items():
        mt = os.path.getmtime(f)
        if time.time() - mt > SESSION_HOURS * 3600:
            continue
        end = rg_chat.last_turn_end(f)
        title = rg_chat.title_of(f) or "Claude session"
        out.append(remote_agent(p, sid, sid, f, status="working" if time.time() - mt < 300 and mt - (rg_chat_ts(end) if end else 0) > 20 else "idle",
                                live=False, name=None, title=title, tab_label=title, role=""))
    return sorted(out, key=lambda a: -a["last_active"])


_pulled = {}


def pull_session(p, sid):
    """Fetch the conversation open in the chat, at most every PULL_EVERY s, skipped while another call to the host
    runs; its local path (the last copy when the host can't be reached)."""
    local = rg_chat.transcript_path(sid) if re.fullmatch(r"[0-9a-fA-F-]{8,64}", sid or "") else None
    if not re.fullmatch(r"[0-9a-fA-F-]{8,64}", sid or "") or time.time() - _pulled.get(sid, 0) < PULL_EVERY:
        return local
    _pulled[sid] = time.time()
    root = os.path.join(REMOTE_SESSIONS, p["name"])
    rel = os.path.relpath(local, root) if local and local.startswith(root + os.sep) else None
    try:
        if not rel:
            code, out, _ = remote_ssh(p["remote_host"], f"cd ~/.claude/projects 2>/dev/null && ls -1 */{sid}.jsonl 2>/dev/null | head -1")
            rel = out.decode(errors="replace").strip()
            if code != 0 or not rel or ".." in rel:
                return local
        dest = os.path.join(root, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        host_call(p["remote_host"], ["rsync", "-tz", "-e", SSH_BATCH, f"{p['remote_host']}:~/.claude/projects/{rel}", dest], RSYNC_LIMIT)
        return dest if os.path.exists(dest) else local
    except ApiError:
        return local


def remote_send(b):
    """Type a message into a live session on a remote host, through its herdr."""
    _, name, rpane = b["pane"].split(":", 2)
    p = project(name)
    a = next((x for x in remote_sessions(p) if x.get("remote_pane") == rpane), None)
    if not a or not a.get("live"):
        raise ApiError(404, f"no live session {rpane} on {p['remote_host']} (its herdr isn't reachable, or it ended)")
    if a["status"] == "blocked":
        raise ApiError(409, f"it is waiting at a prompt on {p['remote_host']}: answer it in its terminal there")
    remote_herdr(p["remote_host"], "agent", "prompt", rpane, (b.get("text") or "").strip(), timeout=40)
    _pulled.pop(a.get("session_id"), None)
    refresh_remote_herdr(p["remote_host"], wait=10, force=True)
    return {"ok": True, "cleared": ""}


def remote_info(p):
    st, h = _remote.get(p["name"]) or {}, host_state(p["remote_host"])
    left = h["until"] - time.time()
    if paused(p["remote_host"]):
        h.update(state="paused", error=f"paused: the app doesn't contact {p['remote_host']} until you resume it")
    link = h["error"] if h["state"] in ("no-link", "paused") else \
        f"{p['remote_host']} unreachable ({h['error']}); next try in {max(1, int(left // 60))} min" if h["state"] == "down" and left > 0 else None
    return {"host": p["remote_host"], "path": p["remote_path"], "synced_at": synced_at(p), "error": link or st.get("error"),
            "link": h["state"]}


def remote_sync_loop():
    while True:
        for p in load_config()["projects"].values():
            if p.get("remote_host"):
                try:
                    sync_remote(p)
                except Exception:      # one unreachable host must not stop the others
                    pass
        time.sleep(REMOTE_EVERY)


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
            "cwd": a.get("cwd"), "transcript": bool((a.get("agent_session") or {}).get("value")), "safeguard": guard_of(a),
            "session_id": (a.get("agent_session") or {}).get("value"),
            "turn_end": rg_chat.last_turn_end(transcript_of(a)) if transcript_of(a) else None,
            "loop": rg_chat.loop_state(transcript_of(a)) if transcript_of(a) else None,
            "api_error": rg_chat.last_api_error(transcript_of(a)) if transcript_of(a) else None,
            "model": rg_chat.last_model(transcript_of(a)) if transcript_of(a) else None,
            "effort": rg_chat.last_effort(transcript_of(a)) if transcript_of(a) else None,
            **btw_fields(a["pane_id"])}


def btw_fields(app_pane):
    rec = btw_of(app_pane)
    return {"role": "btw", "btw_of": rec["label"], "btw_parent": rec["parent"]} if rec else {}


def transcript_of(a):
    if a.get("agent") != "claude":
        return None
    return rg_chat.transcript_path((a.get("agent_session") or {}).get("value"))


def guard_of(a):
    """The agent's latest Opus-safeguard event that still matters, if any (Claude sessions only)."""
    path = transcript_of(a)
    return rg_chat.last_safeguard(path) if path else None


def project_agents(p):
    """herdr agents whose folder is the project, each with its role (roster line, else tab label)."""
    snap, err = herdr_snapshot()
    if not snap:
        return [], err
    ros = roster(p)
    others = [q["path"] for q in load_config()["projects"].values() if q["name"] != p["name"]]

    def mine(a):
        # its folder is the project's, or the project's roster names its pane (a desk started from a parent folder),
        # as long as it isn't sitting inside another registered project
        if in_folder(a.get("cwd"), p["path"]):
            return True
        return a["pane_id"] in ros and not any(in_folder(a.get("cwd"), o) for o in others)
    out = [agent_view(a, snap, ros) for a in snap.get("agents", []) if mine(a)]
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
            named = re.search(rf"(^|/){re.escape(folder)}(/|$|\s)", a["map"]) or (mid and re.search(rf"\b{re.escape(mid)}\b(?!-)", a["map"].lower()))
            if named or (mid and re.search(rf"\b{re.escape(mid)}\b(?!-)", a["tab_label"].lower())):
                found.setdefault(folder, a["pane"])
                a.setdefault("drives", m.get("id"))
                a.setdefault("drives_folder", folder)
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


def ticket_view(k, by_id, root):
    blockers = k.get("blocked_by") or []
    blockers = [blockers] if isinstance(blockers, str) else blockers
    jobs = k.get("jobs") or []
    return {"id": k.get("id"), "title": k.get("title"), "type": tracker.type_of(k), "status": tracker.status_of(k),
            "status_text": k.get("status"), "blocked_by": blockers, "superseded_by": k.get("superseded_by"),
            "path": k["_path"], "folder": os.path.basename(os.path.dirname(k["_path"])),
            "answered": k["_answered"], "unblocked": all(tracker.blocker_met(b, by_id) for b in blockers),
            "holder": tracker.holder(k), "jobs": jobs if isinstance(jobs, list) else [jobs],
            "cost_cap": k.get("cost_cap"), "verdict": k.get("verdict"), "updated": k.get("updated"),
            "mtime": mtime(os.path.join(root, k["_path"]))}


def mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def project_state(p, with_agents=True):
    if p.get("remote_host") and not synced_at(p):
        st = _remote.get(p["name"]) or {}
        raise ApiError(503, f"{p['name']} is on {p['remote_host']}: {st.get('error') or 'mirroring its records (first sync)…'}")
    if p.get("remote_host") and not os.path.exists(os.path.join(p["path"], "CLAUDE.md")) and not glob.glob(os.path.join(p["path"], "*", "*", "*.md")):
        raise ApiError(502, f"{p['name']} is on {p['remote_host']}: {(_remote.get(p['name']) or {}).get('error') or 'not mirrored yet'}")
    if not os.path.isdir(p["path"]):
        raise ApiError(404, f"folder not found: {p['path']}")
    maps = tracker.load(p["path"])
    problems, frontier = tracker.analyse(maps) if maps else ([], {})
    by_id = {k.get("id"): k for m in maps for k in m["_archived"]}
    by_id.update({k.get("id"): k for m in maps for k in m["_tickets"]})
    agents, herdr_err = (remote_sessions(p), None) if p.get("remote_host") else project_agents(p) if with_agents else ([], None)
    driven = live_driver_maps(agents, maps)
    mark_workers(agents, maps, driven)
    codex = mark_codex(p, agents, maps)
    out_maps, waiting = [], []
    for m in maps:
        folder = os.path.basename(os.path.dirname(m["_path"]))
        _, body = tracker.parse_front_matter(os.path.join(p["path"], m["_path"]))
        tickets = [ticket_view(k, by_id, p["path"]) for k in m["_tickets"]]
        fr = {k.get("id") for k in frontier.get(m.get("id")) or []}
        for t in tickets:
            t["frontier"] = t["id"] in fr
            t["waiting"] = t["type"] in tracker.HITL and t["status"] not in tracker.CLOSED | tracker.HUMAN_ONLY   # held: parked by the human
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
                         "tickets": tickets, "fog": fog(body), "counts": counts,
                         "driven": folder in driven, "driver": driven.get(folder), "holder": tracker.holder(m),
                         "mtime": mtime(os.path.join(p["path"], m["_path"]))})
    waiting += [{"kind": "agent", "pane": a["pane"], "role": a["role"], "label": a["tab_label"],
                 "text": f"{a['role'] or a['agent']} ({a['tab_label'] or a['pane']}) is waiting at a prompt"}
                for a in agents if a["status"] == "blocked"]
    team = os.path.exists(os.path.join(p["path"], "scratch", "agents", "roster.md")) or any(a["role"] in ("desk", "driver") for a in agents)
    return {"name": p["name"], "path": p["path"], "server": p.get("server"), "server_root": p.get("server_root"), "team": team,
            "server_maps": p["server_maps"], "shared": p["shared"], "maps": out_maps, "waiting": waiting,
            "problems": problems, "agents": agents, "herdr_error": herdr_err, "changes": changes_since(p, out_maps), "codex": codex,
            "keychain": keychain_has(), "dry_run": ARGS.dry_run, "remote": remote_info(p) if p.get("remote_host") else None,
            "muted": p["muted"]}


def projects_summary():
    cfg = load_config()
    out = []
    for name, p in cfg["projects"].items():
        try:
            s = project_state(p)
            states = {f"map:{m['id']}": [m["status"], m["title"], m["folder"], None] for m in s["maps"]}
            states.update({t["id"]: [t["status"], t["title"], m["folder"], t["folder"]] for m in s["maps"] for t in m["tickets"]})
            out.append({"name": name, "ok": True, "path": p["path"], "waiting": s["waiting"], "agents": s["agents"], "states": states,
                        "open_maps": sum(m["status"] != "closed" for m in s["maps"]),
                        "running": sum(t["status"] in ("running", "claimed") for m in s["maps"] for t in m["tickets"]),
                        "changes": len(s["changes"]["items"]), "server": p.get("server"), "remote": s["remote"], "muted": p["muted"]})
        except Exception as e:  # one broken project must not hide the others
            out.append({"name": name, "ok": False, "error": str(e), "waiting": [], "agents": [],
                        "remote": remote_info(p) if p.get("remote_host") else None})
    registered = {os.path.realpath(p["path"]) for p in cfg["projects"].values()}
    found = []
    for root in cfg.get("roots", []):
        for d in sorted(glob.glob(os.path.join(os.path.expanduser(root), "*"))):
            if os.path.realpath(d) in registered or not os.path.isdir(d):
                continue
            if glob.glob(os.path.join(d, "maps", "*", "map.md")):
                found.append({"name": os.path.basename(d), "path": d})
    snap, err = herdr_snapshot()
    others = []
    if snap:
        for a in snap.get("agents", []):
            claimed = {pane for q in cfg["projects"].values() if not q.get("remote_host") for pane in roster(q)}
            if not any(in_folder(a.get("cwd"), p["path"]) for p in cfg["projects"].values()) and a["pane_id"] not in claimed \
                    and not is_asker(a):
                others.append(agent_view(a, snap, {}))
    return {"projects": out, "unregistered": found, "config": CONFIG, "other_agents": others, "herdr_error": err,
            "dry_run": ARGS.dry_run, "version": VERSION, "moshi_mode": moshi_mode(), "asks": open_asks(), "roots": cfg.get("roots", [])}


# ---------- questions on the phone: Moshi mode (tools/local/ask-human.py, where installed, asks them; the app lists the open ones) ----------

ASK_DIR = os.environ.get("ASK_HUMAN_DIR") or os.path.expanduser("~/.config/research-harness")   # env: tests


def moshi_mode(value=None):
    path = os.path.join(ASK_DIR, "ask.json")
    if value is not None:
        os.makedirs(ASK_DIR, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"moshi": bool(value)}, f)
    try:
        with open(path) as f:
            return bool(json.load(f).get("moshi"))
    except (OSError, ValueError):
        return False


def is_asker(a):
    """A helper session of ask-human (it holds a question on the phone)."""
    return in_folder(a.get("cwd"), os.path.join(ASK_DIR, "asker"))


def open_asks():
    """Questions on the phone with no outcome yet whose waiter is still alive, oldest first."""
    asks = {}
    try:
        with open(os.path.join(ASK_DIR, "asks.jsonl")) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("state") == "asked":
                    asks[r.get("id")] = r
                elif r.get("state") == "posted" and r.get("id") in asks:     # its helper session is up
                    asks[r["id"]].update(helper=r.get("helper"), tab=r.get("tab"))
                else:
                    asks.pop(r.get("id"), None)
    except OSError:
        return []
    out = []
    for r in asks.values():
        try:
            os.kill(int(r["pid"]), 0)
        except (OSError, KeyError, TypeError, ValueError):
            continue
        out.append({k: r.get(k) for k in ("id", "question", "options", "pane", "label", "t", "pid", "tab")})
    return out


def answer_ask(b):
    """Answer a phone question from the app: stop its waiter, close its helper session, type the answer into the pane."""
    rec = next((a for a in open_asks() if a["id"] == b.get("id")), None)
    if not rec:
        raise ApiError(404, "That question is no longer open (answered on the phone, or its session ended).")
    ans = b.get("answer")
    if ans not in rec["options"]:
        raise ApiError(400, "Not one of its options.")
    try:
        os.killpg(int(rec["pid"]), signal.SIGTERM)
    except OSError:
        pass
    if rec.get("tab"):
        try:
            herdr("tab", "close", rec["tab"], timeout=15)
        except HerdrError:
            pass
    msg = f"Answer from the human (app): {ans} (to: {rec['question']})"
    try:
        herdr("agent", "prompt", rec["pane"], msg, timeout=30)
        delivered = True
    except HerdrError:
        delivered = False
    with open(os.path.join(ASK_DIR, "asks.jsonl"), "a") as f:
        f.write(json.dumps({"id": rec["id"], "state": "answered", "answer": ans,
                            "via": "app", "delivered": delivered, "t": time.time()}) + "\n")
    if not delivered:
        raise ApiError(502, f"Couldn't type the answer into {rec['pane']} (the session may have ended).")
    return {"ok": True}


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


def new_project(b):
    """Make a new project's folder under a parent (a projects root) and register it; research-init then sets it up."""
    name, parent = b.get("name") or "", (b.get("parent") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        raise ApiError(400, "Name: letters, digits, - and _ (e.g. prot-design)")
    if not os.path.isdir(os.path.expanduser(parent)):
        raise ApiError(400, f"no folder {parent}")
    path = os.path.join(parent, name)
    full = os.path.expanduser(path)
    if os.path.exists(full) and (not os.path.isdir(full) or os.listdir(full)):
        raise ApiError(400, f"{path} already exists and is not empty: use Add an existing folder")
    if name in load_config()["projects"]:
        raise ApiError(400, f"`{name}` is already registered")
    os.makedirs(full, exist_ok=True)
    add_project({"name": name, "path": path, "server": b.get("server"), "server_root": b.get("server_root"),
                 "server_maps": "maps", "shared": ["common"]})
    return {"ok": True, "name": name, "path": path}


def set_inbox(b):
    """Mute or unmute a project's Inbox items: `inbox = false` in its [projects.<name>] block (or the line removed)."""
    name = b.get("project")
    project(name)
    lines = open(CONFIG).read().split("\n")
    start = next((i for i, l in enumerate(lines) if l.strip() == f"[projects.{name}]"), None)
    if start is None:
        raise ApiError(400, f"no [projects.{name}] block in {CONFIG}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
    body = [l for l in lines[start + 1:end] if not re.match(r"\s*inbox\s*=", l)]
    if b.get("muted"):
        body.insert(0, "inbox = false   # muted in Research Desk: its tickets stay out of the Inbox and alerts")
    save_config("\n".join(lines[:start + 1] + body + lines[end:]))
    return {"ok": True, "muted": bool(b.get("muted"))}


# ---------- btw: a side chat forked from a session, read-only, deleted when closed ----------

BTW_FILE = os.path.expanduser("~/.config/research-gui/btw.json")
BTW_DENY = ("Bash,Edit,Write,NotebookEdit,SendMessage,ScheduleWakeup,CronCreate,CronDelete,Agent,Skill,Monitor,TaskStop,"
            "RemoteTrigger,PushNotification,Workflow,Artifact,ArtifactData,ArtifactComments,EnterWorktree,ExitWorktree,DesignSync")
BTW_NOTE = ("This is a side conversation (a 'btw') that the human forked from the session above to talk something over. "
            "Nothing said here reaches the team or changes the project: you can read files and search, but you cannot edit, "
            "run commands, message other sessions or schedule anything, and you should not try. Just talk with the human. "
            "This chat is deleted when they close it.")
SID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def btw_load():
    try:
        with open(BTW_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def btw_save(d):
    os.makedirs(os.path.dirname(BTW_FILE), exist_ok=True)
    with open(BTW_FILE + ".tmp", "w") as f:
        json.dump(d, f, indent=1)
    os.replace(BTW_FILE + ".tmp", BTW_FILE)


def btw_runner(pane):
    """(herdr command, host or None, the session's herdr record, app pane prefix) for a local or remote session."""
    if (pane or "").startswith("remote:"):
        _, name, rpane = pane.split(":", 2)
        p = project(name)
        host = p["remote_host"]
        refresh_remote_herdr(host, wait=20, force=True)
        a = next((x for x in (_rsnap.get(host) or {}).get("agents") or [] if x["pane_id"] == rpane), None)
        return (lambda *args, timeout=60: remote_herdr(host, *args, timeout=timeout)), host, a, f"remote:{name}:"
    snap, err = herdr_snapshot()
    a = next((x for x in (snap or {}).get("agents", []) if x["pane_id"] == pane), None)
    return (lambda *args, timeout=60: herdr(*args, timeout=timeout)), None, a, ""


def btw_start(b):
    """Fork a Claude session into a new tab beside it: same conversation so far, new session id, tools that change
    anything denied, a system note that this is a side chat. Returns the app pane of the fork."""
    pane = b.get("pane") or ""
    run_herdr, host, a, prefix = btw_runner(pane)
    sid = ((a or {}).get("agent_session") or {}).get("value")
    if not a or a.get("agent") != "claude" or not SID.fullmatch(sid or ""):
        raise ApiError(400, "Only a live Claude Code session can be forked")
    label = (b.get("label") or a.get("name") or a.get("terminal_title_stripped") or "session")[:40]
    key = uuid.uuid4().hex[:6]
    tab = run_herdr("tab", "create", "--workspace", a["workspace_id"], "--cwd", a.get("cwd") or "~", "--label", f"btw {label}"[:48], "--no-focus")
    new, tab_id = tab["root_pane"]["pane_id"], tab["tab"]["tab_id"]
    for _ in range(40):                         # the tab's shell takes a moment
        try:
            run_herdr("agent", "start", f"btw-{key}", "--kind", "claude", "--pane", new, "--timeout", "120000", "--",
                      "--resume", sid, "--fork-session", "--disallowedTools", BTW_DENY, "--append-system-prompt", BTW_NOTE,
                      "-n", f"btw · {label}", timeout=150)
            break
        except (HerdrError, ApiError) as e:
            msg = str(e)
            if "busy" in msg or "not an available shell" in msg:
                time.sleep(1)
                continue
            if "not_ready" in msg or "not ready" in msg:   # stopped at a startup question: answer it in the chat
                break
            run_herdr("tab", "close", tab_id)
            raise
    reg = btw_load()
    reg[prefix + new] = {"host": host, "pane": new, "tab": tab_id, "parent": pane, "parent_sid": sid, "label": label,
                         "at": time.time()}
    btw_save(reg)
    if host:
        refresh_remote_herdr(host, wait=20, force=True)
    return {"pane": prefix + new}


def btw_close(b):
    """Close a btw fork and delete its conversation: the session's files there, the app's copy and search index."""
    reg = btw_load()
    rec = reg.get(b.get("pane") or "")
    if not rec:
        raise ApiError(404, "not a btw chat")
    run_herdr, host, a, _ = btw_runner(b["pane"])
    sid = ((a or {}).get("agent_session") or {}).get("value") or rec.get("sid")
    try:
        run_herdr("tab", "close", rec["tab"], timeout=20)
    except (HerdrError, ApiError):
        pass                                     # already closed
    deleted = False
    if SID.fullmatch(sid or "") and sid != rec["parent_sid"]:   # never the session it was forked from
        time.sleep(1.5)                          # let Claude Code finish writing as it exits
        paths = [f"projects/*/{sid}.jsonl", f"projects/*/{sid}", f"file-history/{sid}", f"session-env/{sid}", f"todos/{sid}*"]
        if host:
            script = (f"cd ~/.claude && rm -rf {' '.join(paths)}; "
                      f"[ -f history.jsonl ] && grep -v '\"sessionId\":\"{sid}\"' history.jsonl > history.jsonl.btw; "
                      f"[ -f history.jsonl.btw ] && cat history.jsonl.btw > history.jsonl && rm -f history.jsonl.btw")
            try:
                remote_ssh(host, script, wait=20, force=True)
            except ApiError as e:
                raise ApiError(e.code, f"closed it, but couldn't delete its conversation on {host}: {e}")
            for f in glob.glob(os.path.join(REMOTE_SESSIONS, "*", "*", f"{sid}.jsonl")):
                os.remove(f)
        else:
            root = os.path.expanduser("~/.claude")
            for pat in paths:
                for f in glob.glob(os.path.join(root, pat)):
                    if os.path.isfile(f) and f.endswith(".jsonl"):
                        ix = rg_chat.index_path(f)
                        for x in (ix, ix + ".pos"):
                            if os.path.exists(x):
                                os.remove(x)
                    shutil.rmtree(f) if os.path.isdir(f) else os.remove(f)
            hist = os.path.join(root, "history.jsonl")
            if os.path.exists(hist):              # the prompts typed into it (up-arrow history)
                with open(hist) as f:
                    lines = f.readlines()
                keep = [l for l in lines if f'"sessionId":"{sid}"' not in l]
                if len(keep) != len(lines):
                    with open(hist, "r+") as f:   # rewrite in place, then keep anything appended meanwhile
                        rest = f.read()[sum(map(len, lines)):]
                        f.seek(0)
                        f.write("".join(keep) + rest)
                        f.truncate()
        deleted = True
    reg.pop(b["pane"], None)
    btw_save(reg)
    if host:
        refresh_remote_herdr(host, wait=10, force=True)
    return {"ok": True, "deleted": deleted, "parent": rec["parent"]}


def btw_of(app_pane):
    """The btw record of an app pane (a fork), if any."""
    return btw_load().get(app_pane)


# ---------- pasted files: the message box is text, so a pasted image becomes a file and its path is typed ----------

PASTE_DIR = os.path.expanduser("~/Library/Caches/research-gui/paste")
PASTE_EXT = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp", "application/pdf": ".pdf"}


def paste_file(b):
    """Save pasted bytes (a screenshot, an image copied from a page) and return a path the agent can read: on this Mac,
    or, for a remote project's session, uploaded to ~/.cache/research-desk-paste on its host."""
    try:
        data = base64.b64decode(b.get("b64") or "", validate=True)
    except ValueError:
        raise ApiError(400, "bad file data")
    if not data or len(data) > 25 << 20:
        raise ApiError(413, "a pasted file must be 1 B to 25 MB")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(b.get("name") or "")).strip("._") or "pasted"
    if "." not in name:
        name += PASTE_EXT.get(b.get("type") or "", "")
    fname = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}-{name}"
    os.makedirs(PASTE_DIR, exist_ok=True)
    for old in glob.glob(os.path.join(PASTE_DIR, "*")):            # a week is plenty for a pasted screenshot
        if time.time() - os.path.getmtime(old) > 7 * 86400:
            os.remove(old)
    local = os.path.join(PASTE_DIR, fname)
    with open(local, "wb") as f:
        f.write(data)
    pane = b.get("pane") or ""
    if not pane.startswith("remote:"):
        return {"path": local}
    host = project(pane.split(":")[1])["remote_host"]
    try:
        code, out, err = remote_ssh(host, "mkdir -p ~/.cache/research-desk-paste && cd ~/.cache/research-desk-paste && pwd",
                                    wait=20, force=True)
    except ApiError as e:
        raise ApiError(e.code, f"couldn't upload it to {host}: {e}")
    rdir = out.decode(errors="replace").strip()
    if code != 0 or not rdir.startswith("/"):
        raise ApiError(502, f"couldn't reach {host} to upload it: {err.strip()[:150]}")
    code, _, err = host_call(host, ["rsync", "-t", "-e", SSH_BATCH, local, f"{host}:{rdir}/"], RSYNC_LIMIT, wait=20, force=True)
    if code != 0:
        raise ApiError(502, f"upload to {host} failed: {err.strip()[:150]}")
    return {"path": f"{rdir}/{fname}"}


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


def gpu_pools():
    """Pool name -> hosts to watch: [gpu_pools] in the projects file (shared clusters: every node, since your jobs can
    land anywhere), plus gpu_hosts and each project's server under "Other" if not already listed."""
    cfg = load_config()
    pools = {k: list(v) for k, v in (cfg.get("gpu_pools") or {}).items() if isinstance(v, list)}
    listed = {h for hs in pools.values() for h in hs}
    extra = [h for h in (cfg.get("gpu_hosts") or []) + [p.get("server") for p in cfg["projects"].values()]
             if h and h not in listed]
    if extra:
        pools.setdefault("Other", [])
        pools["Other"] += [h for h in dict.fromkeys(extra)]
    return pools


def gpu_hosts():
    return [h for hs in gpu_pools().values() for h in hs]


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


# ---------- search across a project's conversations ----------

_codex_cwd = {}


def project_transcripts(p):
    """Every conversation of the project: Claude Code sessions started in its folder (or below it), sessions its
    roster names that started elsewhere (live ones), and Codex rollouts whose working folder is inside it."""
    base = os.path.expanduser("~/.claude/projects")
    enc = re.sub(r"[^A-Za-z0-9-]", "-", p["path"])
    files = set()
    for d in glob.glob(os.path.join(base, enc + "*")):
        if os.path.basename(d) == enc or os.path.basename(d).startswith(enc + "-"):
            files.update(glob.glob(os.path.join(d, "*.jsonl")))
    agents, _ = project_agents(p)
    for a in agents:
        path = rg_chat.transcript_path(a.get("session_id"), a.get("agent")) if a.get("session_id") else None
        if path:
            files.add(path)
    cutoff = time.time() - 90 * 86400
    for f in glob.glob(os.path.expanduser("~/.codex/sessions/*/*/*/rollout-*.jsonl")):
        if os.path.getmtime(f) < cutoff:
            continue
        if f not in _codex_cwd:
            try:
                with open(f) as fh:
                    _codex_cwd[f] = (json.loads(fh.readline()).get("payload") or {}).get("cwd") or ""
            except (OSError, ValueError):
                _codex_cwd[f] = ""
        if _codex_cwd[f] and in_folder(_codex_cwd[f], p["path"]):
            files.add(f)
    return sorted(files, key=lambda f: -os.path.getmtime(f))


def snippet(text, term, width=150):
    i = text.lower().find(term)
    a = max(0, i - width // 2)
    return ("…" if a else "") + text[a:a + width].replace("\n", " ") + ("…" if a + width < len(text) else "")


def search(p, q):
    terms = [t for t in q.lower().split() if t][:6]
    if not terms or len(q) > 200:
        raise ApiError(400, "type a few words to search for")
    pats = [re.compile(re.escape(t.encode()), re.I) for t in terms]
    t0, files = time.time(), project_transcripts(p)
    live = {a["session_id"]: a for a in project_agents(p)[0] if a.get("session_id")}
    hits, matched = [], set()
    for f in files:                                  # message text only (rg_chat's index), updated by appended bytes
        if time.time() - t0 > 20:
            break
        ix = rg_chat.update_index(f)
        if not ix:
            continue
        codex, per = "/.codex/" in f, 0
        with open(ix, "rb") as fh:
            for line in fh:
                if not all(rx.search(line) for rx in pats):
                    continue
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                if not all(t in m["x"].lower() for t in terms):
                    continue
                matched.add(f)
                hits.append({"file": f, "session": os.path.basename(f)[:-6].split("-", 6)[-1] if codex else os.path.basename(f)[:-6],
                             "uuid": m["u"], "ts": m["t"], "role": m["k"], "who": m["w"],
                             "snippet": snippet(m["x"], terms[0]), "codex": codex})
                per += 1
                if per >= 15:
                    break
    hits.sort(key=lambda h: h["ts"] or "", reverse=True)
    hits = hits[:150]
    titles = {}
    for h in hits:
        if h["file"] not in titles:
            titles[h["file"]] = rg_chat.title_of(h["file"]) if not h["codex"] else "Codex session"
        h["title"] = titles[h["file"]]
        a = live.get(h["session"])
        h["live_pane"] = a["pane"] if a else None
        h["live_label"] = (a.get("role") or a.get("agent")) if a else None
    for h in hits:
        h.pop("file")
    return {"hits": hits, "files": len(files), "matched_files": len(matched),
            "ms": int((time.time() - t0) * 1000)}


def archive(session, around):
    """One saved conversation around a message (a search hit), read-only."""
    if not re.fullmatch(r"[0-9a-fA-F-]{8,64}", session or ""):
        raise ApiError(400, "bad session id")
    path = rg_chat.transcript_path(session) or rg_chat.transcript_path(session, "codex")
    if not path:
        raise ApiError(404, "no saved conversation with that id")
    items, focus = rg_chat.read_around(path, around or "")
    return {"pane": "session:" + session, "agent": "codex" if "/.codex/" in path else "claude", "status": "archive",
            "title": rg_chat.title_of(path) or "saved conversation", "session": session, "items": items, "offset": None,
            "focus": focus, "cut": True}


# ---------- raw file bytes (PDFs and images open in the viewer) ----------

RAW_TYPES = {".pdf": "application/pdf", **IMAGE_EXT}
RAW_CAP = 60 << 20


def raw_file(p, side, rel):
    ext = os.path.splitext(rel)[1].lower()
    if ext not in RAW_TYPES:
        raise ApiError(400, "only PDFs and images are served raw")
    if side == "local":
        path = inside(p, rel)
        if os.path.getsize(path) > RAW_CAP:
            raise ApiError(413, "file too large to preview")
        with open(path, "rb") as f:
            return f.read(), RAW_TYPES[ext]
    f = remote_path(p, rel)
    size = ssh(p["server"], f"stat -L -c %s -- {f} 2>/dev/null || echo 0").decode().strip()
    if not size.isdigit() or int(size) == 0:
        raise ApiError(404, f"no file {rel} on {p['server']}")
    if int(size) > RAW_CAP:
        raise ApiError(413, "file too large to preview")
    return cached((p["server"], "raw", p["server_root"], rel), False, lambda: ssh(p["server"], f"cat -- {f}", timeout=120)), RAW_TYPES[ext]


# ---------- skills (for the composer's / menu) ----------

# Claude Code's own commands. Many open a menu on the terminal screen rather than writing to the conversation; the chat
# shows the live screen after any of them is sent.
BUILTIN = [("btw", "Ask a quick side question; the answer is shown, not kept in the conversation"),
           ("rewind", "Go back to an earlier point in the conversation (and code)"), ("clear", "Start a fresh conversation"),
           ("compact", "Summarize the conversation to free context"), ("resume", "Resume an earlier conversation"),
           ("model", "Switch the model"), ("effort", "Set the reasoning effort"), ("context", "Show context usage"),
           ("cost", "Show this session's cost and duration"), ("usage", "Show plan usage limits"),
           ("status", "Show version, model, account and connectivity"), ("config", "Open settings"),
           ("permissions", "View or change tool permissions"), ("memory", "Edit memory files"),
           ("agents", "Manage subagents"), ("mcp", "Manage MCP servers"), ("hooks", "Manage hooks"),
           ("plugin", "Manage plugins"), ("todos", "Show the current todo list"), ("export", "Export the conversation"),
           ("add-dir", "Add a working directory"), ("init", "Write a CLAUDE.md for this project"),
           ("doctor", "Check the installation"), ("loop", "Run a prompt or command on an interval"),
           ("help", "List commands")]


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

def chat(pane, after, session, want_screen=False, around=None):
    if (pane or "").startswith("session:"):
        return archive(pane.split(":", 1)[1], around)
    if (pane or "").startswith("remote:"):          # a session on a remote project's host: its mirrored conversation
        _, name, rpane = pane.split(":", 2)
        p = project(name)
        want(p["remote_host"])
        a = next((x for x in remote_sessions(p) if x["pane"] == pane), None)
        sid = (a or {}).get("session_id") or rpane
        path = pull_session(p, sid) or rg_chat.transcript_path(sid)
        rec = btw_of(pane)
        if not path and rec:                        # a btw fork before its first message: what it starts from
            sid = rec["parent_sid"] + "#btw"
            path = pull_session(p, rec["parent_sid"]) or rg_chat.transcript_path(rec["parent_sid"])
        if not path:
            raise ApiError(404, f"no mirrored conversation {sid}")
        items, offset, cut, reset = rg_chat.read(path, after if session == sid else None)
        return {"pane": pane, "agent": "claude", "status": a["status"] if a else "idle", "remote": p["remote_host"],
                "title": (a or {}).get("title") or "", "session": sid, "items": items, "offset": offset, "cut": cut,
                "reset": reset, "transcript": path}
    try:
        a, snap = live_agent(pane)
    except ApiError as e:
        # the agent's tab closed (a driver ends finished workers): its transcript stays readable
        path = rg_chat.transcript_path(session) if e.code == 404 and session else None
        if not path:
            raise
        items, offset, cut, reset = rg_chat.read(path, after)
        return {"pane": pane, "agent": "claude", "status": "ended", "title": "this session has ended", "session": session,
                "items": items, "offset": offset, "cut": cut, "reset": reset, "transcript": path}
    sess = (a.get("agent_session") or {}).get("value")
    out = {"pane": pane, "agent": a.get("agent"), "status": a.get("agent_status"),
           "title": a.get("terminal_title_stripped"), "session": sess, "cwd": a.get("cwd")}
    path = rg_chat.transcript_path(sess, a.get("agent")) if a.get("agent") in ("claude", "codex") else None
    if path:
        if session != sess:
            after = None
        items, offset, cut, reset = rg_chat.read(path, after)
        name_role(items, a.get("cwd"))
        out.update({"items": items, "offset": offset, "cut": cut, "reset": reset, "transcript": path})
    elif (rec := btw_of(pane)) and (ppath := rg_chat.transcript_path(rec["parent_sid"])):
        # a btw fork writes its own conversation only at its first message: until then show what it starts from
        key = rec["parent_sid"] + "#btw"
        items, offset, cut, reset = rg_chat.read(ppath, after if session == key else None)
        name_role(items, a.get("cwd"))
        out.update({"items": items, "offset": offset, "cut": cut, "reset": reset, "transcript": ppath, "session": key})
    else:
        out["items"], out["offset"] = [], 0
        out["fallback"] = screen(pane, "recent-unwrapped", 300)
    if a.get("agent_status") == "blocked" or want_screen:      # a prompt, or a menu a /command opened
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
            m = re.search(r"\b([MT]\d+)\b", r["map"] or "")
            it["role"] = r["role"] + (f" · {m.group(1)}" if m else "")


def screen(pane, source, lines=None):
    args = ["agent", "read", pane, "--source", source] + (["--lines", str(lines)] if lines else [])
    code, out, err = run(["herdr", *args], timeout=15)
    text = out.decode(errors="replace") if code == 0 else f"(could not read the screen: {err.strip()})"
    return "\n".join(l.rstrip() for l in text.splitlines()).strip("\n")


def input_box(text):
    """What sits in Claude Code's input box (the last box between ─── rules, starting at ❯), and its line count."""
    lines = text.splitlines()
    rules = [i for i, l in enumerate(lines) if l.strip() and set(l.strip()) <= {"─"}]
    if len(rules) < 2:
        return "", 0
    box = lines[rules[-2] + 1:rules[-1]]
    if not box or not box[0].lstrip().startswith("❯"):
        return "", 0
    typed = "\n".join([box[0].split("❯", 1)[1]] + box[1:]).strip()
    if re.fullmatch(r'Try ".*"', typed):          # the dimmed suggestion an empty box shows
        typed = ""
    return typed, len(box)


SENT = {}   # pane -> when the human last sent it something from the app


def chat_send(b):
    pane, text = b.get("pane"), (b.get("text") or "").strip()
    if not text:
        raise ApiError(400, "empty message")
    if (pane or "").startswith("remote:"):
        return remote_send(b)
    a, _ = live_agent(pane)
    if a.get("agent_status") == "blocked":
        raise ApiError(409, "the agent is waiting at a prompt: answer it first")
    cleared = ""
    if a.get("agent") == "claude":
        cleared, n = input_box(screen(pane, "visible"))
        if cleared:                                 # left over (a rewind restores the removed message there): it would
            for _ in range(n):                      # be sent together with this one; Ctrl+U clears a line, ⌫ joins lines
                herdr("agent", "send-keys", pane, "ctrl+u", "backspace", timeout=15)
    try:
        herdr("agent", "prompt", pane, text, timeout=30)
    except HerdrError as e:
        raise ApiError(409 if e.code == "agent_blocked" else 502, str(e))
    _snap["t"] = 0
    SENT[pane] = time.time()
    return {"ok": True, "cleared": cleared}


def chat_keys(b):
    keys = b.get("keys") or []
    if not keys or any(k not in KEYS for k in keys):
        raise ApiError(400, f"keys must be among {sorted(KEYS)}")
    live_agent(b.get("pane"))
    herdr("agent", "send-keys", b["pane"], *keys, timeout=15)
    if any(k == "enter" or k.isdigit() for k in keys):
        SENT[b["pane"]] = time.time()
    _snap["t"] = 0
    return {"ok": True}


def chat_text(b):
    a, _ = live_agent(b.get("pane"))
    text = b.get("text") or ""
    if a.get("agent_status") != "blocked" and not b.get("menu"):
        raise ApiError(409, "typing into the screen is only for answering a prompt or a menu; send a message instead")
    if len(text) > 2000 or re.search(r"[\x00-\x1f\x7f]", text):
        raise ApiError(400, "answers are one line of plain text (at most 2000 characters)")
    herdr("pane", "send-text", b["pane"], text, timeout=15)
    if b.get("enter"):
        herdr("agent", "send-keys", b["pane"], "enter", timeout=15)
        SENT[b["pane"]] = time.time()
    _snap["t"] = 0
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


CODEX_TEAM_ARGS = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "codex-team.args")


def codex_team_args(effort):
    """The flags every Codex team session starts with (tools/codex-team.args) plus a reasoning effort."""
    with open(CODEX_TEAM_ARGS) as f:
        args = [os.path.expanduser(l.strip()) for l in f if l.strip() and not l.lstrip().startswith("#")]
    return args + ["-c", f'model_reasoning_effort="{effort}"']


def team_agent(s):
    """The agent the project's live team runs on (its desk or a driver), else None."""
    return next((a["agent"] for a in s["agents"] if a["role"] in ("desk", "driver") and a.get("agent") in ("claude", "codex")),
                None)


def watch_live(p):
    """A team-watch is running for this project (its lock names a live pid)."""
    try:
        with open(os.path.join(p["path"], "scratch", "agents", "team-watch.pid")) as f:
            os.kill(int(f.read().strip()), 0)
        return True
    except (OSError, ValueError):
        return False


def team_plan(p, only_map=None, agent=None):
    """The herdr steps to start a desk and drivers, skipping roles that are already live. A team is all Claude Code or
    all Codex: a live team keeps its agent. A Codex team also gets a watch tab (team-watch), its drivers' schedule."""
    if p.get("remote_host"):
        raise ApiError(400, f"{p['name']} runs on {p['remote_host']}: start sessions there (Terminal on {p['remote_host']}, on its page)")
    s = project_state(p)
    claude_args, _, role_env = role_settings(p)
    live = team_agent(s)
    if agent not in (None, "claude", "codex"):
        raise ApiError(400, "agent is claude or codex")
    if live and agent and agent != live:
        raise ApiError(409, f"this project's team runs on {live}: stop it before starting a {agent} team")
    kind = agent or live or "claude"
    args = codex_team_args("medium") if kind == "codex" else [*claude_args, "--model", "claude-opus-5-5", "--effort", "xhigh"]   # pinned: a saved /model or /effort never reaches the team

    def role_prompt(role):
        return f"Read ~/.agents/skills/team/SKILL.md and follow it as `team {role}`." if kind == "codex" else f"/team {role}"

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
        steps.append({"role": "driver", "kind": kind, "map": m["id"], "label": f"B driver {m['id']}",
                      "name": agent_name(p, f"driver-{m['id'].lower()}"), "args": args,
                      "prompt": role_prompt(f"driver {m['path'].rsplit('/', 1)[0]}"), "env": role_env.get("driver", {})})
    if only_map is None:
        if any(a["role"] == "desk" for a in s["agents"]):
            notes.append("a desk is already live: skipped")
        else:
            steps.append({"role": "desk", "kind": kind, "label": "A desk", "name": agent_name(p, "desk"),
                          "args": args, "prompt": role_prompt("desk"), "env": role_env.get("desk", {})})
        if not drivers:
            notes.append("no open map that isn't paused: no driver started")
    if kind == "codex" and steps and not watch_live(p):
        steps.append({"role": "watch", "kind": "shell", "label": "watch", "name": agent_name(p, "watch"), "args": [],
                      "prompt": "", "env": {}, "command": "caffeinate -dimsu team-watch"})
    plan = finish_plan(p, ws, steps, notes, s["keychain"])
    plan.update(agent=kind, agent_fixed=bool(live))
    return plan


def session_plan(p, b):
    """One new session in the project's herdr workspace: claude or codex (optionally with a first prompt), or a shell."""
    if p.get("remote_host"):
        raise ApiError(400, f"{p['name']} runs on {p['remote_host']}: start sessions there (Terminal on {p['remote_host']}, on its page)")
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


def alive(pane, wait=8):
    """An agent still runs in the pane a few seconds after its start."""
    time.sleep(wait)
    return any(a.get("pane_id") == pane for a in herdr("agent", "list").get("agents", []))


def start_agent(name, st, pane):
    """herdr agent start, retried while a new tab's shell is still starting (no login export step gives it time)."""
    for attempt in range(10):
        try:
            return herdr("agent", "start", name, "--kind", st["kind"], "--pane", pane, "--timeout", "120000",
                         *(["--", *st["args"]] if st["args"] else []), timeout=150)
        except HerdrError as e:
            if "not an available shell" not in str(e) or attempt == 9:
                raise
            time.sleep(1)


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
                start_agent(name, st, pane)
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
            if not alive(pane):           # an agent can exit during startup (Codex: a daemon or login timeout)
                say(f"{st['label']}: {st['kind']} exited during startup; starting it once more")
                name = unique_name(st["name"])
                start_agent(name, st, pane)
                if st.get("prompt"):
                    herdr("agent", "prompt", name, st["prompt"])
                say(f"{st['label']}: " + ("started" if alive(pane) else "did not start again: see its tab"))
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


# ---------- the notification monitor: state changes become events (rg_notify delivers them) ----------

def label_of(a):
    if a.get("role") == "worker" and a.get("ticket"):
        return f"Worker · {a['ticket']}"
    if a.get("role") == "driver" and a.get("drives"):
        return f"Driver · {a['drives']}"
    if a.get("role"):
        return a["role"].capitalize()
    tab = a.get("tab_label") or ""
    return (a.get("agent") or "agent").capitalize() + (f" · {tab}" if tab and not tab.isdigit() else "")


def monitor_view():
    view = {"agents": {}, "states": {}, "waiting": {}, "projects": set()}
    cfg = load_config()
    for name, p in cfg["projects"].items():
        try:
            s = project_state(p)
        except Exception:
            continue
        if not p["muted"]:
            view["projects"].add(name)                 # muted: its tickets are skipped below (a baseline that never moves)
        for a in s["agents"]:
            view["agents"][a["pane"]] = dict(a, project=name)
        for m in s["maps"]:
            view["states"][(name, "map:" + m["id"])] = (m["status"], m["title"], m["folder"], None)
            for t in m["tickets"]:
                view["states"][(name, t["id"])] = (t["status"], t["title"], m["folder"], t["folder"])
        for w in s["waiting"]:
            if w["kind"] == "ticket":
                view["waiting"][(name, w["id"])] = (w["text"], w["map_folder"], w.get("folder"))
    snap, _ = herdr_snapshot()
    for a in (snap or {}).get("agents", []):
        if a["pane_id"] not in view["agents"] and not is_asker(a):
            view["agents"][a["pane_id"]] = dict(agent_view(a, snap, {}), project=None)
    return view


def diff_events(prev, now):
    emit = rg_notify.emit
    cfg = rg_notify.load()["events"]
    for pane, a in now["agents"].items():
        b = prev["agents"].get(pane)
        if not b:
            continue
        who, proj = label_of(a), a.get("project")
        where = {"project": proj, "pane": pane}
        tail = f" · {proj}" if proj else ""
        if a["status"] == "blocked" and b["status"] != "blocked":
            emit("prompt", f"{who} needs your answer{tail}", a.get("title") or "", **where)
        ended = (a.get("turn_end") and a.get("turn_end") != b.get("turn_end")) or \
            (not a.get("turn_end") and b["status"] == "working" and a["status"] in ("idle", "done"))
        if ended:
            sent = SENT.get(pane)
            end_t = rg_chat_ts(a.get("turn_end")) if a.get("turn_end") else time.time()
            kinds = (["reply"] if sent and end_t > sent else []) + (["desk_reply"] if a.get("role") == "desk" else []) + ["any_reply"]
            if sent and end_t > sent:
                SENT.pop(pane, None)
            kind = next((k for k in kinds if cfg[k]["channels"]), kinds[0])   # one event per reply, the most specific
            emit(kind, f"{who} replied{tail}", a.get("title") or "", **where)
        ls, lb = (a.get("loop") or {}).get("state"), (b.get("loop") or {}).get("state")
        if ls == "missed" and ls != lb:
            emit("loop", f"{who}: its loop missed a pass{tail}", "Restart it from the app", **where)
        e, eb = a.get("api_error"), b.get("api_error")
        if e and (not eb or e.get("ts") != eb.get("ts")):
            emit("api_error", f"{who}: Claude API error{tail}", e.get("text", ""), **where)
        g, gb = a.get("safeguard"), b.get("safeguard")
        if g and (not gb or g.get("ts") != gb.get("ts")):
            emit("safeguard", f"{who}: Opus safeguards{tail}", g.get("text", ""), **where)
    seen = prev.get("projects", set())                # a project's first good look (a remote's first sync) is a baseline
    for key, (text, mf, tf) in now["waiting"].items():
        if key not in prev["waiting"] and key[0] in seen:
            emit("decision", f"Decision for you · {key[0]}", f"{key[1]}: {text}", project=key[0], map=mf, ticket=tf)
    for key, st in now["states"].items():
        if key[0] not in seen:
            continue
        old = prev["states"].get(key)
        if not old or old[0] == st[0]:
            continue
        proj, ident = key
        name = ident.replace("map:", "Map ")
        if st[0] in ("resolved", "closed"):
            emit("result", f"{name} {st[0]} · {proj}", st[1], project=proj, map=st[2], ticket=st[3])
        elif st[0] in ("running", "held", "parked"):
            emit("progress", f"{name} is {st[0]} · {proj}", st[1], project=proj, map=st[2], ticket=st[3])


def rg_chat_ts(iso):
    try:
        return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return time.time()


def monitor():
    prev = None
    while True:
        try:
            now = monitor_view()
            if prev is not None:
                diff_events(prev, now)
            prev = now
        except Exception as e:
            sys.stderr.write(f"monitor: {e}\n")
        time.sleep(5)


# ---------- settings ----------

def config_text():
    text = open(CONFIG).read() if os.path.exists(CONFIG) else open(os.path.join(HERE, "projects.example.toml")).read()
    return {"path": CONFIG, "text": text, "exists": os.path.exists(CONFIG)}


def check_config(cfg):
    """The shape load_config relies on; a project with a server also needs its code folder there."""
    projects = cfg.get("projects", {})
    if not isinstance(projects, dict):
        raise ApiError(400, "[projects] must be a table of projects")
    for name, p in projects.items():
        if not isinstance(p, dict) or not isinstance(p.get("path"), str) or not p["path"].strip():
            raise ApiError(400, f"project `{name}` needs path = \"<folder on this Mac>\"")
        for key in ("server", "server_root", "server_maps"):
            if key in p and not isinstance(p[key], str):
                raise ApiError(400, f"project `{name}`: {key} must be a string")
        if p.get("server") and not p.get("server_root"):
            raise ApiError(400, f"project `{name}` has a server but no server_root (its code folder there)")
        if "shared" in p and not (isinstance(p["shared"], list) and all(isinstance(s, str) for s in p["shared"])):
            raise ApiError(400, f"project `{name}`: shared must be a list of folder names")


def save_config(text):
    try:
        check_config(tomllib.loads(text))
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
    if kind == "tmux":                          # a job's tmux session: validated host and name, no project needed
        check_job(q.get("host"), q.get("session"))
        return (["ssh", "-t", "-o", "ClearAllForwardings=yes", q["host"], f"tmux attach -t {shlex.quote(q['session'])}"],
                os.path.expanduser("~"), b"")
    p = project(q.get("project"))
    if kind == "shell":
        return [os.environ.get("SHELL", "/bin/zsh"), "-l"], p["path"], b""
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
        if url.path == "/api/raw":
            if q.get("token") != TOKEN:
                return self.send(403, {"error": "missing or stale token"})
            try:
                data, ctype = raw_file(project(q.get("project")), q.get("side"), clean_rel(q.get("path")))
            except ApiError as e:
                return self.send(e.code, {"error": str(e)})
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.close_connection = True
            self.end_headers()
            self.wfile.write(data)
            return
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
            p = project(q.get("name"))
            if p.get("remote_host"):
                want(p["remote_host"])                   # someone looks: its live sessions are checked while they do
                if not synced_at(p):
                    sync_remote(p, wait=5)               # never mirrored: do it now
                elif time.time() - synced_at(p) > 120:   # stale: refresh behind the page
                    threading.Thread(target=sync_remote, args=(p,), daemon=True).start()
            return project_state(p)
        if path == "/api/tree":
            p, rel = project(q.get("project")), clean_rel(q.get("path"))
            return {"entries": local_tree(p, rel) if q.get("side") == "local" else server_tree(p, rel, fresh)}
        if path == "/api/file":
            p, rel = project(q.get("project")), clean_rel(q.get("path"))
            if q.get("side") == "local":
                return local_read(p, rel, q.get("mode"))
            return server_read(p, rel, q.get("mode"), fresh)
        if path == "/api/plan":
            return team_plan(project(q.get("project")), q.get("map") or None, q.get("agent") or None)
        if path == "/api/job":
            job = _jobs.get(q.get("id"))
            if not job:
                raise ApiError(404, "no such job")
            return job
        if path == "/api/chat":
            after = q.get("after")
            return chat(q.get("pane"), int(after) if after and after.isdigit() else None, q.get("session"), q.get("screen") == "1",
                        q.get("around"))
        if path == "/api/search":
            return search(project(q.get("project")), q.get("q") or "")
        if path == "/api/events":
            after = q.get("after")
            return rg_notify.events_after(int(after) if after and after.isdigit() else 0)
        if path == "/api/notify":
            return rg_notify.describe()
        if path == "/api/skills":
            return skills()
        if path == "/api/gpus":
            return gpus(q.get("host"), fresh)
        if path == "/api/tmux":
            return tmux_peek(q.get("host"), q.get("session"))
        if path == "/api/gpu-hosts":
            return {"hosts": gpu_hosts(), "pools": gpu_pools()}
        if path == "/api/config":
            return config_text()
        raise ApiError(404, "unknown endpoint")

    def post_api(self, path, b):
        if path == "/api/start":
            p = project(b.get("project"))
            return start_job(p, team_plan(p, b.get("map") or None, b.get("agent") or None))
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
        if path == "/api/notify":
            return {"settings": rg_notify.save(b)}
        if path == "/api/notify-test":
            r = rg_notify.send_push("Research Desk", "Test push: notifications from Research Desk reach this phone.")
            if not r["ok"]:
                raise ApiError(502, f"push failed: {r['error']}")
            return r
        if path == "/api/project-inbox":
            return set_inbox(b)
        if path == "/api/paste":
            return paste_file(b)
        if path == "/api/btw":
            return btw_start(b)
        if path == "/api/btw-close":
            return btw_close(b)
        if path == "/api/remote-sync":
            p = project(b.get("project"))
            if not p.get("remote_host"):
                raise ApiError(400, "not a remote project")
            st = sync_remote(p, wait=30, force=True)             # Sync now: a person's action, even in back-off
            refresh_remote_herdr(p["remote_host"], wait=10, force=True)
            return {"at": st.get("at"), "error": st.get("error")}
        if path == "/api/new-project":
            return new_project(b)
        if path == "/api/moshi-mode":
            return {"moshi_mode": moshi_mode(bool(b.get("on")))}
        if path == "/api/ask-answer":
            if ARGS.dry_run:
                raise ApiError(400, "dry run: nothing sent")
            return answer_ask(b)
        if path == "/api/notify-sound":
            rg_notify.play(b.get("sound"))
            return {"ok": True}
        if path == "/api/client-error":                   # the page failed to start (web/js/boot.js)
            print(f"[{dt.datetime.now():%H:%M}] page failed to start (try {b.get('try')}): {str(b.get('error'))[:300]}", file=sys.stderr, flush=True)
            return {"ok": True}
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
    def warm():                                      # build search indexes once, quietly
        for p in load_config()["projects"].values():
            try:
                for f in project_transcripts(p):
                    rg_chat.update_index(f)
            except Exception:
                pass
    threading.Thread(target=warm, daemon=True).start()
    rg_notify.QUIET = ARGS.dry_run
    threading.Thread(target=monitor, daemon=True).start()
    threading.Thread(target=remote_sync_loop, daemon=True).start()
    threading.Thread(target=remote_herdr_loop, daemon=True).start()
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
