#!/usr/bin/env python3
"""team-worker: open a worker for one ticket, or rescue a stopped one, and check that it really started.

  team-worker <ticket path>          a new tab labelled with the ticket id, on the driver's own agent: Claude Code on Opus
                                     5.5 at medium effort, logged in (macOS: from the Keychain), with an explicit --model so a /model
                                     elsewhere cannot change it; or Codex with the flags in codex-team.args at xhigh. It is
                                     told to work the ticket and to report to the calling driver with one line:
                                     `done|running|ask|blocked <id>: <path of the file that holds the result>`,
                                     or `handback <id>: <request>` for a request beyond its ticket
  team-worker --rescue <ticket id>   the worker in the tab labelled <id>: exited and its own session resumed on Sonnet 5.5
                                     at high effort, keeping its chat, then told to continue (after a safeguard stop)

Run by the driver inside herdr, from the project folder. Exits non-zero with the reason when the worker did not start:
no login, no tab, or a prompt that never began. The login token is read from the Keychain item `claude-code-oauth` and
handed to the new tab's environment; it is never printed or written.
"""
import json
import os
import re
import subprocess
import sys
import time

MODEL, EFFORT, RESCUE_MODEL, RESCUE_EFFORT = "claude-opus-5-5", "medium", "sonnet", "high"   # the driver already planned the ticket
DEAD = re.compile(r"login expired|please run /login|invalid api key|not logged in|authentication (failed|error)|"
                  r"sign in with chatgpt|run codex login", re.I)


def codex_args(effort):
    """The Codex team flags (codex-team.args, next to this file) plus a reasoning effort."""
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "codex-team.args")) as f:
        args = [os.path.expanduser(l.strip()) for l in f if l.strip() and not l.lstrip().startswith("#")]
    return args + ["-c", f'model_reasoning_effort="{effort}"']


def herdr(*args, timeout=150):
    return subprocess.run(["herdr", *args], capture_output=True, text=True, timeout=timeout)


def fail(why):
    sys.exit(f"team-worker: {why}")


def ticket_id(path):
    head = open(path).read().split("\n---", 1)[0]
    m = re.search(r"^id:\s*\"?([^\"\s]+)", head, re.M)
    return m.group(1) if m else os.path.basename(os.path.dirname(os.path.abspath(path)))


def token():
    try:
        r = subprocess.run(["security", "find-generic-password", "-a", os.environ.get("USER", ""), "-s",
                            "claude-code-oauth", "-w"], capture_output=True, text=True)
    except FileNotFoundError:          # not macOS: claude reads its own login file in every tab
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def submit(name, pane, text):
    """Type a prompt and see it submitted: a prompt left typed in the input box (2026-11-02: 13 min) looks like a
    started worker. herdr reports a prompt that started no turn within 5 s as stalled; then press Enter once."""
    r = herdr("agent", "prompt", name, text, "--wait", "--until", "working", "--timeout", "60000")
    if r.returncode != 0 and "stalled" in (r.stdout + r.stderr):
        herdr("pane", "send-keys", pane, "Enter")


def started(name):
    """The worker took its prompt (it is working, not idle with the prompt unsent) and is not stuck on a login screen."""
    time.sleep(6)
    screen = herdr("agent", "read", name).stdout
    if DEAD.search(screen):
        return False, "the worker is not logged in (its screen asks for a login)"
    res = json.loads(herdr("agent", "get", name).stdout or "{}").get("result", {})
    status = (res.get("agent") or res).get("agent_status")
    why = "its prompt sits unsubmitted (idle)" if status == "idle" else f"worker status: {status}"
    return (status in ("working", "blocked", "done")), why


def caller_kind():
    """The agent in the calling pane (the driver): a worker runs on the same one."""
    try:
        return json.loads(herdr("pane", "current").stdout)["result"]["pane"].get("agent") or "claude"
    except (ValueError, KeyError, TypeError):
        return "claude"


def open_worker(path):
    tid, here = ticket_id(path), os.getcwd()
    driver = os.environ.get("HERDR_PANE_ID") or fail("run this inside herdr (no HERDR_PANE_ID)")
    kind, env = caller_kind(), []
    tok = token() if kind == "claude" else None
    if tok:
        env = ["--env", f"CLAUDE_CODE_OAUTH_TOKEN={tok}"]
    elif kind == "claude" and sys.platform == "darwin" and not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        fail("no login token: neither the Keychain item claude-code-oauth nor CLAUDE_CODE_OAUTH_TOKEN is set")
    out = herdr("tab", "create", "--workspace", os.environ.get("HERDR_WORKSPACE_ID", ""), "--cwd", here, "--label", tid,
                "--no-focus", *env)
    try:
        pane = json.loads(out.stdout)["result"]["root_pane"]["pane_id"]
    except (ValueError, KeyError, TypeError):
        fail(f"could not open a tab: {(out.stderr or out.stdout).strip()[:200]}")
    name = f"{tid.lower()}-{time.strftime('%H%M%S')}"
    if kind == "codex":
        flags, first, what = codex_args("xhigh"), f"Use the research-work skill (~/.agents/skills/research-work/SKILL.md) on {path}.", "Codex, xhigh"
    else:
        flags, first, what = ["--model", MODEL, "--effort", EFFORT], f"/research-work {path}.", f"{MODEL}, {EFFORT}"
    for _ in range(10):                # a new tab's shell may still be starting
        r = herdr("agent", "start", name, "--kind", kind, "--pane", pane, "--timeout", "120000", "--", *flags)
        if r.returncode == 0 or "not an available shell" not in (r.stderr + r.stdout):
            break
        time.sleep(1)
    if r.returncode != 0:
        screen = herdr("agent", "read", name).stdout
        if "trust" in screen.lower():
            fail(f"{pane} waits at {kind}'s folder-trust check: open {kind} in {here} once and accept, then retry")
        fail(f"{kind} did not start in {pane}: {(r.stderr or r.stdout).strip()[:200]}")
    prompt = (f"{first} You are a worker: when you finish, stop or need the user, send the driver one line with "
              f"herdr agent prompt {driver} 'done|running|ask|blocked {tid}: <path of the file that holds the result or "
              f"question>', or 'handback {tid}: <request>' for a request beyond your ticket.")
    submit(name, pane, prompt)
    ok, why = started(name)
    if not ok:
        fail(f"{tid} in {pane} did not start: {why}")
    print(f"team-worker: {tid} working in {pane} (agent {name}, {what})")


def rescue(tid):
    tabs = json.loads(herdr("tab", "list").stdout or "{}").get("result", {}).get("tabs", [])
    tabs.sort(key=lambda t: t.get("workspace_id") != os.environ.get("HERDR_WORKSPACE_ID"))   # `tab list` spans workspaces: ours first
    tab = next((t["tab_id"] for t in tabs if t.get("label") == tid), None) or fail(f"no tab labelled {tid}")
    agents = json.loads(herdr("agent", "list").stdout or "{}").get("result", {}).get("agents", [])
    a = next((a for a in agents if a.get("tab_id") == tab), None) or fail(f"no agent in the tab of {tid}")
    if a.get("agent") != "claude":
        fail(f"{tid} runs on {a.get('agent')}: --rescue is for Claude sessions stopped by Claude's safeguards")
    session = (a.get("agent_session") or {}).get("value") or fail(f"the session of {tid} is unknown")
    pane = a["pane_id"]
    herdr("agent", "prompt", pane, "/exit")
    time.sleep(8)
    name = f"{tid.lower()}-s{time.strftime('%H%M%S')}"
    r = herdr("agent", "start", name, "--kind", "claude", "--pane", pane, "--timeout", "120000",
              "--", "--resume", session, "--model", RESCUE_MODEL, "--effort", RESCUE_EFFORT)
    if r.returncode != 0:
        fail(f"could not resume {tid}: {r.stderr.strip()[:200]}")
    submit(name, pane, "continue: this session was resumed on Sonnet 5.5 after Claude's safeguards stopped it. Pick up "
                       "where you stopped, but before repeating any launch or other outside action, check the ticket's "
                       "Log and the server for what already ran; no summary; hand biology steps to their delegate by "
                       "pointer; report to the driver as before.")
    ok, why = started(name)
    if not ok:
        fail(f"{tid} did not resume: {why}")
    print(f"team-worker: {tid} resumed in {pane} on Sonnet 5.5 ({RESCUE_EFFORT}), session {session[:8]}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--rescue"] and len(args) == 2:
        rescue(args[1])
    elif len(args) == 1 and os.path.isfile(args[0]):
        open_worker(args[0])
    else:
        sys.exit(__doc__)
