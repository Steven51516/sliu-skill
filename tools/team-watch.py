#!/usr/bin/env python3
"""team-watch: the watch tab's supervisor. Prints the driver's log as it grows, and replaces a stuck driver with a fresh
one on Sonnet 5.5, so a map keeps moving while nobody is watching.

Usage (from the project folder, inside herdr):  team-watch                 every driver on scratch/agents/roster.md
                                                team-watch <map> <driver pane> [agent name]   one driver
team-up starts it; after starting a team any other way, run it once in a spare tab: `caffeinate -dimsu team-watch`.

Every 5 minutes it looks at the driver's pane. The driver is stuck when it is idle and either its session ended on a
safeguard stop (Claude Code then waits for a human to retry or switch model), or no pass has been logged in
scratch/agents/driver.log for 90 minutes (longer than the driver's longest sleep, an hour). A driver waiting on a
permission prompt (`blocked`) needs the human and is left alone. A stuck driver is closed and a fresh one started on
Sonnet 5.5 in the same pane with `/team driver <map>`; the map and its tickets hold its state, so it picks up from
there. At most 3 restarts per run; every action is logged to driver.log.
"""
import datetime as dt
import glob
import json
import os
import subprocess
import sys
import time

EVERY, STALE_MIN, MAX_RESTARTS, MODEL = 300, 90, 3, "sonnet"
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


def restart(pane, name, map_ref, reason, old_sid, n):
    note(f"driver in {pane} is stuck ({reason}); closing it and starting a fresh driver on Sonnet 5.5 (restart {n})")
    herdr("agent", "prompt", pane, "/exit")
    time.sleep(8)
    start = herdr("agent", "start", name, "--kind", "claude", "--pane", pane, "--timeout", "120000", "--", "--model", MODEL)
    if start.returncode != 0:
        note(f"could not start the new driver: {start.stderr.strip()[:200]}; leaving it for the human")
        return False
    herdr("agent", "prompt", name, f"/team driver {map_ref} (the watchdog closed the previous driver, session "
                                   f"{old_sid}, because it was stuck: {reason}; take over its claim on the map)")
    return True


def main():
    if len(sys.argv) == 2 or sys.argv[1:2] in (["-h"], ["--help"]):
        sys.exit(__doc__)
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
                note(f"driver in {pane} is stuck ({reason}) and {MAX_RESTARTS} restarts are used up; leaving it for the human")
                restarts[pane] += 1
                continue
            restarts[pane] = restarts.get(pane, 0) + 1
            old = ((agent.get("agent_session") or {}).get("value") or "?")[:8]
            name = f"{base}-{pane.replace(':', '')}-r{restarts[pane]}"
            restart(pane, name, map_ref, reason, old, restarts[pane])
            seen = os.path.getsize(LOG) if os.path.exists(LOG) else 0
        time.sleep(EVERY)


if __name__ == "__main__":
    main()
