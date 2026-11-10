#!/usr/bin/env python3
"""team-watch: the watch tab's supervisor. Prints the driver's log as it grows, resumes a driver or worker stopped by
Claude's safeguards on Sonnet 5.5, and passes what needs the human to their alert command, once each.

Usage (from the project folder, inside herdr):  team-watch                 every driver on scratch/agents/roster.md
                                                team-watch <map> <driver pane> [agent name]   one driver
team-up starts it; after starting a team any other way, run it once in a spare tab: `caffeinate -dimsu team-watch`.

Every 5 minutes it looks at each driver's pane. A driver whose map is closed is skipped. A driver waiting on a
permission prompt (`blocked`) needs the human and is left alone.

Stopped by a safeguard: the driver is idle and its session ended on a safeguard stop (Claude Code then waits for a human
to retry or switch model). It is exited and its own session resumed in the same pane on Sonnet 5.5 at high effort
(`claude --resume <session> --model sonnet --effort high`), keeping its whole chat, then told to continue. It stays on
Sonnet 5.5 until the human switches it back. At most 3 resumes per driver per run.

Silent: the driver is idle and its own session has written nothing for 90 minutes (longer than its longest sleep, an
hour), so its /loop has ended. Silence is read from that session's transcript, never from the shared driver.log, where
another driver's line would hide it. A silent driver is not restarted and not prompted (a driver often waits on purpose,
and until 11-10 all 15 resumes were of such drivers, each moved to Sonnet): the human gets one alert per silence. A
driver whose map is paused is not reported.

Questions for the human go to the alert command once each: every open grilling or prototype ticket of a map that is neither
paused nor closed, and every new driver.log line that says `needs-you` (unless it names a ticket already sent). What
was sent is kept in scratch/agents/team-watch.pushed, so restarting the watch sends nothing twice.

A Codex driver has no /loop: the watchdog is its schedule. It types `tick` into the driver's pane once the pane has been
idle, with no change of state and no tick, for 25 minutes. A Codex driver is never resumed; one whose pane does not move
for 90 minutes despite the ticks is reported once.

Workers (the Claude tabs team-worker opened in the watched drivers' workspaces) are checked too: one whose reply Claude's
safeguards stopped is resumed once with `team-worker --rescue`, so it does not wait for the driver's next pass (up to an
hour). Stopped again, or stopped before this watch started, it is left to its driver, which gets one line.

An alert runs the command in ~/.config/research-harness/notify, if that file exists, with the message as its last
argument and its kind in RH_EVENT: `question`, `silent` or `gave-up`. Your command routes it (a phone push, a sound, a
banner; the `alerts` preset installs one that routes by kind). Without the file, alerts go only to driver.log.
Every action is logged to driver.log.
"""
import datetime as dt
import fcntl
import glob
import json
import os
import re
import shlex
import subprocess
import sys
import time

EVERY, STALE_MIN, MAX_RESTARTS, MODEL, EFFORT, TICK_MIN = 300, 90, 3, "sonnet", "high", 25
LOG = os.path.join("scratch", "agents", "driver.log")
ROSTER = os.path.join("scratch", "agents", "roster.md")
PUSHED = os.path.join("scratch", "agents", "team-watch.pushed")   # what the human was already told, one key per line
HERE = os.path.dirname(os.path.realpath(__file__))
TEAM_WORKER = os.path.join(HERE, "team-worker.py")
sys.path.insert(0, HERE)
import status as tracker   # noqa: E402  (status.py, the `research-status` parser: maps, tickets, what waits on the human)
WORKER_NAME = re.compile(r"^(.+)-s?\d{6}$")   # team-worker names a worker <ticket id>-HHMMSS (rescued: -sHHMMSS)
NEEDS = re.compile(r"\bneeds-you\b", re.I)
NO_NEEDS = re.compile(r"\bno\b[^.;|]{0,30}\bneeds-you\b", re.I)
STAMP = re.compile(r"^\d{4}-\d\d-\d\d[T ][\d:]+Z?\s*\|?\s*")
STARTED = time.time()


def roster_drivers():
    """{pane: (map, session name)} for the driver lines on the roster (the latest line per pane wins)."""
    out = {}
    if os.path.exists(ROSTER):
        for line in open(ROSTER):
            cells = [c.strip() for c in line.split("|")]
            if len(cells) >= 6 and cells[0] == "driver" and cells[2] not in ("", "-") and cells[5] not in ("", "-"):
                out[cells[2]] = (cells[5].split()[0], (cells[3].split() or [""])[0])
    return out


def load_maps():
    try:
        return tracker.load(".")
    except (OSError, ValueError):          # a file caught half-written: next cycle reads it whole
        return []


def map_state(maps, ref, name):
    """(map id, status) of the map a driver drives: the roster's map cell as a folder or an id, else the open map whose
    claim names the driver's session (a roster line may describe its map in words). (None, None) when neither finds
    one: that driver is watched as on an open map."""
    want = os.path.basename(ref.rstrip("/")).lower()
    for m in maps:
        if want in (os.path.basename(os.path.dirname(m["_path"])).lower(), str(m.get("id")).lower()):
            return m.get("id"), tracker.status_of(m)
    for m in maps:
        if name and tracker.status_of(m) != "closed" and name in f"{m.get('status')} {m.get('claimed')}":
            return m.get("id"), tracker.status_of(m)
    return None, None


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def herdr(*args, timeout=150):
    return subprocess.run(["herdr", *args], capture_output=True, text=True, timeout=timeout)


def agent_at(pane):
    try:
        out = json.loads(herdr("agent", "list", timeout=20).stdout or "{}")
    except (ValueError, subprocess.SubprocessError):
        return None
    return next((a for a in out.get("result", {}).get("agents", []) if a.get("pane_id") == pane), None)


def note(text):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{now()}  watchdog: {text}\n")
    print(f"{now()}  watchdog: {text}", flush=True)


def transcript(session_id):
    hits = glob.glob(os.path.expanduser(f"~/.claude/projects/*/{session_id}.jsonl")) if session_id else []
    return max(hits, key=os.path.getmtime) if hits else None


NOTIFY = os.path.expanduser("~/.config/research-harness/notify")   # optional: your own alert command


def alert(text, kind="other"):
    """note(), plus the human's own alert: the command in ~/.config/research-harness/notify, if any, with the
    message added as its last argument and the kind in RH_EVENT (question, silent, gave-up), so the command can route
    it (e.g. extras/notify.py, the `alerts` preset; or `ntfy publish <topic>`). Best effort."""
    note(text)
    try:
        cmd = shlex.split(open(NOTIFY).read().strip())
    except (OSError, ValueError):
        return
    if cmd:
        try:
            subprocess.run([os.path.expanduser(c) for c in cmd] + [text], capture_output=True, timeout=60,
                           env={**os.environ, "RH_EVENT": kind})
        except (OSError, subprocess.SubprocessError):
            pass


def load_pushed():
    try:
        return set(open(PUSHED).read().splitlines())
    except OSError:
        return set()


def save_pushed(pushed):
    with open(PUSHED + ".tmp", "w") as f:
        f.write("".join(k + "\n" for k in sorted(pushed)))
    os.replace(PUSHED + ".tmp", PUSHED)


def push_once(key, text, pushed, kind):
    """alert() the human, unless this key was sent before (by this watch or an earlier one)."""
    if key not in pushed:
        pushed.add(key)
        alert(text, kind)


def push_questions(maps, pushed):
    """Each open question for the human (a grilling or prototype ticket, an old map's Needs-you item) once. Paused and
    closed maps are left alone. More than 3 new at once (a first run) go as one alert."""
    quiet = {m.get("id") for m in maps if tracker.status_of(m) in ("paused", "closed")}
    new = [(mid, text, f"ask {key}") for mid, text, key in tracker.waiting(maps)
           if mid not in quiet and f"ask {key}" not in pushed]
    if len(new) > 3:
        pushed.update(key for _, _, key in new)
        alert(f"{len(new)} questions wait on you ({', '.join(sorted({str(mid) for mid, _, _ in new}))}): research-status --now", "question")
        return
    for mid, text, key in new:
        push_once(key, f"needs you ({mid}): {text}"[:400], pushed, "question")


def asked(maps):
    """Ids and paths of the tickets waiting on the human: a log line that names one adds nothing to that ticket's alert."""
    paths = {key for _, _, key in tracker.waiting(maps)}
    return paths | {str(k.get("id")) for m in maps for k in m["_tickets"] if k["_path"] in paths}


def push_needs(lines, pushed, covered=()):
    """Each new driver.log line that says `needs-you`, once: what a driver sends the desk reaches the human's phone too."""
    for line in lines:
        m = NEEDS.search(line)
        if m and "watchdog:" not in line and not NO_NEEDS.search(line) and not any(c.lower() in line.lower() for c in covered):
            push_once("log " + STAMP.sub("", line)[:160], "driver.log: …" + line[max(0, m.start() - 160):m.start() + 240], pushed,
                      "question")


def ended_on_safeguard_stop(session_id):
    """True when the session's transcript ends on a reply Claude's safeguards stopped (or Claude Code's retry note)."""
    path = transcript(session_id)
    if not path:
        return False
    with open(path, "rb") as f:
        f.seek(max(0, f.seek(0, 2) - (256 << 10)))
        lines = f.read().split(b"\n")
    for line in reversed(lines):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("isSidechain") or d.get("type") not in ("user", "assistant"):
            continue
        msg = d.get("message") or {}
        if d["type"] == "assistant":
            return msg.get("stop_reason") == "refusal"
        c = msg.get("content")
        if isinstance(c, str):
            return "stopped by a safety classifier" in c
        if any(isinstance(x, dict) and x.get("type") == "tool_result" for x in c or []):
            continue
        return any("stopped by a safety classifier" in (x.get("text") or "") for x in c or [] if isinstance(x, dict))
    return False


def stuck_reason(agent):
    if not agent or agent.get("agent_status") in ("working", "blocked"):
        return None
    if ended_on_safeguard_stop((agent.get("agent_session") or {}).get("value")):
        return "its last reply was stopped by Claude's safeguards"
    return None


def check_silence(pane, label, agent, pushed):
    """An idle driver whose own session wrote nothing for STALE_MIN has lost its /loop. One alert per silence; the
    driver is not restarted and not prompted. A session whose transcript cannot be found is never judged."""
    path = transcript((agent.get("agent_session") or {}).get("value"))
    if not path:
        return
    quiet, key = (time.time() - os.path.getmtime(path)) / 60, f"silent {pane}"
    if quiet <= STALE_MIN:
        pushed.discard(key)
    elif agent.get("agent_status") not in ("working", "blocked"):
        push_once(key, f"driver for {label} in {pane} is idle and has written nothing for {quiet:.0f} min: its loop has "
                       f"ended. Not restarted; left for the human", pushed, "silent")


def restart(pane, name, map_ref, reason, session, n):
    note(f"driver in {pane} is stuck ({reason}); resuming its session {session[:8]} on Sonnet 5.5 (resume {n})")
    herdr("agent", "prompt", pane, "/exit")
    time.sleep(8)
    start = herdr("agent", "start", name, "--kind", "claude", "--pane", pane, "--timeout", "120000",
                  "--", "--resume", session, "--model", MODEL, "--effort", EFFORT)
    if start.returncode != 0:
        note(f"could not resume the driver: {(start.stderr or start.stdout).strip()[:200]}; trying again next cycle")
        return False
    herdr("agent", "prompt", name, f"continue: the watchdog resumed this session on Sonnet 5.5 ({reason}). Pick up the "
                                   f"pass for {map_ref} where you stopped, but before repeating a dispatch, launch or other "
                                   f"outside action, check driver.log, the tickets and the server for what already ran; "
                                   f"no summary, end with one line naming the file; hand biology steps to their delegate "
                                   f"by pointer.")
    return True


def tick(pane, agent, ticks, moved, pushed):
    """Wake an idle Codex driver with `tick` when its pane changed state last, and was ticked last, TICK_MIN minutes ago
    or more. `moved` holds, per pane, herdr's state counter and when this watch saw it change."""
    seq = agent.get("state_change_seq")
    if pane not in moved:
        moved[pane] = (seq, STARTED - TICK_MIN * 60)      # first sight: a tick is due as soon as the pane is idle
    elif moved[pane][0] != seq:
        moved[pane] = (seq, time.time())
        pushed.discard(f"silent {pane}")
    if agent.get("agent_status") in ("working", "blocked"):
        return
    changed = moved[pane][1]
    if (time.time() - max(changed, ticks.get(pane, 0))) / 60 < TICK_MIN:
        return
    quiet = (time.time() - changed) / 60
    if quiet > STALE_MIN and pane in ticks:
        push_once(f"silent {pane}", f"Codex driver in {pane} has not moved for {quiet:.0f} min despite ticks; left for the human",
                  pushed, "silent")
    herdr("agent", "prompt", pane, "tick")
    ticks[pane] = time.time()


def workers(spaces):
    """{pane: (ticket id, agent)}: the Claude workers team-worker opened in these workspaces (agent named after its tab)."""
    try:
        agents = json.loads(herdr("agent", "list", timeout=20).stdout or "{}").get("result", {}).get("agents", [])
        tabs = json.loads(herdr("tab", "list", timeout=20).stdout or "{}").get("result", {}).get("tabs", [])
    except (ValueError, subprocess.SubprocessError):
        return {}
    label = {t.get("tab_id"): t.get("label") or "" for t in tabs}
    out = {}
    for a in agents:
        m, tid = WORKER_NAME.match(a.get("name") or ""), label.get(a.get("tab_id"), "")
        if a.get("workspace_id") in spaces and a.get("agent") == "claude" and m and m.group(1) == tid.lower():
            out[a["pane_id"]] = (tid, a)
    return out


def driver_of(tid, drivers):
    """The driver pane whose map shares the ticket's prefix (T12 for T12-09)."""
    prefix = tid.split("-")[0].upper()
    return next((p for p, m in drivers.items() if os.path.basename(m.rstrip("/")).split("-")[0].upper() == prefix), None)


def check_worker(pane, tid, agent, drivers, rescued):
    """Rescue a worker stopped by Claude's safeguards once; after that, or for a stop older than this watch, tell its driver."""
    session = (agent.get("agent_session") or {}).get("value")
    if rescued.get(pane) == "left" or agent.get("agent_status") in ("working", "blocked") or not ended_on_safeguard_stop(session):
        return
    if pane in rescued:
        why = "again, after its Sonnet rescue"
    elif os.path.getmtime(transcript(session)) < STARTED:
        why = "before this watch started"
    else:
        rescued[pane] = "rescued"
        note(f"worker {tid} in {pane} was stopped by Claude's safeguards; resuming it on Sonnet 5.5 (team-worker --rescue)")
        r = subprocess.run([sys.executable, TEAM_WORKER, "--rescue", tid], capture_output=True, text=True, timeout=300)
        if r.returncode == 0:
            return
        why = f"the rescue failed: {(r.stderr or r.stdout).strip()[:200]}"
    rescued[pane] = "left"
    driver = driver_of(tid, drivers)
    msg = f"worker {tid} in {pane} is stopped by Claude's safeguards ({why}); left to {'its driver ' + driver if driver else 'the human'}"
    note(msg) if driver else alert(msg, "gave-up")
    if driver:
        herdr("agent", "prompt", driver, f"watchdog: worker {tid} in {pane} was stopped by Claude's safeguards ({why}); "
                                         f"read its screen and hand that step to its delegate (docs/agents/delegation.md)")


def handle_stuck(pane, map_ref, agent, base, restarts, fails, given_up):
    """Resume a Claude driver stopped by a safeguard. Only a resume that started counts toward MAX_RESTARTS; a start that failed (the pane
    busy, 10-31: 4 such failures used up both drivers' resumes) is tried again next cycle, at most MAX_RESTARTS times in a
    row. Giving up pushes to the human's phone. True when it acted."""
    reason = stuck_reason(agent)
    if not reason:
        return False
    if pane in given_up:
        return True
    session = (agent.get("agent_session") or {}).get("value")
    done, failed = restarts.get(pane, 0), fails.get(pane, 0)
    if done >= MAX_RESTARTS or failed >= MAX_RESTARTS or not session:
        why = "its session id is unknown" if not session else f"{done} resumes, {failed} failed starts in a row"
        alert(f"driver in {pane} is stuck ({reason}); {why}: leaving it for the human", "gave-up")
        given_up.add(pane)
        return True
    if restart(pane, f"{base}-{pane.replace(':', '')}-r{done + 1}", map_ref, reason, session, done + 1):
        restarts[pane], fails[pane] = done + 1, 0
    else:
        fails[pane] = failed + 1
    return True


LOCK = os.path.join("scratch", "agents", "team-watch.pid")   # also the heartbeat: touched every cycle


def single():
    """Only one team-watch per project: two would both restart the same driver. An OS lock, not a pid check: two watches
    starting together cannot both take it, and it is released when the process dies, so it never goes stale."""
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    fd = os.open(LOCK, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        other = os.read(fd, 32).decode().strip() or "?"
        sys.exit(f"team-watch is already running for this project (pid {other}); stop it first or use that one")
    os.ftruncate(fd, 0)
    os.write(fd, str(os.getpid()).encode())     # the pid, for Research Desk and the error above
    return fd                                   # kept open for the process's life: closing it releases the lock


def show_log(seen, pushed, covered=()):
    """Print what the drivers added to driver.log since `seen` (whole lines; the watchdog's own were printed by note())
    and push its needs-you lines, except those about a ticket in `covered`. Returns the new offset."""
    if not os.path.exists(LOG) or os.path.getsize(LOG) <= seen:
        return min(seen, os.path.getsize(LOG)) if os.path.exists(LOG) else 0
    with open(LOG, "rb") as f:
        f.seek(seen)
        chunk = f.read()
    chunk = chunk[:chunk.rfind(b"\n") + 1]
    lines = [l for l in chunk.decode(errors="replace").splitlines() if "  watchdog: " not in l]
    if lines:
        print("\n".join(lines), flush=True)
    push_needs(lines, pushed, covered)
    return seen + len(chunk)


def main():
    if len(sys.argv) == 2 or sys.argv[1:2] in (["-h"], ["--help"]):
        sys.exit(__doc__)
    lock = single()   # noqa: F841 (held until exit)
    fixed = {sys.argv[2]: (sys.argv[1], "")} if len(sys.argv) >= 3 else None
    base = sys.argv[3] if len(sys.argv) > 3 else "driver"
    restarts, fails, given_up, ticks, moved, rescued = {}, {}, set(), {}, {}, {}
    pushed = load_pushed()
    seen = os.path.getsize(LOG) if os.path.exists(LOG) else 0
    print(f"{now()}  watching " + (f"the driver in {sys.argv[2]}" if fixed else "every driver on the roster"), flush=True)
    while True:
        os.utime(LOCK)        # a session that cannot list processes (Codex's sandbox) reads this file's age instead
        told = set(pushed)
        maps = load_maps()
        push_questions(maps, pushed)
        seen = show_log(seen, pushed, asked(maps))
        drivers, spaces = {}, set()
        for pane, (ref, name) in (fixed or roster_drivers()).items():
            map_id, state = map_state(maps, ref, name)
            label = drivers[pane] = map_id or ref
            agent = agent_at(pane)
            spaces.add((agent or {}).get("workspace_id"))
            if not agent or state == "closed":
                continue
            if agent.get("agent") == "codex":
                tick(pane, agent, ticks, moved, pushed)
            elif not handle_stuck(pane, label, agent, base, restarts, fails, given_up) and state != "paused":
                check_silence(pane, label, agent, pushed)
        for pane, (tid, agent) in workers(spaces - {None}).items():
            check_worker(pane, tid, agent, drivers, rescued)
        if pushed != told:
            save_pushed(pushed)
        time.sleep(EVERY)


if __name__ == "__main__":
    main()
