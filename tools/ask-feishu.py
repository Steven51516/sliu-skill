#!/usr/bin/env python3
"""ask-feishu: ask someone other than the human a question on Feishu, through the Feishu bridge bot; the answer comes
back later as a prompt typed into this session's herdr pane.

  ask-feishu --to "<name|email|open_id>" [--context "<pointer or short excerpt>"] "<question>"
  ask-feishu --dry-run ...          print the request instead of sending it

It finds its pane with `herdr pane current` and POSTs {id, pane_id, to, question, context, cwd} as JSON to
FEISHU_BRIDGE_URL with `Authorization: Bearer <FEISHU_BRIDGE_KEY>`, both read from ~/.config/feishu-bridge/env (KEY=value
lines; the file is read, never sourced). It prints the bridge's status (a `status` field in its JSON reply): the bridge
may hold a question for the human's approval, so taking it is not sending it. The bridge types its notices into the pane
as lines starting `[Feishu bridge]`, and the answer as
`Answer from <name> (Feishu): <answer> (to: <question>, id <id>)`. Every question the bridge takes is a line in
~/.config/research-harness/feishu-asks.jsonl. Exits 2 with the reason when it cannot send (not in a herdr pane, bridge
not configured, bridge unreachable or refusing); the key is never printed.

Setup: fill in the env file, then let Claude Code's auto mode run it, or its classifier blocks every call: add to
`autoMode.allow` in ~/.claude/settings.json a rule such as "Running the user's Feishu bridge tool `ask-feishu` to send a
colleague a question or a results summary, when the user named that colleague for this kind of question (in this
conversation, the project's AGENTS.md or the ticket); never credentials or private data; never anyone the user did not
name."
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

ENV = os.path.expanduser("~/.config/feishu-bridge/env")
LOG = os.path.join(os.environ.get("ASK_HUMAN_DIR") or os.path.expanduser("~/.config/research-harness"),
                   "feishu-asks.jsonl")
PLACEHOLDER = "FILL_ME"


def fail(why):
    print(f"ask-feishu: {why}", file=sys.stderr)
    sys.exit(2)


def bridge():
    """(url, key) from the env file, or fail when it is missing or still holds the placeholders."""
    conf = {}
    try:
        for line in open(ENV):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                conf[k.strip().removeprefix("export ").strip()] = v.strip().strip("'\"")
    except OSError:
        fail(f"no {ENV}: the Feishu bridge is not set up; ask the human instead")
    url, key = conf.get("FEISHU_BRIDGE_URL", ""), conf.get("FEISHU_BRIDGE_KEY", "")
    if not url or not key or PLACEHOLDER in (url, key):
        fail(f"FEISHU_BRIDGE_URL and FEISHU_BRIDGE_KEY are not filled in {ENV}; ask the human instead")
    return url, key


def pane():
    try:
        r = subprocess.run(["herdr", "pane", "current"], capture_output=True, text=True, timeout=20)
        return json.loads(r.stdout)["result"]["pane"]["pane_id"]
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        fail("not in a herdr pane (herdr pane current failed), so no answer could reach you; ask the human instead")


def main():
    p = argparse.ArgumentParser(prog="ask-feishu", description=__doc__.split("\n\n")[0])
    p.add_argument("--to", required=True, help="the person: name, email or open_id")
    p.add_argument("--context", default="", help="a pointer or short excerpt the person needs")
    p.add_argument("--dry-run", action="store_true", help="print the request instead of sending it")
    p.add_argument("question")
    a = p.parse_args()
    req = {"id": uuid.uuid4().hex[:8], "pane_id": pane(), "to": a.to, "question": a.question, "context": a.context,
           "cwd": os.getcwd()}
    if a.dry_run:
        print(json.dumps(req, ensure_ascii=False, indent=2))
        return
    url, key = bridge()
    post = urllib.request.Request(url, data=json.dumps(req, ensure_ascii=False).encode(), method="POST",
                                  headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(post, timeout=20) as resp:
            status, body = resp.status, resp.read(4096).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        fail(f"the bridge refused the question (HTTP {e.code}); nothing was sent")
    except (urllib.error.URLError, OSError) as e:
        fail(f"could not reach the bridge ({getattr(e, 'reason', e)}); nothing was sent")
    try:
        said = json.loads(body) if body.strip() else {}
    except ValueError:
        said = {}
    state = str(said.get("status") or said.get("state") or "") if isinstance(said, dict) else ""
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(dict(req, t=time.time(), status=status, bridge=state), ensure_ascii=False) + "\n")
    # Taking a question is not sending it: the bridge may hold it for the human's approval (2026-11-02, a relayed "replied")
    print(f"ask-feishu: the bridge took {req['id']} for {a.to} (bridge status: {state or 'none given'}). It is not "
          f"delivered until the bridge says so, so report it as asked, not sent. The answer will arrive in this pane as "
          f"'Answer from {a.to} (Feishu): ...'; keep working on what doesn't need it, or end your turn.")


if __name__ == "__main__":
    main()
