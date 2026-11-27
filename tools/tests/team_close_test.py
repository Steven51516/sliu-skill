#!/usr/bin/env python3
"""team_close_test: closing a worker must never type an exit into it over and over. Eight finished workers once held a
poll loop each (Claude Code does not exit over a background command), and every pass of their driver and of the watch
typed /exit into them again, 4 to 16 times, for days, while the loops polled a server.

A fake herdr stands in for one worker tab. Checks, on `team-worker --close`:
- a worker that holds a background command is asked once to stop it, and the call says "try again later" (exit 3);
- once it has stopped it, the next call ends the session and closes the tab;
- one that keeps a command after being asked is left (exit 1), and further calls type nothing until its state changes;
- a working worker is never typed into (exit 3);
- team-watch tries again after "later", and leaves a tab that team-worker left.

  python3 tools/tests/team_close_test.py        (scripts/check.py runs it)
"""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import shutil
import sys
import tempfile
import types

TOOLS = pathlib.Path(__file__).resolve().parent.parent


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Herdr:
    """One tab labelled M1-01 with a Claude session in pane w1:p1. `holds` is its background commands; `obeys` says
    whether it stops them when asked."""

    def __init__(self, holds=1, obeys=True, status="done"):
        self.holds, self.obeys, self.status, self.seq = holds, obeys, status, 10
        self.alive, self.tab, self.typed, self.dialog = True, True, [], False

    def agents(self):
        a = {"pane_id": "w1:p1", "tab_id": "w1:t1", "agent": "claude", "name": "m1-01-120000", "workspace_id": "w1",
             "agent_status": "blocked" if self.dialog else self.status, "state_change_seq": self.seq,
             "agent_session": {"value": "s-1"}}
        return [a] if self.alive else []

    def __call__(self, *args, timeout=150):
        out = {}
        if args[:2] == ("tab", "list"):
            out = {"result": {"tabs": [{"tab_id": "w1:t1", "label": "M1-01", "workspace_id": "w1"}] if self.tab else []}}
        elif args[:2] == ("agent", "list"):
            out = {"result": {"agents": self.agents()}}
        elif args[:2] == ("agent", "prompt"):
            self.typed.append(args[3])
            self.seq += 1
            if args[3] == "/exit":
                self.dialog, self.alive = self.holds > 0, self.holds > 0
            elif self.obeys:                                # the question about its background commands: it stops them
                self.holds = 0
        elif args[:2] == ("pane", "send-keys"):
            self.typed.append(f"<{args[3]}>")
            self.dialog = False
            self.seq += 1
        elif args[:2] == ("tab", "close"):
            self.tab = False
        return types.SimpleNamespace(returncode=0, stdout=json.dumps(out), stderr="")


def close(worker, h):
    """Run `team-worker --close M1-01` against the fake: (exit code, what it typed in this call)."""
    worker.herdr, before = h, len(h.typed)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            worker.close("M1-01")
        code = 0
    except SystemExit as e:
        code = e.code
    return code, h.typed[before:]


def main():
    problems, tmp, here = [], tempfile.mkdtemp(prefix="team-close-"), os.getcwd()
    os.chdir(tmp)                                           # CLOSING is written under the project's scratch/agents
    sys.stderr = open(os.devnull, "w")                      # the tool's own refusals
    try:
        worker = load("team-worker")
        worker.time.sleep = lambda s: None
        exits = lambda typed: typed.count("/exit")

        h = Herdr(holds=1, obeys=True)                      # asked once, then closed
        code, typed = close(worker, h)
        if code != worker.LATER or exits(typed) != 1 or not any(t.startswith("closing M1-01") for t in typed):
            problems.append(f"a worker holding a background command was not asked to stop it: exit {code}, typed {typed}")
        code, typed = close(worker, h)
        if code != 0 or h.tab or exits(typed) != 1:
            problems.append(f"the worker that stopped its commands was not closed: exit {code}, tab open {h.tab}, typed {typed}")
        if worker.closing():
            problems.append(f"a closed worker is still on record: {worker.closing()}")

        h = Herdr(holds=1, obeys=False)                     # keeps its command: left, and not typed into again
        close(worker, h)
        code, typed = close(worker, h)
        if code != 1 or exits(typed) != 1 or any(t.startswith("closing") for t in typed):
            problems.append(f"a worker that kept its command was not left after one more try: exit {code}, typed {typed}")
        for _ in range(5):
            code, typed = close(worker, h)
            if code != 1 or typed:
                problems.append(f"an exit was typed again into a worker that was left: exit {code}, typed {typed}")
                break
        if not h.tab or exits(h.typed) != 2:
            problems.append(f"a worker with a background command was closed, or got {exits(h.typed)} exits (2 expected)")
        h.seq += 1                                          # it did something since: one more try, and it has stopped them
        h.holds = 0
        code, typed = close(worker, h)
        if code != 0 or h.tab:
            problems.append(f"a left worker that later stopped its commands was not closed: exit {code}")

        h = Herdr(holds=0, status="working")                # never typed into while it works
        code, typed = close(worker, h)
        if code != worker.LATER or typed:
            problems.append(f"a working worker was typed into or not put off: exit {code}, typed {typed}")

        watch = load("team-watch")                          # the watch: again after "later", never after "left"
        calls, answers, notes = [], [watch.CLOSE_LATER, 0], []
        watch.note = notes.append
        watch.subprocess = types.SimpleNamespace(run=lambda *a, **k: (calls.append(1), types.SimpleNamespace(
            returncode=answers[len(calls) - 1], stdout="", stderr="team-worker: why"))[1])
        agent, idle, kept, clock = {"agent_status": "done"}, {"p": 0}, {}, [10 ** 6]
        watch.time = types.SimpleNamespace(time=lambda: clock[0])
        watch.close_finished("p", "M1-01", agent, {"M1-01"}, idle, kept)
        watch.close_finished("p", "M1-01", agent, {"M1-01"}, idle, kept)
        if len(calls) != 1:
            problems.append(f"the watch called --close {len(calls)} times before the retry was due (1 expected)")
        clock[0] += watch.CLOSE_RETRY_MIN * 60 + 1
        watch.close_finished("p", "M1-01", agent, {"M1-01"}, idle, kept)
        if len(calls) != 2 or "p" in kept:
            problems.append(f"the watch did not close the worker on its retry: {len(calls)} calls, kept {kept}")
        calls.clear()
        answers[:] = [1]
        kept.clear()
        for _ in range(4):
            clock[0] += 3600
            watch.close_finished("p", "M1-01", agent, {"M1-01"}, idle, kept)
        if len(calls) != 1:
            problems.append(f"the watch called --close {len(calls)} times on a worker that was left (1 expected)")
    except Exception as e:                                  # the code under test broke: that is a failure too
        problems.append(f"the close code raised {type(e).__name__}: {e}")
    finally:
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    for x in problems:
        print("team_close_test:", x)
    print(f"team_close_test: {'FAILED' if problems else 'ok'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
