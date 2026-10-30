#!/usr/bin/env python3
"""ask-human: put a question with fixed answers to the human; in Moshi mode it goes to their phone as buttons.

  ask-human "Keep the 10x LR on L4's distogram head?" Yes No        the first option is your pick
  ask-human --mode [on|off]                                          show or set Moshi mode

Moshi mode on: the question becomes a Moshi card on the human's phone, one button per option plus "I'll reply in text",
and this returns at once, so the session keeps working. A waiter in the background types the answer into the asking
session's herdr pane when it comes: `Answer from the human (phone): <option> (to: <question>)`. Mode off, outside herdr,
or Moshi unreachable: it says so and exits 3, and the session asks in plain text as usual.

Every question and its outcome is a line in ~/.config/research-harness/asks.jsonl (the app's Inbox lists the open ones
and can answer them too: it stops the waiter by its pid and types the answer itself).
"""
import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid

DIR = os.environ.get("ASK_HUMAN_DIR") or os.path.expanduser("~/.config/research-harness")   # env: tests
CONF, LOG = os.path.join(DIR, "ask.json"), os.path.join(DIR, "asks.jsonl")
OTHER = "I'll reply in text"
OFF = 3


def moshi_mode(value=None):
    if value is not None:
        os.makedirs(DIR, exist_ok=True)
        with open(CONF, "w") as f:
            json.dump({"moshi": value}, f)
    try:
        with open(CONF) as f:
            return bool(json.load(f).get("moshi"))
    except (OSError, ValueError):
        return False


def log(rec):
    os.makedirs(DIR, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(dict(rec, t=time.time())) + "\n")


def moshi_hook():
    return os.environ.get("MOSHI_HOOK") or shutil.which("moshi-hook") or os.path.expanduser("~/.local/bin/moshi-hook")


def deliver(pane, text):
    r = subprocess.run(["herdr", "agent", "prompt", pane, text], capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def wait(q):
    """The background half: wait for the phone, then type the outcome into the asking session."""
    cmd = [moshi_hook(), "ask", "--require-remote", "--timeout", q["timeout"], "--source", q["source"], "--label", q["label"]]
    for o in q["options"]:
        cmd += ["--option", o]
    r = subprocess.run(cmd + [q["question"]], capture_output=True, text=True)
    answer = r.stdout.strip()
    if r.returncode == 0 and answer == OTHER:
        state, msg = "text", f"The human will answer in text (to: {q['question']}). Wait for their message."
    elif r.returncode == 0:
        state, msg = "answered", f"Answer from the human (phone): {answer} (to: {q['question']})"
    elif r.returncode == 1:
        state, msg = "dismissed", f"The human dismissed your phone question without choosing (to: {q['question']}). Ask in plain text if it still matters."
    elif r.returncode == 3:
        state, msg = "timeout", f"No answer on the phone within {q['timeout']} (to: {q['question']}). Ask in plain text if it still matters."
    else:
        state, msg = "failed", f"Your phone question could not be delivered (to: {q['question']}): {(r.stderr or r.stdout).strip()[:200]}. Ask in plain text."
    log({"id": q["id"], "state": state, "answer": answer if state == "answered" else None, "delivered": deliver(q["pane"], msg)})


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("question", nargs="?")
    ap.add_argument("options", nargs="*", help="2-5 answers, your pick first")
    ap.add_argument("--mode", nargs="?", const="show", choices=["show", "on", "off"], help="show or set Moshi mode")
    ap.add_argument("--from", dest="label", help="who asks, shown on the card (default: the project folder's name)")
    ap.add_argument("--pane", default=os.environ.get("HERDR_PANE_ID"), help="where the answer goes (default: this herdr pane)")
    ap.add_argument("--timeout", default="24h")
    ap.add_argument("--wait", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.wait:
        return wait(json.loads(a.wait))
    if a.mode:
        on = moshi_mode(None if a.mode == "show" else a.mode == "on")
        print(f"Moshi mode is {'on' if on else 'off'}")
        return
    if not a.question or not 2 <= len(a.options) <= 5:
        ap.error("give a question and 2-5 options, your pick first")
    if not moshi_mode():
        print("Moshi mode is off: ask the human in plain text.")
        sys.exit(OFF)
    if not a.pane:
        print("Not in a herdr pane, so the answer could not come back: ask the human in plain text.")
        sys.exit(OFF)
    if subprocess.run([moshi_hook(), "probe"], capture_output=True, timeout=15).returncode != 0:
        print("Moshi is unreachable (moshi-hook probe failed): ask the human in plain text.")
        sys.exit(OFF)
    label = a.label or os.path.basename(os.getcwd())
    q = {"id": uuid.uuid4().hex[:12], "question": a.question, "options": a.options + [OTHER], "pane": a.pane,
         "label": label, "source": re.sub(r"[^a-z0-9._-]+", "-", label.lower()).strip("-") or "agent",
         "timeout": a.timeout, "cwd": os.getcwd()}
    p = subprocess.Popen([sys.executable, os.path.realpath(__file__), "--wait", json.dumps(q)], start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log(dict(q, state="asked", pid=p.pid))
    print(f"Asked on the human's phone (Moshi). Carry on; the answer will arrive in this session as a message "
          f"starting \"Answer from the human (phone):\". [ask {q['id']}, waiter pid {p.pid}]")


if __name__ == "__main__":
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    main()
