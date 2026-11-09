#!/usr/bin/env python3
"""delete-guard: a Claude Code PreToolUse hook for Bash. A recursive delete (rm -r in any form, find -delete,
rsync --delete, shutil.rmtree, trash --empty), anywhere in the command, ssh quotes included, is put to the human as a
permission prompt, as before. If nobody answers for 15 minutes (an unattended session waits forever otherwise), a timer
declines it (Esc in the session's herdr pane) and tells the agent to use `trash <path>`, which can be undone.

Free to run without asking: targets under /tmp or /private/tmp, and __pycache__ folders. `git rm` is left to git.
The timer acts only when the call is still unanswered in the session's transcript and herdr shows the pane waiting on
a prompt; outside herdr the prompt simply waits. It never approves anything. Actions: ~/.local/state/delete-guard.log.

Install in ~/.claude/settings.json under "hooks":
  "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 ~/research-harness/tools/delete-guard.py"}]}]
"""
import json
import os
import re
import subprocess
import sys
import time

WAIT_MIN = float(os.environ.get("DELETE_GUARD_WAIT_MIN", "15"))       # env: tests
LOG = os.path.expanduser("~/.local/state/delete-guard.log")
FREE = ("/tmp/", "/private/tmp/")
RM = re.compile(r"(?:^|[\s;&|('\"`])rm((?:\s+-[-\w]+)+)\s+([^;&|)\n]*)")
OTHER = {"find -delete": re.compile(r"\bfind\b[^;&|\n]*\s-delete\b"),
         "rsync --delete": re.compile(r"\brsync\b[^;&|\n]*\s--delete"),
         "shutil.rmtree": re.compile(r"\bshutil\.rmtree\b"),
         "trash --empty": re.compile(r"\btrash(?:\.py)?\s+--empty\b")}
TOLD = ("delete-guard: your recursive delete waited {m:g} min for the human and was declined. Move what you meant to "
        "delete with `trash <path>` (it can be undone and prints where it went; over ssh, where ~/.local/bin is often not on PATH, call it as ~/.local/bin/trash). If it must really be deleted, record "
        "that in the ticket for the human, and carry on with other work.")


def note(text):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  {text}\n")


def recursive_delete(cmd):
    """What makes this command a recursive delete, or None."""
    for m in RM.finditer(cmd):
        if re.search(r"\bgit\s+$", cmd[:m.start() + 1]):
            continue                                                  # git rm: the files stay in git's history
        if not re.search(r"(?:^|\s)-(?!-)\w*[rR]|--recursive\b", m.group(1)):
            continue
        targets = [t.strip("'\"") for t in m.group(2).split()]
        if targets and all(t.startswith(FREE) or os.path.basename(t.rstrip("/")) == "__pycache__" for t in targets):
            continue
        return "rm -r"
    return next((name for name, pat in OTHER.items() if pat.search(cmd)), None)


def answered(transcript, tool_use_id, cmd):
    """True once the call has a result in the transcript (approved, denied or run). Found by its id, else its command."""
    last, done = None, set()
    try:
        with open(transcript, errors="replace") as f:
            for line in f:
                if '"tool_use"' not in line and '"tool_result"' not in line:
                    continue
                try:
                    content = (json.loads(line).get("message") or {}).get("content") or []
                except ValueError:
                    continue
                for x in content if isinstance(content, list) else []:
                    if not isinstance(x, dict):
                        continue
                    if x.get("type") == "tool_use" and (x.get("id") == tool_use_id if tool_use_id else
                                                         (x.get("input") or {}).get("command") == cmd):
                        last = x.get("id")
                    elif x.get("type") == "tool_result":
                        done.add(x.get("tool_use_id"))
    except OSError:
        return True                                                   # no transcript: never act blind
    return last is None or last in done                               # a call it cannot find counts as answered


def herdr(*args):
    return subprocess.run(["herdr", *args], capture_output=True, text=True, timeout=60)


def timer(pane, transcript, tool_use_id, cmd):
    time.sleep(WAIT_MIN * 60)
    if answered(transcript, tool_use_id, cmd):
        return
    try:
        agents = json.loads(herdr("agent", "list").stdout or "{}").get("result", {}).get("agents", [])
    except (ValueError, subprocess.SubprocessError):
        return
    a = next((a for a in agents if a.get("pane_id") == pane), None)
    if not a or a.get("agent_status") != "blocked":
        note(f"{pane}: a delete is unanswered but the pane is not waiting on a prompt ({(a or {}).get('agent_status')}); left alone")
        return
    herdr("pane", "send-keys", pane, "esc")                           # Claude Code's "No" on its permission prompt
    time.sleep(5)
    herdr("agent", "prompt", pane, TOLD.format(m=WAIT_MIN))
    note(f"{pane}: declined after {WAIT_MIN:g} min and told to use trash: {cmd[:200]}")


def main():
    if sys.argv[1:2] == ["--timer"]:
        return timer(*sys.argv[2:6])
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if os.path.exists(LOG + ".debug"):                                # touch it to see that the hook runs at all
        note(f"saw {data.get('tool_name')}: {cmd[:80]!r} (fields: {', '.join(sorted(data))})")
    why = data.get("tool_name") == "Bash" and recursive_delete(cmd)
    if not why:
        return
    pane, later = os.environ.get("HERDR_PANE_ID"), ""
    if pane and data.get("transcript_path"):
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as out:
            subprocess.Popen([sys.executable, os.path.realpath(__file__), "--timer", pane, data["transcript_path"],
                              data.get("tool_use_id") or "", cmd], start_new_session=True, stdin=subprocess.DEVNULL,
                             stdout=out, stderr=out)
        later = f" Unanswered for {WAIT_MIN:g} min, it is declined and the agent is told to use `trash`."
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "ask",
        "permissionDecisionReason": f"Recursive delete ({why}): deleting data needs the human.{later}"}}))


if __name__ == "__main__":
    main()
