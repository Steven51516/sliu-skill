#!/usr/bin/env python3
"""notify: route an alert to your channels by its kind. team-watch runs your alert command with the message as its last
argument and the kind in RH_EVENT: `question` (an open question or a needs-you line), `silent` (a driver's loop ended),
`gave-up` (a resume or rescue that failed). The `alerts` preset makes this script that command.

  notify.py <message>            send it on the channels ~/.config/research-harness/notify.json names for its kind
  notify.py --test [kind]        send a test message (kind: question by default)
  notify.py --dry-run <message>  print the commands it would run

notify.json: {"channels": {<name>: {"run": "<command>", "message": true|false}}, "events": {<kind>: [<channel>...]}}.
A channel's command gets the message as its last argument when "message" is true. A kind with no line uses "other".
If no channel of the kind succeeds, a banner is tried (macOS). Every send is a line in ~/.local/state/notify.log.
Optional (README, "Presets and extras"): no skill relies on it.
"""
import json
import os
import shlex
import subprocess
import sys
import time

CONFIG = os.path.expanduser("~/.config/research-harness/notify.json")
LOG = os.path.expanduser("~/.local/state/notify.log")
BANNER = {"run": 'osascript -e "on run argv" -e "display notification (item 1 of argv) with title \\"research\\"" '
                 '-e "end run"', "message": True}


def log(text):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}  {text}\n")


def command(channel, message):
    cmd = [os.path.expanduser(t) for t in shlex.split(channel["run"])]
    return cmd + [message] if channel.get("message", True) else cmd


def send(kind, message, dry=False):
    try:
        cfg = json.load(open(CONFIG))
    except (OSError, ValueError) as e:
        cfg = {"channels": {}, "events": {}}
        log(f"{kind}: no usable {CONFIG} ({e}); banner only")
    channels, events = cfg.get("channels", {}), cfg.get("events", {})
    names = events.get(kind, events.get("other", []))
    ok = False
    for name in names + ([] if "banner" in names else ["banner"]):
        if name == "banner" and ok:
            break                                     # the fallback banner only when nothing else got through
        ch = channels.get(name) or (BANNER if name == "banner" else None)
        if not ch:
            log(f"{kind}: unknown channel `{name}`")
            continue
        cmd = command(ch, message)
        if dry:
            print(" ".join(shlex.quote(c) for c in cmd))
            ok = True
            continue
        try:
            rc = subprocess.run(cmd, capture_output=True, timeout=60, stdin=subprocess.DEVNULL).returncode
        except (OSError, subprocess.SubprocessError) as e:
            rc = f"failed: {e}"
        log(f"{kind} -> {name}: {rc}: {message[:120]}")
        ok = ok or rc == 0


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        sys.exit(__doc__)
    if a[0] == "--test":
        kind = a[1] if len(a) > 1 else "question"
        return send(kind, f"research-harness: test alert ({kind})")
    if a[0] == "--dry-run":
        return send(os.environ.get("RH_EVENT") or "other", " ".join(a[1:]), dry=True)
    send(os.environ.get("RH_EVENT") or "other", " ".join(a))


if __name__ == "__main__":
    main()
