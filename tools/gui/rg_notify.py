"""Notifications: which events reach you, and how (a Mac banner, a Mac sound, a Moshi push on your phone).

The backend's monitor turns state changes into events (rg_notify.emit); each event kind has its channels in
~/.config/research-gui/notify.json. Sounds and pushes are sent from here, so they work with the app window closed;
banners are shown by the page, which reads the same event log (/api/events). Pushes go to Moshi's webhook with the
token from the Keychain item `moshi-push`; they are bundled (one push per 20 s window) and rate-limited, and can be
held back while you are at the Mac.
"""
import json
import os
import subprocess
import threading
import time

FILE = os.path.expanduser("~/.config/research-gui/notify.json")
KINDS = {   # kind -> (label, what it means, default channels, default sound); INBOX below marks what waits on you
    "prompt": ("Needs your answer", "an agent stops at a permission or question prompt", ["banner", "sound", "push"], "Sosumi"),
    "reply": ("Reply to your message", "an agent finishes the turn you started from the app", ["banner", "sound", "push"], "Glass"),
    "decision": ("New decision for you", "a grilling or prototype ticket appears", ["banner", "push"], "Ping"),
    "loop": ("A loop went quiet", "a driver missed a pass, or a pass died", ["banner", "sound", "push"], "Basso"),
    "safeguard": ("Safeguard flag", "Opus's safeguards stopped a reply or switched the model", ["banner", "push"], "Funk"),
    "desk_reply": ("Every desk reply", "the desk finishes any turn", [], "Glass"),
    "any_reply": ("Every reply from any agent", "any session finishes a turn", [], "Tink"),
    "result": ("Results", "a ticket resolves or a map closes", ["banner"], "Hero"),
    "progress": ("Other ticket changes", "a ticket starts running, is held or parked", [], "Pop"),
}
INBOX = ["prompt", "decision", "loop", "safeguard"]   # what waits on the human (a reply to them does not)
SOUNDS = ["Basso", "Blow", "Bottle", "Frog", "Funk", "Glass", "Hero", "Morse", "Ping", "Pop", "Purr", "Sosumi", "Submarine", "Tink"]
MOSHI_URL = "https://api.getmoshi.app/api/webhook"
KEYCHAIN = "moshi-push"

QUIET = False         # a dry-run backend records events but plays and pushes nothing (the real one already does)
_lock = threading.Lock()
_events = []          # recent events, newest last: {seq, at, kind, title, body, project, pane, map, ticket, channels}
_seq = [0]
_push = {"queue": [], "timer": None, "sent": []}


def defaults():
    return {"events": {k: {"channels": list(v[2]), "sound": v[3]} for k, v in KINDS.items()},
            "push_away_only": False, "away_minutes": 5, "push_max_per_hour": 30}


def load():
    d = defaults()
    try:
        with open(FILE) as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return d
    for k, v in (saved.get("events") or {}).items():
        if k in d["events"] and isinstance(v, dict):
            chans = [c for c in v.get("channels", []) if c in ("banner", "sound", "push")]
            d["events"][k] = {"channels": chans, "sound": v.get("sound") if v.get("sound") in SOUNDS else d["events"][k]["sound"]}
    for key in ("push_away_only", "away_minutes", "push_max_per_hour"):
        if key in saved:
            d[key] = saved[key]
    return d


def save(d):
    clean = defaults()
    for k, v in (d.get("events") or {}).items():
        if k in clean["events"]:
            clean["events"][k] = {"channels": [c for c in v.get("channels", []) if c in ("banner", "sound", "push")],
                                  "sound": v.get("sound") if v.get("sound") in SOUNDS else clean["events"][k]["sound"]}
    clean["push_away_only"] = bool(d.get("push_away_only"))
    clean["away_minutes"] = max(1, min(120, int(d.get("away_minutes") or 5)))
    clean["push_max_per_hour"] = max(1, min(200, int(d.get("push_max_per_hour") or 30)))
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    with open(FILE + ".tmp", "w") as f:
        json.dump(clean, f, indent=1)
    os.replace(FILE + ".tmp", FILE)
    return clean


def describe():
    return {"kinds": [{"kind": k, "label": v[0], "meaning": v[1], "inbox": k in INBOX} for k, v in KINDS.items()],
            "sounds": SOUNDS, "settings": load(), "push_ready": token() is not None, "idle_seconds": idle_seconds()}


def idle_seconds():
    """Seconds since the last keyboard or mouse input on this Mac."""
    try:
        out = subprocess.run(["ioreg", "-c", "IOHIDSystem"], capture_output=True, text=True, timeout=5).stdout
        for line in out.splitlines():
            if "HIDIdleTime" in line:
                return int(line.rsplit("=", 1)[1].strip()) // 1_000_000_000
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return 0


_tok = {"t": 0, "v": None}


def token():
    if time.time() - _tok["t"] > 60:
        r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN, "-w"], capture_output=True, text=True, timeout=5)
        _tok.update(t=time.time(), v=r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None)
    return _tok["v"]


def play(sound):
    if sound in SOUNDS:
        subprocess.Popen(["afplay", f"/System/Library/Sounds/{sound}.aiff"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def send_push(title, message):
    """One Moshi push; curl, since Moshi's Cloudflare front refuses Python's default client."""
    tok = token()
    if not tok:
        return {"ok": False, "error": f"no `{KEYCHAIN}` item in the Keychain"}
    body = json.dumps({"token": tok, "title": title[:120], "message": message[:400]})
    r = subprocess.run(["curl", "-s", "-m", "20", "-X", "POST", MOSHI_URL, "-H", "Content-Type: application/json", "-d", "@-"],
                       input=body, capture_output=True, text=True, timeout=30)
    try:
        ok = json.loads(r.stdout).get("success") is True
    except ValueError:
        ok = False
    return {"ok": ok, "error": None if ok else (r.stdout or r.stderr)[:200]}


def _flush():
    with _lock:
        batch, _push["queue"], _push["timer"] = _push["queue"], [], None
        hour = time.time() - 3600
        _push["sent"] = [t for t in _push["sent"] if t > hour]
        allowed = load()["push_max_per_hour"] - len(_push["sent"])
        if not batch or allowed <= 0:
            return
        _push["sent"].append(time.time())
    if len(batch) == 1:
        send_push(batch[0]["title"], batch[0]["body"])
    else:
        send_push(f"{len(batch)} things need you", "\n".join(f"• {e['title']}" for e in batch[:8]))


def emit(kind, title, body="", **where):
    """Record an event and deliver it on its sound and push channels; the page shows banners from the log."""
    if kind not in KINDS:
        return
    cfg = load()
    rule = cfg["events"][kind]
    with _lock:
        _seq[0] += 1
        ev = {"seq": _seq[0], "at": time.time(), "kind": kind, "title": title, "body": body, "channels": rule["channels"], **where}
        _events.append(ev)
        del _events[:-300]
    if QUIET:
        return
    if "sound" in rule["channels"]:
        play(rule["sound"])
    if "push" in rule["channels"] and not (cfg["push_away_only"] and idle_seconds() < cfg["away_minutes"] * 60):
        with _lock:
            _push["queue"].append(ev)
            if not _push["timer"]:                   # bundle what arrives within 20 s into one push
                _push["timer"] = threading.Timer(20, _flush)
                _push["timer"].daemon = True
                _push["timer"].start()


def events_after(seq):
    with _lock:
        return {"events": [e for e in _events if e["seq"] > seq], "last": _seq[0]}
