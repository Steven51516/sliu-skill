#!/usr/bin/env python3
"""team_switch_test: when team-watch moves a fallen-back session to Sonnet in place, Claude Code's question about the
switch must be answered. Since 2.1.3xx a /model on a conversation cached for another model asks "Switch model?" first;
the watch typed /model and /effort four seconds apart, the session sat at the question, the /effort was refused, and
the log said "switched in place".

A fake herdr stands in for one session. Checks, on team-watch's switch_in_place:
- the question with Yes marked gets Enter, and /effort is typed only after it has closed;
- with no question, both commands are typed and no key is pressed;
- with another choice marked, nothing is pressed, /effort is not typed, and the human is told (a `question` alert)
  instead of "switched in place";
- a command left typed and unsent is sent by itself, and what the input box showed before is cleared first: the two
  commands once went out as one line, "/model claude-sonnet-5-5/effort high".

  python3 tools/tests/team_switch_test.py        (scripts/check.py runs it)
"""
import importlib.util
import json
import os
import pathlib
import shutil
import sys
import tempfile
import types

TOOLS = pathlib.Path(__file__).resolve().parent.parent
ASK = ["  Switch model?", "  Your next response will be slower and use more tokens",
       "  This conversation is cached for the current model. Switching to Sonnet 5.5 means the full history gets re-read.",
       "  {a} 1. Yes, switch to Sonnet 5.5", "  {b} 2. No, go back", "  Enter to confirm · Esc to cancel"]


RULE = "─" * 40


class Herdr:
    """One Claude session in pane w1:p1. `asks`: it shows the question after /model; `marked`: the choice the question
    opens on (1 is Yes); `box`: what its input box shows at the start; `stalls`: its first command stays typed, unsent."""

    def __init__(self, asks=True, marked=1, box="", stalls=False):
        self.asks, self.marked, self.box, self.stalls = asks, marked, box, stalls
        self.asking, self.did, self.sent = False, [], []

    def send(self):
        line, self.box = self.box, ""
        self.sent.append(line)
        self.asking = self.asks and line.startswith("/model")

    def __call__(self, *args, timeout=150):
        out = ""
        if args[:2] == ("agent", "prompt"):
            if self.asking:                                   # herdr sends nothing to a session at a question
                self.did.append("refused " + args[3])
                return types.SimpleNamespace(returncode=1, stdout="", stderr="agent_blocked")
            self.did.append(args[3])
            self.box += args[3]
            if self.stalls:
                self.stalls = False
            else:
                self.send()
        elif args[1:2] == ("send-keys",):
            self.did.append(f"<{' '.join(args[3:])}>")
            if "ctrl+u" in args[3:]:
                self.box = ""
            elif args[3] == "Enter" and self.asking:
                self.asking = self.marked != 1
            elif args[3] == "Enter" and self.box:
                self.send()
        elif args[:2] == ("agent", "read"):
            lines = [l.format(a="❯" if self.marked == 1 else " ", b="❯" if self.marked == 2 else " ") for l in ASK] if self.asking \
                else [f"❯ {x}" for x in self.sent[-2:]] + [RULE, f"❯ {self.box}", RULE, "  ⏵⏵ auto mode on"]
            out = json.dumps({"result": {"text": "\n".join(lines)}})
        elif args[:2] == ("agent", "list"):
            out = json.dumps({"result": {"agents": [{"pane_id": "w1:p1", "agent_status": "blocked" if self.asking else "idle"}]}})
        return types.SimpleNamespace(returncode=0, stdout=out, stderr="")


def main():
    problems, tmp, here = [], tempfile.mkdtemp(prefix="team-switch-"), os.getcwd()
    os.chdir(tmp)
    try:
        spec = importlib.util.spec_from_file_location("team_watch", TOOLS / "team-watch.py")
        watch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(watch)
        watch.time.sleep = lambda s: None
        watch.user_defaults = lambda: {"model": "opus"}       # unchanged: nothing to put back
        said = []
        watch.note = lambda text: said.append(("note", text))
        watch.alert = lambda text, kind="other": said.append((kind, text))

        def switch(h, session):
            watch.herdr = h
            said.clear()
            watch.switch_in_place("w1:p1", "worker M1-01", "it fell back", session)
            return list(said)

        h = Herdr(asks=True, marked=1)
        told = switch(h, "s1")
        if h.did != ["/model claude-sonnet-5-5", "<Enter>", f"/effort {watch.EFFORT}"]:
            problems.append(f"the question was not answered and then the effort set: {h.did}")
        if not told or told[0][0] != "note" or "switched in place" not in told[0][1]:
            problems.append(f"an answered switch was not logged as done: {told}")

        h = Herdr(asks=False)
        switch(h, "s2")
        if h.did != ["/model claude-sonnet-5-5", f"/effort {watch.EFFORT}"]:
            problems.append(f"with no question, something else was typed or pressed: {h.did}")

        h = Herdr(asks=False, stalls=True)                    # the first command stays typed: Enter sends it, alone
        switch(h, "s4")
        if h.sent != ["/model claude-sonnet-5-5", f"/effort {watch.EFFORT}"]:
            problems.append(f"a command left unsent was not sent by itself: sent {h.sent}, did {h.did}")

        h = Herdr(asks=False, box="half a sentence")          # what the box showed is cleared, not sent with the command
        switch(h, "s5")
        if h.sent != ["/model claude-sonnet-5-5", f"/effort {watch.EFFORT}"] or not h.did[0].startswith("<ctrl+u"):
            problems.append(f"the command was typed onto what the input box held: sent {h.sent}, did {h.did}")

        h = Herdr(asks=True, marked=2)
        told = switch(h, "s3")
        if h.did != ["/model claude-sonnet-5-5"]:
            problems.append(f"a question with another choice marked was answered, or more was typed: {h.did}")
        if not told or told[0][0] != "question" or "switched in place" in told[0][1]:
            problems.append(f"a session left at the question was not reported as one: {told}")
    except Exception as e:                                  # the code under test broke: that is a failure too
        problems.append(f"the switch code raised {type(e).__name__}: {e}")
    finally:
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    for x in problems:
        print("team_switch_test:", x)
    print(f"team_switch_test: {'FAILED' if problems else 'ok'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
