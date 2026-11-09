#!/usr/bin/env python3
"""team-watch: the watch tab's supervisor. Prints the driver's log as it grows, and resumes a stuck driver's own session
on Sonnet 5.5, so a map keeps moving while nobody is watching.

Usage (from the project folder, inside herdr):  team-watch                 every driver on scratch/agents/roster.md
                                                team-watch <map> <driver pane> [agent name]   one driver
team-up starts it; after starting a team any other way, run it once in a spare tab: `caffeinate -dimsu team-watch`.

Every 5 minutes it looks at the driver's pane. The driver is stuck when it is idle and either its session ended on a
safeguard stop (Claude Code then waits for a human to retry or switch model), or no pass has been logged in
scratch/agents/driver.log for 90 minutes (longer than the driver's longest sleep, an hour). A driver waiting on a
permission prompt (`blocked`) needs the human and is left alone. A stuck driver is exited and its own session resumed
in the same pane on Sonnet 5.5 at high effort (`claude --resume <session> --model sonnet --effort high`), keeping its whole chat, then told to
continue. It stays on Sonnet 5.5 until the human switches it back. At most 3 resumes per driver per run; every action is
logged to driver.log.

A Codex driver has no /loop: the watchdog is its schedule. It types `tick` into the driver's pane once the driver is idle
and neither a pass nor a tick has come for 25 minutes. A Codex driver is never resumed; one that logs no pass for 90
minutes despite the ticks is noted once, for the human.

Workers (the Claude tabs team-worker opened in the watched drivers' workspaces) are checked too: one whose reply Claude's
safeguards stopped is resumed once with `team-worker --rescue`, so it does not wait for the driver's next pass (up to an
hour). Stopped again, or stopped before this watch started, it is left to its driver, which gets one line.

When it gives up on anything, it runs the command in ~/.config/research-harness/notify, if that file exists, with the
message as its last argument: your own phone or desktop alert. Without it, give-ups go only to driver.log.
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
TEAM_WORKER = os.path.join(os.path.dirname(os.path.realpath(__file__)), "team-worker.py")
WORKER_NAME = re.compile(r"^(.+)-s?\d{6}$")   # team-worker names a worker <ticket id>-HHMMSS (rescued: -sHHMMSS)
STARTED = time.time()


def roster_drivers():
    """{pane: map} for the driver lines on the roster (the latest line per pane wins)."""
    out = {}
    if os.path.exists(ROSTER):
        for line in open(ROSTER):
            cells = [c.strip() for c in line.split("|")]
            if len(cells) >= 6 and cells[0] == "driver" and cells[2] not in ("", "-") and cells[5] not in ("", "-"):
                out[cells[2]] = cells[5].split()[0]
    return out


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


def alert(text):
    """note(), plus your own alert for a give-up: the command in ~/.config/research-harness/notify, if any, with the
    message added as its last argument (e.g. `ntfy publish <topic>`, or a phone app's notify command). Best effort."""
    note(text)
    try:
        cmd = shlex.split(open(NOTIFY).read().strip())
    except (OSError, ValueError):
        return
    if cmd:
        try:
            subprocess.run([os.path.expanduser(cmd[0]), *cmd[1:], text], capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            pass


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
    last_pass = os.path.getmtime(LOG) if os.path.exists(LOG) else 0
    if ended_on_safeguard_stop((agent.get("agent_session") or {}).get("value")):
        return "its last reply was stopped by Claude's safeguards"
    idle_min = (time.time() - last_pass) / 60
    if last_pass and idle_min > STALE_MIN:
        return f"no pass logged for {idle_min:.0f} min"
    return None


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


def tick(pane, agent, ticks, warned):
    """Wake an idle Codex driver with `tick` when neither a pass nor a tick came for TICK_MIN minutes."""
    if agent.get("agent_status") in ("working", "blocked"):
        return
    last_pass = os.path.getmtime(LOG) if os.path.exists(LOG) else 0
    if (time.time() - max(last_pass, ticks.get(pane, 0))) / 60 < TICK_MIN:
        return
    silent = (time.time() - last_pass) / 60
    if last_pass and silent > STALE_MIN and pane not in warned:
        alert(f"Codex driver in {pane} has logged no pass for {silent:.0f} min despite ticks; leaving it for the human")
        warned.add(pane)
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
    (note if driver else alert)(f"worker {tid} in {pane} is stopped by Claude's safeguards ({why}); left to {'its driver ' + driver if driver else 'the human'}")
    if driver:
        herdr("agent", "prompt", driver, f"watchdog: worker {tid} in {pane} was stopped by Claude's safeguards ({why}); "
                                         f"read its screen and hand that step to its delegate (docs/agents/delegation.md)")


def handle_stuck(pane, map_ref, agent, base, restarts, fails, given_up):
    """Resume a stuck Claude driver. Only a resume that started counts toward MAX_RESTARTS; a start that failed (the pane
    busy, 10-31: 4 such failures used up both drivers' resumes) is tried again next cycle, at most MAX_RESTARTS times in a
    row. Giving up pushes to the human's phone. True when it acted."""
    reason = stuck_reason(agent)
    if not reason or pane in given_up:
        return False
    session = (agent.get("agent_session") or {}).get("value")
    done, failed = restarts.get(pane, 0), fails.get(pane, 0)
    if done >= MAX_RESTARTS or failed >= MAX_RESTARTS or not session:
        why = "its session id is unknown" if not session else f"{done} resumes, {failed} failed starts in a row"
        alert(f"driver in {pane} is stuck ({reason}); {why}: leaving it for the human")
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


def main():
    if len(sys.argv) == 2 or sys.argv[1:2] in (["-h"], ["--help"]):
        sys.exit(__doc__)
    lock = single()   # noqa: F841 (held until exit)
    fixed = {sys.argv[2]: sys.argv[1]} if len(sys.argv) >= 3 else None
    base = sys.argv[3] if len(sys.argv) > 3 else "driver"
    restarts, fails, given_up, ticks, warned, rescued = {}, {}, set(), {}, set(), {}
    seen = os.path.getsize(LOG) if os.path.exists(LOG) else 0
    print(f"{now()}  watching " + (f"the driver in {sys.argv[2]}" if fixed else "every driver on the roster"), flush=True)
    while True:
        os.utime(LOCK)        # a session that cannot list processes (Codex's sandbox) reads this file's age instead
        if os.path.exists(LOG) and os.path.getsize(LOG) > seen:     # show the driver's log as it grows
            with open(LOG) as f:
                f.seek(seen)
                sys.stdout.write(f.read())
                sys.stdout.flush()
            seen = os.path.getsize(LOG)
        drivers, spaces = fixed or roster_drivers(), set()
        for pane, map_ref in drivers.items():
            agent = agent_at(pane)
            spaces.add((agent or {}).get("workspace_id"))
            if agent and agent.get("agent") == "codex":
                tick(pane, agent, ticks, warned)
                continue
            if handle_stuck(pane, map_ref, agent, base, restarts, fails, given_up):
                seen = os.path.getsize(LOG) if os.path.exists(LOG) else 0
        for pane, (tid, agent) in workers(spaces - {None}).items():
            check_worker(pane, tid, agent, drivers, rescued)
        time.sleep(EVERY)


if __name__ == "__main__":
    main()
