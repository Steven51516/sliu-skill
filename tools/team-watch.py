#!/usr/bin/env python3
"""team-watch: the watch tab's supervisor. Prints the driver's log as it grows, and replaces a stuck driver with a fresh
one on Sonnet 5.5, so a map keeps moving while nobody is watching.

Usage (from the project folder, inside herdr; team-up starts it):  team-watch <map> <driver pane> [agent name]

Every 5 minutes it looks at the driver's pane. The driver is stuck when it is idle and either the safeguard-stop hook
logged that it let this session stop (Claude's safeguards stopped its replies twice), or no pass has been logged in
scratch/agents/driver.log for 90 minutes (longer than the driver's longest sleep, an hour). A driver waiting on a
permission prompt (`blocked`) needs the human and is left alone. A stuck driver is closed and a fresh one started on
Sonnet 5.5 in the same pane with `/team driver <map>`; the map and its tickets hold its state, so it picks up from
there. At most 3 restarts per run; every action is logged to driver.log.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time

EVERY, STALE_MIN, MAX_RESTARTS, MODEL = 300, 90, 3, "sonnet"
LOG = os.path.join("scratch", "agents", "driver.log")
SAFEGUARD_LOG = os.path.join("scratch", "agents", "safeguard-stop.log")


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


def stuck_reason(agent):
    if not agent or agent.get("agent_status") in ("working", "blocked"):
        return None
    last_pass = os.path.getmtime(LOG) if os.path.exists(LOG) else 0
    sid = ((agent.get("agent_session") or {}).get("value") or "")[:8]
    if sid and os.path.exists(SAFEGUARD_LOG) and os.path.getmtime(SAFEGUARD_LOG) > last_pass:
        with open(SAFEGUARD_LOG) as f:
            if any(sid in line and "letting it stop" in line for line in f.readlines()[-50:]):
                return "Claude's safeguards stopped its replies twice"
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
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    map_ref, pane = sys.argv[1], sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else "driver"
    restarts, seen = 0, os.path.getsize(LOG) if os.path.exists(LOG) else 0
    print(f"{now()}  watching the driver in {pane} for {map_ref}", flush=True)
    while True:
        if os.path.exists(LOG) and os.path.getsize(LOG) > seen:     # show the driver's log as it grows
            with open(LOG) as f:
                f.seek(seen)
                sys.stdout.write(f.read())
                sys.stdout.flush()
            seen = os.path.getsize(LOG)
        agent = agent_at(pane)
        reason = stuck_reason(agent)
        if reason:
            if restarts >= MAX_RESTARTS:
                note(f"driver in {pane} is stuck ({reason}) and {MAX_RESTARTS} restarts are used up; leaving it for the human")
                return
            restarts += 1
            old = ((agent.get("agent_session") or {}).get("value") or "?")[:8]
            if not restart(pane, f"{name}-r{restarts}", map_ref, reason, old, restarts):
                return
            seen = os.path.getsize(LOG) if os.path.exists(LOG) else 0
        time.sleep(EVERY)


if __name__ == "__main__":
    main()
