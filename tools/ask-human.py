#!/usr/bin/env python3
"""ask-human: put a question with fixed answers to the human; in Moshi mode it goes to their phone as buttons.

  ask-human "Keep the 10x LR on L4's distogram head?" Yes No        2-4 options, your pick first
  ask-human --mode [on|off]                                          show or set Moshi mode

Moshi mode on: this returns at once and the asking session keeps working. A waiter in the background opens a small
helper session (Claude Code on Haiku, in a herdr tab next to the asker, in a bare folder) that asks the question with
Claude Code's own question tool; Moshi shows that as buttons on the phone (plus a free-text answer). When the human
answers, the waiter reads the answer from the helper's transcript, closes the helper, and types
`Answer from the human (phone): <answer> (to: <question>)` into the asking session's pane. (Moshi's own `moshi-hook ask`
shows only allow/deny on the phone, so it is not used.) Mode off, or outside herdr: it says so and exits 3, and the
session asks in plain text as usual.

Every question and its outcome is a line in ~/.config/research-harness/asks.jsonl. Research Desk's Inbox lists the open
ones and can answer them: it stops the waiter by its pid, closes the helper's tab and types the answer itself.
"""
import argparse
import glob
import json
import os
import signal
import subprocess
import sys
import time
import uuid

DIR = os.environ.get("ASK_HUMAN_DIR") or os.path.expanduser("~/.config/research-harness")   # env: tests
CONF, LOG = os.path.join(DIR, "ask.json"), os.path.join(DIR, "asks.jsonl")
ASKER = os.path.join(DIR, "asker")          # the helper's folder: no project rules to load
MODEL = "haiku"
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


def herdr(*args, timeout=60):
    """herdr's JSON result, or {"error": {...}}."""
    r = subprocess.run(["herdr", *args], capture_output=True, text=True, timeout=timeout)
    try:
        d = json.loads(r.stdout or r.stderr)
    except ValueError:
        return {"error": {"message": (r.stderr or r.stdout).strip()}}
    return d if "error" in d else d.get("result", d)


def agent(name):
    return next((a for a in herdr("agent", "list").get("agents", []) if a.get("name") == name), None)


def start_helper(q):
    """Open the helper's tab next to the asker and start Claude Code there; its agent name and tab, or raise."""
    ws = (herdr("pane", "get", q["pane"]).get("pane") or {}).get("workspace_id")
    tab = herdr("tab", "create", *(["--workspace", ws] if ws else []), "--cwd", ASKER, "--label", f"ask {q['id'][:6]}", "--no-focus")
    pane, tab_id = (tab.get("root_pane") or {}).get("pane_id"), (tab.get("tab") or {}).get("tab_id")
    if not pane:
        raise RuntimeError(f"couldn't open a tab: {tab.get('error')}")
    name = f"ask-{q['id']}"
    for _ in range(60):                     # the shell takes a moment; a first run in the folder asks to trust it
        r = herdr("agent", "start", name, "--kind", "claude", "--pane", pane, "--", "--model", MODEL, timeout=90)
        code = (r.get("error") or {}).get("code")
        if code == "agent_pane_busy":
            time.sleep(1)
            continue
        if code == "agent_not_ready" and "trust this folder" in json.dumps(herdr("pane", "read", pane)):
            herdr("agent", "send-keys", name, "down", "enter")
        break
    for _ in range(30):
        if (agent(name) or {}).get("agent_status") in ("idle", "done"):
            return name, tab_id
        time.sleep(1)
    herdr("tab", "close", tab_id)
    raise RuntimeError("the helper session didn't start")


def transcript(name):
    sid = ((agent(name) or {}).get("agent_session") or {}).get("value")
    hits = glob.glob(os.path.expanduser(f"~/.claude/projects/*/{sid}.jsonl")) if sid else []
    return hits[0] if hits else None


def outcome(path):
    """("answer", text) once the question tool returned, ("failed", why) if the helper ended without asking, else None."""
    asked = False
    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            res = d.get("toolUseResult")
            if d.get("type") == "user" and isinstance(res, dict) and "answers" in res:
                ans = list((res.get("answers") or {}).values())
                return ("answer", str(ans[0])) if ans else ("failed", "the question was dismissed")
            if d.get("type") == "assistant":
                for b in (d.get("message") or {}).get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "AskUserQuestion":
                        asked = True
                if not asked and (d.get("message") or {}).get("stop_reason") == "end_turn":
                    return ("failed", "the helper did not ask")
    return None


def deliver(pane, text):
    return "error" not in herdr("agent", "prompt", pane, text)


def wait(q):
    """The background half: the helper session asks; the answer goes back to the asking session."""
    tab = None
    try:
        name, tab = start_helper(q)
        log({"id": q["id"], "state": "posted", "helper": name, "tab": tab})
        tool_input = {"questions": [{"question": q["question"], "header": q["label"][:12] or "Question", "multiSelect": False,
                                     "options": [{"label": o, "description": ""} for o in q["options"]]}]}
        herdr("agent", "prompt", name, "Call the AskUserQuestion tool exactly once with exactly this input, then stop "
              f"without doing anything else: {json.dumps(tool_input, ensure_ascii=False)}")
        end, got = time.time() + q["timeout_s"], None
        while time.time() < end and not got:
            time.sleep(3)
            path = transcript(name)
            got = outcome(path) if path else None
            if not got and not agent(name):
                got = ("failed", "the helper session was closed")
        state, answer = got or ("timeout", None)
    except Exception as e:                       # whatever broke, the asker must hear back
        state, answer = "failed", str(e)
    if tab:
        herdr("tab", "close", tab)
    msg = {"answer": f"Answer from the human (phone): {answer} (to: {q['question']})",
           "timeout": f"No answer on the phone within {q['timeout']} (to: {q['question']}). Ask in plain text if it still matters.",
           "failed": f"Your phone question didn't go through ({answer}) (to: {q['question']}). Ask in plain text."}[state]
    log({"id": q["id"], "state": "answered" if state == "answer" else state, "answer": answer if state == "answer" else None,
         "delivered": deliver(q["pane"], msg)})


def seconds(s):
    return int(float(s[:-1]) * {"s": 1, "m": 60, "h": 3600}[s[-1]]) if s[-1] in "smh" else int(s)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("question", nargs="?")
    ap.add_argument("options", nargs="*", help="2-4 answers, your pick first")
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
    if not a.question or not 2 <= len(a.options) <= 4:
        ap.error("give a question and 2-4 options, your pick first")
    if not moshi_mode():
        print("Moshi mode is off: ask the human in plain text.")
        sys.exit(OFF)
    if not a.pane:
        print("Not in a herdr pane, so the answer could not come back: ask the human in plain text.")
        sys.exit(OFF)
    os.makedirs(ASKER, exist_ok=True)
    q = {"id": uuid.uuid4().hex[:12], "question": a.question, "options": a.options, "pane": a.pane,
         "label": a.label or os.path.basename(os.getcwd()), "timeout": a.timeout, "timeout_s": seconds(a.timeout), "cwd": os.getcwd()}
    p = subprocess.Popen([sys.executable, os.path.realpath(__file__), "--wait", json.dumps(q)], start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log(dict(q, state="asked", pid=p.pid))
    print(f"Asking on the human's phone (Moshi). Carry on; the answer will arrive in this session as a message "
          f"starting \"Answer from the human\". [ask {q['id']}, waiter pid {p.pid}]")


if __name__ == "__main__":
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    main()
