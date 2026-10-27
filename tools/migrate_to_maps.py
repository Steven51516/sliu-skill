#!/usr/bin/env python3
"""research-migrate: move a project from the old tracks/ layout to the local issue tracker's maps/ layout.

    research-migrate [PROJECT] [--dry-run]

What it does (a tar.gz backup of every file it may touch goes to docs/archive/ first):
- tracks/ -> maps/, with a `tracks` symlink back so old links keep resolving; each track.md -> map.md
- map front matter keeps id, title, claimed, updated (drops driver, headline, next); `## Contract` stays;
  open `- [ ]` items in `## Needs you` become grilling tickets, and the section goes
- tickets: type lit -> research, decision -> grilling, baseline/diagnostic/analysis -> experiment; status done ->
  resolved; `driver:` dropped; `## Verdict` -> `## Answer`
- every other .md in the project: project-relative `tracks/` -> `maps/` and `track.md` -> `map.md` (server paths such as
  `~/code/<p>/tracks/...` are left alone), and "call the Skill tool with `research`" -> `resume`
- writes docs/agents/issue-tracker.md, delegation.md and domain.md from the research-init seeds if missing, then
  regenerates STATUS.md
"""
import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import tarfile

HERE = os.path.dirname(os.path.realpath(__file__))
TYPE_MAP = {"lit": "research", "decision": "grilling", "baseline": "experiment", "diagnostic": "experiment",
            "analysis": "experiment"}
REL_TRACKS = re.compile(r"(?<![\w./~-])tracks/([A-Za-z0-9_./-]*)")
REL_TRACKMD = re.compile(r"(?<![\w-])track\.md")
SKIP_DIRS = {".git", "node_modules", "__pycache__"}


def split_front(text):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    return (m.group(1), m.group(2)) if m else (None, text)


def sections(body):
    """[(heading or None, lines)] split at `## ` headings."""
    out, cur = [], [None, []]
    for line in body.splitlines(keepends=True):
        if line.startswith("## "):
            out.append(cur)
            cur = [line.strip()[3:], [line]]
        else:
            cur[1].append(line)
    out.append(cur)
    return out


def open_needs(lines):
    items, cur = [], None
    for line in lines:
        if line.startswith("- [ ]"):
            cur = [line[5:].strip()]
            items.append(cur)
        elif line.startswith("- "):
            cur = None
        elif cur is not None and line.startswith("  ") and line.strip():
            cur.append(line.strip())
    return [" ".join(i) for i in items]


def slug(text, n=40):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:n].rstrip("-") or "decision"


def migrate_map(path, plan, write):
    text = open(path).read()
    front, body = split_front(text)
    keep = []
    for line in (front or "").splitlines():
        key = line.split(":", 1)[0].strip()
        if key in ("driver", "headline", "next"):
            plan.append(f"{path}: drop front matter `{key}`")
            continue
        keep.append(line)
    new_secs, needs = [], []
    for head, lines in sections(body):
        if head and head.lower() == "needs you":
            needs = open_needs(lines)
            plan.append(f"{path}: drop ## Needs you ({len(needs)} open item(s) -> grilling tickets)")
            continue
        new_secs.append("".join(lines))
    new = "---\n" + "\n".join(keep) + "\n---\n" + "".join(new_secs)
    mdir = os.path.dirname(path)
    tdir = os.path.join(mdir, "tickets")
    mid = re.search(r"^id:\s*(\S+)", front or "", re.M)
    mid = mid.group(1) if mid else os.path.basename(mdir).split("-")[0]
    nums = [int(d[:2]) for d in (os.listdir(tdir) if os.path.isdir(tdir) else []) if d[:2].isdigit()]
    nxt = max(nums, default=0) + 1
    for item in needs:
        title = re.search(r"\*\*(.+?)\*\*", item)
        title = (title.group(1) if title else item[:80]).strip()
        folder = os.path.join(tdir, f"{nxt:02d}-{slug(title)}")
        plan.append(f"{folder}/ticket.md: new grilling ticket `{title}`")
        if write:
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, "ticket.md"), "w") as f:
                f.write(f"---\nid: {mid}-{nxt:02d}\ntitle: \"{title}\"\ntype: grilling\nstatus: open\nclaimed: null\n"
                        f"blocked_by: []\nupdated: {dt.date.today().isoformat()}\n---\n# {title}\n\n## Question\n\n"
                        f"{item}\n\n_Moved from the map's Needs you section on {dt.date.today().isoformat()}._\n")
        nxt += 1
    target = os.path.join(mdir, "map.md")
    plan.append(f"{path} -> {target}")
    if write:
        with open(target, "w") as f:
            f.write(new)
        os.remove(path)


def migrate_ticket(path, plan, write):
    text = open(path).read()
    front, body = split_front(text)
    if front is None:
        return
    lines, changed = [], []
    for line in front.splitlines():
        key, _, val = line.partition(":")
        k, v = key.strip(), re.sub(r"\s+#.*$", "", val).strip()
        if k == "driver":
            changed.append("drop driver")
            continue
        if k == "type" and v in TYPE_MAP:
            changed.append(f"type {v} -> {TYPE_MAP[v]}")
            line = f"type: {TYPE_MAP[v]}"
        if k == "status" and v == "done":
            changed.append("status done -> resolved")
            line = "status: resolved"
        lines.append(line)
    new_body = re.sub(r"^## Verdict\b", "## Answer", body, flags=re.M)
    if new_body != body:
        changed.append("## Verdict -> ## Answer")
    if changed:
        plan.append(f"{path}: " + ", ".join(changed))
        if write:
            with open(path, "w") as f:
                f.write("---\n" + "\n".join(lines) + "\n---\n" + new_body)


def local_ref(base, rest):
    """A `tracks/<rest>` reference is to this project's maps only if it exists here; else it names the code repo."""
    rest = rest.rstrip(".,;:")
    alt = re.sub(r"track\.md$", "map.md", rest)
    return rest in ("", "tickets") or any(os.path.exists(os.path.join(base, r)) for r in (rest, alt))


def rewrite_refs(project, base, plan, write):
    for root, dirs, files in os.walk(project):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not os.path.islink(os.path.join(root, d))
                   and os.path.relpath(os.path.join(root, d), project) not in ("docs/archive",)]
        for name in files:
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            try:
                text = open(path).read()
            except (UnicodeDecodeError, OSError):
                continue
            kept = [m.group(0) for m in REL_TRACKS.finditer(text) if not local_ref(base, m.group(1))]
            new = REL_TRACKS.sub(lambda m: "maps/" + m.group(1) if local_ref(base, m.group(1)) else m.group(0), text)
            new = REL_TRACKMD.sub("map.md", new)
            new = new.replace("call the Skill tool with `research`:", "call the Skill tool with `resume`:")
            if new != text:
                n = len(REL_TRACKS.findall(text)) - len(kept) + len(REL_TRACKMD.findall(text))
                plan.append(f"{os.path.relpath(path, project)}: {n} path reference(s)"
                            + (f"; kept as code-repo paths: {', '.join(sorted(set(kept)))}" if kept else ""))
                if write:
                    with open(path, "w") as f:
                        f.write(new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    project = os.path.abspath(a.project)
    old, new = os.path.join(project, "tracks"), os.path.join(project, "maps")
    if not os.path.isdir(old) or os.path.islink(old):
        sys.exit(f"no tracks/ folder to migrate in {project}")
    if os.path.exists(new):
        sys.exit(f"{new} already exists; nothing done")
    write = not a.dry_run
    plan = []
    if write:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
        os.makedirs(os.path.join(project, "docs", "archive"), exist_ok=True)
        backup = os.path.join(project, "docs", "archive", f"pre-maps-{stamp}.tar.gz")
        with tarfile.open(backup, "w:gz") as tar:
            for root, dirs, files in os.walk(project):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not os.path.islink(os.path.join(root, d))]
                for name in files:
                    if name.endswith(".md"):
                        p = os.path.join(root, name)
                        tar.add(p, arcname=os.path.relpath(p, project))
        print(f"backup: {backup}")
        os.rename(old, new)
        os.symlink("maps", old)
    plan.append("tracks/ -> maps/ (+ symlink tracks -> maps)")
    base = new if write else old
    for root, _, files in os.walk(base):
        if "track.md" in files:
            migrate_map(os.path.join(root, "track.md"), plan, write)
    for root, _, files in os.walk(base):
        if "ticket.md" in files:
            migrate_ticket(os.path.join(root, "ticket.md"), plan, write)
    rewrite_refs(project, base, plan, write)
    tracker = os.path.join(project, "docs", "agents", "issue-tracker.md")
    if not os.path.exists(tracker):
        plan.append("docs/agents/issue-tracker.md from the local template")
        if write:
            os.makedirs(os.path.dirname(tracker), exist_ok=True)
            with open(os.path.join(HERE, "..", "skills", "research-init", "issue-tracker-local.md")) as src, open(tracker, "w") as dst:
                dst.write(src.read())
    for name in ("delegation.md", "domain.md"):
        dst = os.path.join(project, "docs", "agents", name)
        if not os.path.exists(dst):
            plan.append(f"docs/agents/{name} from the research-init seed")
            if write:
                with open(os.path.join(HERE, "..", "skills", "research-init", name)) as src, open(dst, "w") as out:
                    out.write(src.read())
    print("\n".join(("would: " if a.dry_run else "") + p.replace(project + "/", "") for p in plan))
    if write:
        subprocess.run([sys.executable, os.path.join(HERE, "status.py"), project])
        subprocess.run([sys.executable, os.path.join(HERE, "status.py"), project, "--check"])


if __name__ == "__main__":
    main()
