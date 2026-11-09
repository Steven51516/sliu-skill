#!/usr/bin/env python3
"""trash: a delete that can be undone. Each path moves into a `.trash/` folder beside it: the same disk, so it is an
instant rename, never a copy. Emptying the trash is the human's call.

  trash <path>...                  move into <parent>/.trash/<UTC time>-<name>, and print where it went
  trash --list                     the entries still in the trash, oldest first
  trash --restore <path>           put an entry back (give its trash path or its original path)
  trash --empty --older <days>     delete the entries trashed more than <days> days ago (the human runs this)

Every move is a line in ~/.local/state/trash.log (tab-separated: UTC time, action, original path, trash path), so the
trash can be found again from any folder. A path that cannot be renamed in place (a mount point, no write access to its
folder) is left alone with an error: ask the human.
"""
import calendar
import os
import shutil
import sys
import time

LOG = os.path.expanduser("~/.local/state/trash.log")
STAMP = "%Y%m%dT%H%M%SZ"


def fail(why):
    sys.exit(f"trash: {why}")


def log(action, orig, dest):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{time.strftime(STAMP, time.gmtime())}\t{action}\t{orig}\t{dest}\n")


def entries():
    """{trash path: (time, original path)} for every entry still in the trash."""
    out = {}
    if os.path.exists(LOG):
        for line in open(LOG):
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 4:
                continue
            t, action, orig, dest = parts
            if action == "trash":
                out[dest] = (t, orig)
            else:
                out.pop(dest, None)
    return {d: v for d, v in out.items() if os.path.lexists(d)}


def put(path):
    src = os.path.abspath(path)                      # abspath, not realpath: a symlink moves, not its target
    if not os.path.lexists(src):
        fail(f"no such path: {path}")
    parent, name = os.path.split(src.rstrip("/") or "/")
    if name in ("", ".trash") or "/.trash/" in src + "/":
        fail(f"{src} is a trash folder or inside one; emptying is `trash --empty`, by the human")
    bin_ = os.path.join(parent, ".trash")
    os.makedirs(bin_, exist_ok=True)
    dest = base = os.path.join(bin_, f"{time.strftime(STAMP, time.gmtime())}-{name}")
    n = 1
    while os.path.lexists(dest):
        dest, n = f"{base}~{n}", n + 1
    try:
        os.rename(src, dest)
    except OSError as e:
        fail(f"cannot move {src} in place ({e.strerror}); nothing was moved, ask the human")
    log("trash", src, dest)
    print(f"trash: {src} -> {dest}")


def restore(path):
    p, live = os.path.abspath(path), entries()
    hits = [d for d, (_, orig) in live.items() if d == p or orig == p]
    if not hits:
        fail(f"{path} is not in the trash log ({LOG})")
    dest = max(hits)                                 # the newest entry of that path
    orig = live[dest][1]
    if os.path.lexists(orig):
        fail(f"{orig} exists again; move it aside first")
    os.rename(dest, orig)
    log("restore", orig, dest)
    print(f"trash: restored {orig}")


def empty(days):
    cutoff = time.time() - days * 86400
    n = 0
    for dest, (t, orig) in sorted(entries().items(), key=lambda kv: kv[1][0]):
        if calendar.timegm(time.strptime(t, STAMP)) > cutoff:
            continue
        if os.path.isdir(dest) and not os.path.islink(dest):
            shutil.rmtree(dest)
        else:
            os.remove(dest)
        log("empty", orig, dest)
        n += 1
    print(f"trash: deleted {n} entr{'y' if n == 1 else 'ies'} older than {days:g} days")


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        sys.exit(__doc__)
    if a == ["--list"]:
        for dest, (t, orig) in sorted(entries().items(), key=lambda kv: kv[1][0]):
            print(f"{t}  {orig}  ->  {dest}")
    elif a[0] == "--restore" and len(a) == 2:
        restore(a[1])
    elif a[:2] == ["--empty", "--older"] and len(a) == 3:
        empty(float(a[2]))
    elif a[0].startswith("--"):
        sys.exit(__doc__)
    else:
        for p in a:
            put(p)


if __name__ == "__main__":
    main()
