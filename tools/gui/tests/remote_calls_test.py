#!/usr/bin/env python3
"""remote_calls_test: Research Desk must never flood a remote host with ssh. It once took down Engaging's login008: a
check every few seconds, each a new ssh through a ProxyCommand hop, none waiting for the last, hops left running when
the link stalled, until sshd refused everyone.

A fake `ssh` and `rsync` stand in for a host whose link has stalled: each call hangs, and starts a second process as a
ProxyCommand hop would. The app's background loops, plus a page hammering it, run against that host. Checks:
- at no moment is more than one call to the host running;
- every call's processes (the hop included) are gone within its deadline, and none are left at the end;
- after a failure the app backs off instead of retrying;
- with the shared connection closed (`ssh -O check` fails) it starts no call at all.

  python3 tools/gui/tests/remote_calls_test.py        (scripts/check.py runs it)
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time

GUI = pathlib.Path(__file__).resolve().parent.parent
FAKE = """#!/bin/sh
# a remote host whose link has stalled (remote_calls_test)
for a in "$@"; do
  if [ "$a" = "-O" ]; then
    [ "$FAKE_LINK" = up ] && exit 0
    echo "Control socket connect(x): No such file or directory" >&2; exit 255
  fi
done
sleep 318 &          # the hop a ProxyCommand starts
echo "hop $!" >> "$FAKE_LOG"
echo "call $$" >> "$FAKE_LOG"
exec sleep 317
"""


def logged(log, kind):
    """PIDs of the fake calls (or their hops) started so far; each call's process is its own PID (exec keeps it)."""
    return [int(w[1]) for w in (l.split() for l in log.read_text().splitlines()) if len(w) == 2 and w[0] == kind]


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="rd-remote-test-"))
    (tmp / "bin").mkdir()
    for name in ("ssh", "rsync"):
        (tmp / "bin" / name).write_text(FAKE)
        (tmp / "bin" / name).chmod(0o755)
    (tmp / "projects.toml").write_text('[projects.deadproj]\nhost = "deadhost"\npath = "~/projects/deadproj"\n')
    log = tmp / "calls.log"
    log.touch()
    os.environ.update(PATH=f"{tmp / 'bin'}:{os.environ['PATH']}", FAKE_LOG=str(log), FAKE_LINK="up",
                      RG_CONFIG=str(tmp / "projects.toml"))
    sys.path.insert(0, str(GUI))
    import server

    server.REMOTE_CACHE = str(tmp / "cache")
    server.REMOTE_SESSIONS = str(tmp / "cache" / ".sessions")
    server.CALL_LIMIT, server.RSYNC_LIMIT = 2, 2
    server.HERDR_EVERY, server.REMOTE_EVERY, server.PULL_EVERY = 0.3, 0.3, 0
    server.BACKOFF = [4, 8, 16]
    server.wanted = lambda host: True
    p = server.project("deadproj")
    problems, attempts, peak = [], 0, 0

    def hammer():                                  # a page polling as fast as it can
        while not stop.is_set():
            server.pull_session(p, "0123abcd-0000-0000-0000-000000000000")
            server.refresh_remote_herdr("deadhost")
            time.sleep(0.05)

    def running():
        return [pid for pid in logged(log, "call") + logged(log, "hop") if alive(pid)]

    def watch(seconds, limit):
        seen, peak = {}, 0
        end = time.time() + seconds
        while time.time() < end:
            peak = max(peak, sum(alive(pid) for pid in logged(log, "call")))
            for pid in running():
                seen.setdefault(pid, time.time())
                if time.time() - seen[pid] > limit:
                    problems.append(f"a call or its hop ran past its deadline ({limit} s): pid {pid}")
                    return peak
            time.sleep(0.1)
        return peak

    try:
        stop = threading.Event()
        for target in (server.remote_sync_loop, server.remote_herdr_loop, hammer, hammer):
            threading.Thread(target=target, daemon=True).start()
        peak = watch(12, server.CALL_LIMIT + 1.5)
        attempts = len(logged(log, "call"))
        if peak > 1:
            problems.append(f"{peak} calls to the host ran at once (at most 1)")
        if attempts > 4:
            problems.append(f"{attempts} calls in 12 s to a host that never answers (back-off allows about 3)")
        info = server.remote_info(p)
        if "unreachable" not in (info["error"] or ""):
            problems.append(f"the project does not say the host is unreachable: {info['error']!r}")
        stop.set()
        time.sleep(server.CALL_LIMIT + 1)
        if running():
            problems.append(f"calls or hops left running after their deadline: pids {running()}")

        os.environ["FAKE_LINK"] = "down"            # the shared connection is closed: nothing may be tried
        getattr(server, "_hosts", {}).clear()
        before = len(logged(log, "call"))
        stop.clear()
        threading.Thread(target=hammer, daemon=True).start()
        watch(4, server.CALL_LIMIT + 1.5)
        stop.set()
        if len(logged(log, "call")) != before:
            problems.append("with the shared connection closed, the app still started calls to the host")
        info = server.remote_info(p)
        if "not connected" not in (info["error"] or ""):
            problems.append(f"the project does not say it is not connected: {info['error']!r}")
    except Exception as e:                        # the code under test broke: that is a failure too
        problems.append(f"the app's remote code raised {type(e).__name__}: {e}")
    finally:
        for pid in logged(log, "call") + logged(log, "hop"):    # whatever happened, leave nothing behind: only our fakes
            try:
                os.kill(pid, 9)
            except OSError:
                pass
        shutil.rmtree(tmp, ignore_errors=True)
    for x in problems:
        print("remote_calls_test:", x)
    print(f"remote_calls_test: {'FAILED' if problems else 'ok'} ({attempts} calls to a stalled host in 12 s, at most {peak} at once)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
