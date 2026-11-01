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
in the same pane on Sonnet 5.5 at xhigh effort (`claude --resume <session> --model sonnet --effort xhigh`), keeping its whole chat, then told to
continue. It stays on Sonnet 5.5 until the human switches it back. At most 3 resumes per driver per run; every action is
logged to driver.log.
"""
import datetime as dt
import glob
import json
import os
import subprocess
import sys
import time

EVERY, STALE_MIN, MAX_RESTARTS, MODEL, EFFORT = 300, 90, 3, "sonnet", "xhigh"
LOG = os.path.join("scratch", "agents", "driver.log")
ROSTER = os.path.join("scratch", "agents", "roster.md")


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


def ended_on_safeguard_stop(session_id):
    """True when the session's transcript ends on a reply Claude's safeguards stopped (or Claude Code's retry note)."""
    if not session_id:
        return False
    hits = glob.glob(os.path.expanduser(f"~/.claude/projects/*/{session_id}.jsonl"))
    if not hits:
        return False
    with open(max(hits, key=os.path.getmtime), "rb") as f:
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
        note(f"could not resume the driver: {start.stderr.strip()[:200]}; leaving it for the human")
        return False
    herdr("agent", "prompt", name, f"continue: the watchdog resumed this session on Sonnet 5.5 ({reason}). Pick up the "
                                   f"pass for {map_ref} where you stopped, but before repeating a dispatch, launch or other "
                                   f"outside action, check driver.log, the tickets and the server for what already ran; "
                                   f"no summary, end with one line naming the file; hand biology steps to their delegate "
                                   f"by pointer.")
    return True


def single():
    """Only one team-watch per project: two would both restart the same driver."""
    lock = os.path.join("scratch", "agents", "team-watch.pid")
    try:
        other = int(open(lock).read().strip())
        os.kill(other, 0)
        if other != os.getpid():
            sys.exit(f"team-watch is already running for this project (pid {other}); stop it first or use that one")
    except (OSError, ValueError):
        pass
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    with open(lock, "w") as f:
        f.write(str(os.getpid()))


def main():
    if len(sys.argv) == 2 or sys.argv[1:2] in (["-h"], ["--help"]):
        sys.exit(__doc__)
    single()
    fixed = {sys.argv[2]: sys.argv[1]} if len(sys.argv) >= 3 else None
    base = sys.argv[3] if len(sys.argv) > 3 else "driver"
    restarts, seen = {}, os.path.getsize(LOG) if os.path.exists(LOG) else 0
    print(f"{now()}  watching " + (f"the driver in {sys.argv[2]}" if fixed else "every driver on the roster"), flush=True)
    while True:
        if os.path.exists(LOG) and os.path.getsize(LOG) > seen:     # show the driver's log as it grows
            with open(LOG) as f:
                f.seek(seen)
                sys.stdout.write(f.read())
                sys.stdout.flush()
            seen = os.path.getsize(LOG)
        for pane, map_ref in (fixed or roster_drivers()).items():
            agent = agent_at(pane)
            reason = stuck_reason(agent)
            if not reason or restarts.get(pane, 0) > MAX_RESTARTS:
                continue
            if restarts.get(pane, 0) == MAX_RESTARTS:
                note(f"driver in {pane} is stuck ({reason}) and {MAX_RESTARTS} resumes are used up; leaving it for the human")
                restarts[pane] += 1
                continue
            restarts[pane] = restarts.get(pane, 0) + 1
            session = (agent.get("agent_session") or {}).get("value")
            if not session:
                note(f"driver in {pane} is stuck ({reason}) but its session id is unknown; leaving it for the human")
                restarts[pane] = MAX_RESTARTS + 1
                continue
            name = f"{base}-{pane.replace(':', '')}-r{restarts[pane]}"
            restart(pane, name, map_ref, reason, session, restarts[pane])
            seen = os.path.getsize(LOG) if os.path.exists(LOG) else 0
        time.sleep(EVERY)


if __name__ == "__main__":
    main()
