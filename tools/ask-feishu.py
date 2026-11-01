#!/usr/bin/env python3
"""ask-feishu: ask someone other than the human a question on Feishu, through the Feishu bridge bot; the answer comes
back later as a prompt typed into this session's herdr pane.

  ask-feishu --to "<name|email|open_id>" [--context "<pointer or short excerpt>"] "<question>"
  ask-feishu --dry-run ...          print the request instead of sending it

It finds its pane with `herdr pane current` and POSTs {id, pane_id, to, question, context, cwd} as JSON to
FEISHU_BRIDGE_URL with `Authorization: Bearer <FEISHU_BRIDGE_KEY>`, both read from ~/.config/feishu-bridge/env (KEY=value
lines; the file is read, never sourced). The bridge types the answer into the pane as
`Answer from <name> (Feishu): <answer> (to: <question>, id <id>)`. Every question sent is a line in
~/.config/research-harness/feishu-asks.jsonl. Exits 2 with the reason when it cannot send (not in a herdr pane, bridge
not configured, bridge unreachable or refusing); the key is never printed.
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
            status = resp.status
    except urllib.error.HTTPError as e:
        fail(f"the bridge refused the question (HTTP {e.code}); nothing was sent")
    except (urllib.error.URLError, OSError) as e:
        fail(f"could not reach the bridge ({getattr(e, 'reason', e)}); nothing was sent")
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(dict(req, t=time.time(), status=status), ensure_ascii=False) + "\n")
    print(f"ask-feishu: sent {req['id']} to {a.to}. The answer will arrive in this pane as "
          f"'Answer from {a.to} (Feishu): ...'; keep working on what doesn't need it, or end your turn.")


if __name__ == "__main__":
    main()
