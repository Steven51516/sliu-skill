#!/usr/bin/env python3
"""team-watch: the watch tab's supervisor. Prints the driver's log as it grows, resumes a driver or worker stopped by
Claude's safeguards on Sonnet 5.5, and passes what needs the human to their alert command, once each.

Usage (from the project folder, inside herdr):  team-watch                 every driver on scratch/agents/roster.md
                                                team-watch <map> <driver pane> [agent name]   one driver
team-up starts it; after starting a team any other way, run it once in a spare tab: `caffeinate -dimsu team-watch`.

Every 5 minutes it looks at each driver's pane. A driver whose map is closed is skipped. A driver waiting on a
permission prompt (`blocked`) needs the human and is left alone.

Stopped by a safeguard: the driver is idle and its session ended on a safeguard stop (Claude Code then waits for a human
to retry or switch model). A session that Claude Code moved to its fallback model after a flag (its last reply came
from Opus 4.x) is not exited: the watch types `/model` and `/effort` into it (and answers Claude Code's question about
the switch), so its background work goes on, and puts
the saved defaults those commands change back to what they were. It is exited and its own session resumed in the same pane on Sonnet 5.5 at high effort
(`claude --resume <session> --model sonnet --effort high`), keeping its whole chat, then told to continue. It stays on
Sonnet 5.5 until the human switches it back. At most 3 resumes per driver per run.

Silent: the driver is idle and its own session has written nothing for 90 minutes (longer than its longest sleep, an
hour), so its /loop has ended. Silence is read from that session's transcript, never from the shared driver.log, where
another driver's line would hide it. A silent driver is not restarted and not prompted (a driver often waits on purpose,
and until 11-10 all 15 resumes were of such drivers, each moved to Sonnet): the human gets one alert per silence. A
driver whose map is paused is not reported.

Questions for the human go to the alert command once each: every open grilling or prototype ticket of a map that is neither
paused nor closed, and every new driver.log line that says `needs-you` without naming such a ticket; that line's
driver is also told once to file the question as a ticket. What
was sent is kept in scratch/agents/team-watch.pushed, so restarting the watch sends nothing twice.

A Codex driver has no /loop: the watchdog is its schedule. It types `tick` into the driver's pane once the pane has been
idle, with no change of state and no tick, for 25 minutes. A Codex driver is never resumed; one whose pane does not move
for 90 minutes despite the ticks is reported once.

Workers (the Claude tabs team-worker opened in the watched drivers' workspaces) are checked too: one whose reply Claude's
safeguards stopped is resumed once with `team-worker --rescue`, so it does not wait for the driver's next pass (up to an
hour). Stopped again, or stopped before this watch started, it is left to its driver, which gets one line. A worker
whose ticket is closed and which has sat idle for 30 minutes has its tab closed. One that still holds a background
command is asked by team-worker to stop it and tried again 10 minutes later; kept if it holds one after that.

An alert runs the command in ~/.config/research-harness/notify, if that file exists, with the message as its last
argument and its kind in RH_EVENT: `question`, `silent`, `gave-up` or `slept` (the watch found its clock had jumped: the
machine or its VM was asleep). An alert the command could not deliver is marked in scratch/agents/alerts.log and shown
by `research-status --now`. Your command routes it (a phone push, a sound, a
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
ALERTS = os.path.join("scratch", "agents", "alerts.log")    # time, kind, delivered | undelivered, text (tab-separated)
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
    it (e.g. extras/notify.py, the `alerts` preset; or `ntfy publish <topic>`). Whether the command got it through
    (exit 0) is a line in scratch/agents/alerts.log, which `research-status --now` reads: an alert that failed must not
    fail silently (15 of 15 did, 11-11..11-20, from a container without the Mac's programs)."""
    note(text)
    try:
        cmd = shlex.split(open(NOTIFY).read().strip())
    except (OSError, ValueError):
        return                                        # no alert command: driver.log is the record, by choice
    if not cmd:
        return
    try:
        rc = subprocess.run([os.path.expanduser(c) for c in cmd] + [text], capture_output=True, timeout=60,
                            env={**os.environ, "RH_EVENT": kind}).returncode
    except (OSError, subprocess.SubprocessError) as e:
        rc = f"{type(e).__name__}"
    with open(ALERTS, "a") as f:
        f.write(f"{now()}\t{kind}\t{'delivered' if rc == 0 else 'undelivered'}\t{text[:300]}\n")
    if rc != 0:
        note(f"ALERT NOT DELIVERED ({cmd[0]}: {rc}); it is only in this log. Check the alert command: research-preset")


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
    """Each open question for the human (a grilling or prototype ticket, an old map's Needs-you item) once; `waiting`
    leaves paused and closed maps out. More than 3 new at once (a first run) go as one alert."""
    new = [(mid, text, f"ask {key}") for mid, text, key in tracker.waiting(maps) if f"ask {key}" not in pushed]
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


def driver_for(line, drivers):
    """The driver pane a log line belongs to: the one whose map id the line names, or the only driver."""
    ids = {p: os.path.basename(str(label).rstrip("/")).split("-")[0] for p, label in drivers.items()}
    hits = [p for p, i in ids.items() if i and re.search(rf"\b{re.escape(i)}\b", line, re.I)]
    return hits[0] if len(hits) == 1 else next(iter(drivers)) if len(drivers) == 1 else None


def push_needs(lines, pushed, covered=(), drivers=None):
    """Each new driver.log line that says `needs-you` and names no open question ticket: once to the human, and once to
    its driver, to file it. Only a ticket shows as waiting on the human and closes with their answer; an ask that lived
    in a pane and this log was dropped twice on 2026-11-20."""
    for line in lines:
        m = NEEDS.search(line)
        key = "log " + STAMP.sub("", line)[:160]
        if not m or "watchdog:" in line or NO_NEEDS.search(line) or key in pushed or \
                any(c.lower() in line.lower() for c in covered):
            continue
        push_once(key, "no ticket yet; driver.log: …" + line[max(0, m.start() - 160):m.start() + 240], pushed, "question")
        pane = driver_for(line, drivers or {})
        if pane:
            herdr("agent", "prompt", pane, f"watchdog: your driver.log line \"…{line[m.start():m.start() + 70]}…\" names no open "
                                           f"grilling ticket. A question for the human is a ticket first (`to-tickets`, type "
                                           f"grilling): only then does it show as waiting on them, and their answer closes it.")


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


FALLBACK = re.compile(r"opus-4")       # the model Claude Code switches a flagged session to (switchModelsOnFlag)


def latest_model(session_id):
    """The model of the session's last reply, from the end of its transcript; None when it cannot be told."""
    path = transcript(session_id)
    if not path:
        return None
    with open(path, "rb") as f:
        f.seek(max(0, f.seek(0, 2) - (512 << 10)))
        lines = f.read().split(b"\n")
    for line in reversed(lines):
        if b'"type":"assistant"' not in line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        model = (d.get("message") or {}).get("model")
        if model and model != "<synthetic>" and not d.get("isSidechain"):
            return model
    return None


WORKED = {}                            # pane -> when this watch last saw its agent working


def current(agent, session_id):
    """True when the transcript herdr names for this pane is the one the session is writing now: it was written since
    this watch last saw the agent work. herdr can keep an old session id after a resume, and that old transcript's
    last reply is not the session's model (2026-11-25: a driver on Sonnet was exited for a stale Opus 4.8 line)."""
    seen, path = WORKED.get(agent.get("pane_id")), transcript(session_id)
    return bool(seen and path and os.path.getmtime(path) >= seen - 120)


SETTINGS = os.path.expanduser("~/.claude/settings.json")
SWITCHED = {}                          # pane -> the session it was switched in, so one fallback gets one switch


def user_defaults():
    try:
        d = json.load(open(SETTINGS))
    except (OSError, ValueError):
        return None
    return {k: v for k, v in d.items() if k == "model" or "effort" in k.lower()}


def screen_tail(pane, n=14):
    """The last lines on a pane's screen: where Claude Code shows a question."""
    out = herdr("agent", "read", pane, timeout=20).stdout or ""
    try:
        res = json.loads(out).get("result", {})
        out = res.get("text") or res.get("screen") or res.get("content") or ""
    except (ValueError, AttributeError):
        pass
    return [line.rstrip() for line in out.splitlines() if line.strip()][-n:]


def input_box(tail):
    """What Claude Code's input box shows: the last box between ─── rules, starting at ❯ ("" for an empty one)."""
    rules = [i for i, line in enumerate(tail) if line.strip() and set(line.strip()) <= {"─"}]
    box = tail[rules[-2] + 1:rules[-1]] if len(rules) >= 2 else []
    if not box or not box[0].lstrip().startswith("❯"):
        return ""
    text = "\n".join([box[0].split("❯", 1)[1]] + box[1:]).strip()
    return "" if re.fullmatch(r'Try ".*"', text) else text


def typed(pane, command):
    """Type a slash command into a session and see it through. Two things went wrong when it was only typed:
    - Claude Code asks before a /model that changes the model of a conversation it has cached ("Switch model? ...
      > 1. Yes, switch to Sonnet 5.5  2. No, go back"); with nobody to answer, the session sat at the question and the
      /effort typed next was refused (2026-11-27). Enter on the marked Yes answers it;
    - a command can be left typed and unsent, and the next one was then sent with it as one line, "/model
      claude-sonnet-5-5/effort high" (2026-11-26). Enter sends a command still in the box, and what the box showed
      before is cleared first.
    False when the session is left at a question: one with another choice marked, or another question."""
    left = input_box(screen_tail(pane))
    if left:
        for _ in range(left.count("\n") + 1):
            herdr("agent", "send-keys", pane, "ctrl+u", "backspace")      # Ctrl+U clears a line, ⌫ joins it to the one before
        note(f"{pane}: its input box showed {left[:80]!r} before `{command}` was typed: cleared")
    herdr("agent", "prompt", pane, command)
    for look in range(12):
        time.sleep(1.5)
        tail = screen_tail(pane)
        if any("Switch model?" in line for line in tail):
            if not any("❯" in line and "Yes" in line for line in tail):
                return False
            herdr("pane", "send-keys", pane, "Enter")
        elif command in input_box(tail):
            herdr("pane", "send-keys", pane, "Enter")
        elif look and (agent_at(pane) or {}).get("agent_status") != "blocked":
            return True
    return False


def switch_in_place(pane, who, reason, session):
    """Move a fallen-back session to Sonnet 5.5 at high without exiting it, so its background work goes on: `/model`
    and `/effort` typed into it, and Claude Code's question about the switch answered. Both commands also save the
    user's default for new sessions, so the saved model and effort are put back to what they were. Once per fallback;
    True when it acted. A session left at a question is the human's to answer: they are told."""
    if SWITCHED.get(pane) == session:
        return False
    SWITCHED[pane] = session
    before = user_defaults()
    took = typed(pane, "/model claude-sonnet-5-5") and typed(pane, f"/effort {EFFORT}")
    time.sleep(2)
    after, restored = user_defaults(), ""
    if before is not None and after is not None and before != after:
        try:
            d = json.load(open(SETTINGS))
            for k in set(before) | set(after):
                if k in before:
                    d[k] = before[k]
                else:
                    d.pop(k, None)
            with open(SETTINGS + ".tmp", "w") as f:
                json.dump(d, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.replace(SETTINGS + ".tmp", SETTINGS)
            restored = "; saved defaults put back"
        except (OSError, ValueError) as e:
            restored = f"; could not put the saved defaults back ({e})"
    if took:
        note(f"{who} in {pane}: {reason}; switched in place to Sonnet 5.5 at {EFFORT} (/model, /effort){restored}")
    else:
        alert(f"{who} in {pane}: {reason}; the switch to Sonnet 5.5 at {EFFORT} waits at a question in its tab that "
              f"the watch does not answer: answer it there{restored}", "question")
    return True


def stuck_reason(agent):
    """Why an idle Claude session should be resumed on Sonnet 5.5: a safeguard stopped its last reply, or Claude Code
    moved it to its fallback model after a flag (it keeps working there, on a model nobody chose)."""
    if not agent or agent.get("agent_status") in ("working", "blocked"):
        return None
    session = (agent.get("agent_session") or {}).get("value")
    if ended_on_safeguard_stop(session):
        return "its last reply was stopped by Claude's safeguards"
    model = latest_model(session)
    if model and FALLBACK.search(model) and current(agent, session):
        return f"it fell back to {model}"
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
    for _ in range(10):                # Claude Code may ask "Background work is running: exit and stop tasks?"
        time.sleep(2)
        a = agent_at(pane)
        if not a:
            break
        if a.get("agent_status") == "blocked":
            break
    else:
        a = agent_at(pane)
    if a:                                                 # at the dialog, or it never took /exit
        herdr("pane", "send-keys", pane, "esc")           # Stay: nothing the driver started is stopped
        note(f"driver in {pane} did not exit (background work is running, which an exit would stop): left as it is")
        return False
    name = re.sub(r"[^a-z0-9_-]", "", name.lower())[:32]      # herdr: lowercase letters, digits, - or _; pane ids may be w1F:p3K
    for _ in range(6):                 # the session is gone now: this start has to work, or the human has to know
        start = herdr("agent", "start", name, "--kind", "claude", "--pane", pane, "--timeout", "120000",
                      "--", "--resume", session, "--model", MODEL, "--effort", EFFORT)
        if start.returncode == 0:
            break
        time.sleep(5)
    else:
        alert(f"driver for {map_ref} in {pane} was exited to resume it on Sonnet 5.5 and the restart failed "
              f"({(start.stderr or start.stdout).strip()[:160]}). It is NOT running: in that pane run "
              f"`claude --resume {session} --model {MODEL} --effort {EFFORT}`", "gave-up")
        return False
    herdr("agent", "prompt", name, f"continue: the watchdog resumed this session on Sonnet 5.5 ({reason}). Pick up the "
                                   f"pass for {map_ref} where you stopped, but before repeating a dispatch, launch or other "
                                   f"outside action, check driver.log, the tickets and the server for what already ran; "
                                   f"no summary, end with one line naming the file; hand biology steps to their delegate "
                                   f"by pointer.")
    return True


CLOSE_AFTER_MIN, CLOSE_RETRY_MIN, CLOSE_LATER = 30, 10, 3   # CLOSE_LATER: team-worker --close says "try again later"


def close_finished(pane, tid, agent, closed, idle_since, kept):
    """Close a worker's tab once its ticket is resolved, parked or superseded and it has sat idle for CLOSE_AFTER_MIN:
    every open tab is a live process, and drivers left them open (8 of 19 on 2026-11-24). team-worker --close backs
    out when the session still has background work and asks the worker to stop it (exit 3: tried again
    CLOSE_RETRY_MIN later); a tab it leaves for any other reason is kept and noted once. `kept` holds, per pane, when
    to try again, or None for a tab that is left."""
    if tid not in closed or agent.get("agent_status") in ("working", "blocked") or kept.get(pane, 0) is None:
        idle_since.pop(pane, None)
        return
    if pane in kept:
        if time.time() < kept[pane]:
            return
    elif (time.time() - idle_since.setdefault(pane, time.time())) / 60 < CLOSE_AFTER_MIN:
        return
    r = subprocess.run([sys.executable, TEAM_WORKER, "--close", tid], capture_output=True, text=True, timeout=180)
    why = (r.stderr or r.stdout).strip()[:220]
    if r.returncode == 0:
        kept.pop(pane, None)
        note(f"closed the tab of {tid} ({pane}): its ticket is closed and it sat idle {CLOSE_AFTER_MIN} min")
    elif r.returncode == CLOSE_LATER:
        kept[pane] = time.time() + CLOSE_RETRY_MIN * 60
        note(f"the tab of {tid} ({pane}) is not closed yet, trying again in {CLOSE_RETRY_MIN} min: {why}")
    else:
        kept[pane] = None
        note(f"left the tab of {tid} ({pane}) open: {why}")


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
    """The driver pane whose map shares the ticket's prefix (M12 for M12-09)."""
    prefix = tid.split("-")[0].upper()
    return next((p for p, m in drivers.items() if os.path.basename(m.rstrip("/")).split("-")[0].upper() == prefix), None)


def check_worker(pane, tid, agent, drivers, rescued):
    """Rescue a worker stopped by Claude's safeguards once; after that, or for a stop older than this watch, tell its driver."""
    session = (agent.get("agent_session") or {}).get("value")
    reason = None if rescued.get(pane) == "left" else stuck_reason(agent)
    if not reason:
        return
    if "fell back" in reason:              # still running, only on the wrong model: switched where it is
        switch_in_place(pane, f"worker {tid}", reason, session)
        return
    stopped = "safeguards" in reason
    if pane in rescued:
        why = "again, after its Sonnet rescue"
    elif stopped and os.path.getmtime(transcript(session)) < STARTED:
        why = "before this watch started"
    else:
        rescued[pane] = "rescued"
        note(f"worker {tid} in {pane}: {reason}; resuming it on Sonnet 5.5 (team-worker --rescue)")
        r = subprocess.run([sys.executable, TEAM_WORKER, "--rescue", tid], capture_output=True, text=True, timeout=300)
        if r.returncode == 0:
            return
        why = f"the rescue failed: {(r.stderr or r.stdout).strip()[:200]}"
    rescued[pane] = "left"
    driver = None if "background work" in why else driver_of(tid, drivers)   # nothing for its driver to do
    msg = f"worker {tid} in {pane}: {reason} ({why}); left to {'its driver ' + driver if driver else 'the human'}"
    note(msg) if driver or "background work" in why else alert(msg, "gave-up")
    if driver:
        herdr("agent", "prompt", driver, f"watchdog: worker {tid} in {pane}: {reason} ({why}); "
                                         f"read its screen and hand that step to its delegate (docs/agents/delegation.md)")


def handle_stuck(pane, map_ref, agent, base, restarts, fails, given_up):
    """Resume a Claude driver stopped by a safeguard. Only a resume that started counts toward MAX_RESTARTS; a start that failed (the pane
    busy, 10-31: 4 such failures used up both drivers' resumes) is tried again next cycle, at most MAX_RESTARTS times in a
    row. Giving up pushes to the human's phone. True when it acted."""
    reason = stuck_reason(agent)
    if not reason:
        return False
    session = (agent.get("agent_session") or {}).get("value")
    if "fell back" in reason:              # still running, only on the wrong model: no exit, no resume
        switch_in_place(pane, f"driver for {map_ref}", reason, session)
        return True
    if pane in given_up:
        return True
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


def show_log(seen, pushed, covered=(), drivers=None):
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
    push_needs(lines, pushed, covered, drivers)
    return seen + len(chunk)


def main():
    if len(sys.argv) == 2 or sys.argv[1:2] in (["-h"], ["--help"]):
        sys.exit(__doc__)
    lock = single()   # noqa: F841 (held until exit)
    fixed = {sys.argv[2]: (sys.argv[1], "")} if len(sys.argv) >= 3 else None
    base = sys.argv[3] if len(sys.argv) > 3 else "driver"
    restarts, fails, given_up, ticks, moved, rescued = {}, {}, set(), {}, {}, {}
    idle_since, kept = {}, {}
    pushed = load_pushed()
    seen = os.path.getsize(LOG) if os.path.exists(LOG) else 0
    print(f"{now()}  watching " + (f"the driver in {sys.argv[2]}" if fixed else "every driver on the roster"), flush=True)
    beat = time.time()
    while True:
        gap = (time.time() - beat) / 60
        if gap > EVERY / 60 + 10:      # the clock jumped: this machine (or its VM) was asleep or stopped
            alert(f"this machine was asleep or stopped for {gap:.0f} min until {now()}: wake-ups and waits inside "
                  f"sessions did not fire; check each driver and worker", "slept")
        os.utime(LOCK)        # a session that cannot list processes (Codex's sandbox) reads this file's age instead
        told = set(pushed)
        maps = load_maps()
        roster = {pane: map_state(maps, ref, name) + (ref,) for pane, (ref, name) in (fixed or roster_drivers()).items()}
        drivers, spaces = {pane: map_id or ref for pane, (map_id, _, ref) in roster.items()}, set()
        push_questions(maps, pushed)
        seen = show_log(seen, pushed, asked(maps), {p: l for p, l in drivers.items() if roster[p][1] != "closed"})
        for pane, (map_id, state, ref) in roster.items():
            label = drivers[pane]
            agent = agent_at(pane)
            spaces.add((agent or {}).get("workspace_id"))
            if not agent or state == "closed":
                continue
            if agent.get("agent") == "codex":
                tick(pane, agent, ticks, moved, pushed)
            elif not handle_stuck(pane, label, agent, base, restarts, fails, given_up) and state != "paused":
                check_silence(pane, label, agent, pushed)
        try:
            for a in json.loads(herdr("agent", "list", timeout=20).stdout or "{}").get("result", {}).get("agents", []):
                if a.get("agent_status") == "working":
                    WORKED[a.get("pane_id")] = time.time()
        except (ValueError, subprocess.SubprocessError):
            pass
        closed = {str(k.get("id")) for m in maps for k in m["_tickets"] if tracker.status_of(k) in tracker.CLOSED}
        for pane, (tid, agent) in workers(spaces - {None}).items():
            check_worker(pane, tid, agent, drivers, rescued)
            close_finished(pane, tid, agent, closed, idle_since, kept)
        if pushed != told:
            save_pushed(pushed)
        beat = time.time()
        time.sleep(EVERY)


if __name__ == "__main__":
    main()
