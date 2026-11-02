#!/usr/bin/env python3
"""team-roster-hook: a Claude Code SessionStart hook for team sessions. A session whose herdr pane is on the project's
team roster (scratch/agents/roster.md) is told, when it starts, resumes or compacts, that its session name may have
changed and to rewrite its roster line first, so the other sessions can still reach it (2026-11-02: three names changed
after a restart and the desk rebuilt the roster by hand). Prints nothing for any other session.

Install once, in ~/.claude/settings.json under hooks.SessionStart:
  {"type": "command", "command": "python3 ~/research-harness/tools/team-roster-hook.py", "timeout": 10}
"""
import json
import os
import sys


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    pane = os.environ.get("HERDR_PANE_ID")
    roster = os.path.join(event.get("cwd") or os.getcwd(), "scratch", "agents", "roster.md")
    if not pane or not os.path.exists(roster):
        return
    lines = [l.strip() for l in open(roster) if f"| {pane} |" in l]      # the latest line for this pane wins
    if not lines:
        return
    role = lines[-1].split("|")[0].strip()
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": (
        f"This session (herdr pane {pane}) is the {role} on this project's team roster, scratch/agents/roster.md. Its "
        f"session name may have changed ({event.get('source', 'start')}): learn your current name (the ListAgents tool); "
        f"if it differs from your roster line, rewrite that line before anything else and tell the other roles your new "
        f"name.")}}))


if __name__ == "__main__":
    main()
