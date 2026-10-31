#!/usr/bin/env python3
"""research-status: generate a project's STATUS.md from maps/*/map.md and maps/*/tickets/*/ticket.md.

The local issue tracker's view and checker (docs/agents/issue-tracker.md). STATUS.md is a VIEW: nobody edits it by hand.
Edit the map/ticket files, then rerun, so parallel sessions never collide on one shared file.
Projects still on the old layout (tracks/*/track.md) are read too.

Usage (from the project root, or pass it):
    research-status [PROJECT] [--print] [--check] [--frontier]
      (none)      write STATUS.md, the project page: milestones (closed maps' outcomes) and open maps
      --print     the same page to stdout instead
      --now       print what is live: waiting on you, running or claimed, the frontier (never stored)
      --check     only report problems (unknown or unmet blockers, dependency cycles, unknown statuses, stale claims,
                  missing fields, resolved tickets missing from their map or their answer); exit 1 if any
      --frontier  only list the frontier (open, unblocked, unclaimed tickets), one per line
Pure standard library.
"""
import argparse
import csv
import datetime as dt
import glob
import os
import re
import sys

CLOSED = {"resolved", "parked", "superseded"}     # off the frontier
STATUSES = {"open", "claimed", "running", "held", "resolved", "parked", "superseded"}
MAP_STATUSES = {"open", "claimed", "paused", "closed"}
HUMAN_ONLY = {"held", "paused"}
ACTIVE = {"claimed", "running"}
HITL = {"grilling", "prototype"}
TYPES = {"experiment", "research", "prototype", "grilling", "task"}
STALE_HOURS = 36
MAX_WAITING = 8
# older words for the same states and types, read as the canonical ones
STATUS_ALIASES = {"done": "resolved", "final": "resolved", "planned": "open", "stale": "open", "approved": "open",
                  "handed-off": "open"}
TYPE_ALIASES = {"lit": "research", "decision": "grilling", "baseline": "experiment", "diagnostic": "experiment",
                "analysis": "experiment"}
CHECKBOX = re.compile(r"^- \[[ xX]\] ")


def base(status):
    """`claimed (sess, 2026-10-28 03:21 UTC)` -> `claimed`."""
    word = re.split(r"[\s(]", (status or "").strip(), maxsplit=1)[0]
    return STATUS_ALIASES.get(word, word)


def status_of(k):
    return base(k.get("status"))


def holder(k):
    """Who holds a ticket or map: the first item inside `claimed (...)`, else the older `claimed:` field."""
    m = re.match(r"\s*claimed\s*\(([^,)]*)", k.get("status") or "")
    return (m.group(1).strip() if m else None) or k.get("claimed")


def claim_text(k):
    m = re.match(r"\s*claimed\s*\((.*)\)", k.get("status") or "")
    return m.group(1) if m else k.get("claimed")


def type_of(k):
    t = k.get("type")
    return TYPE_ALIASES.get(t, t)


def parse_front_matter(path):
    """Tiny YAML subset: `key: value` lines between the first two `---`; values may be null, [a, b], "quoted", plain."""
    with open(path) as f:
        text = f.read()
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    meta, last = {}, None
    for line in m.group(1).splitlines():
        if line.startswith((" ", "\t")) and line.strip().startswith("- ") and last and (meta.get(last) is None or isinstance(meta.get(last), list)):
            meta[last] = (meta.get(last) or []) + [line.strip()[2:].strip().strip("'\"")]   # block-list item
            continue
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        val = val.strip()
        if not (val.startswith('"') or val.startswith("'")):
            val = re.sub(r"\s+#.*$", "", val)  # strip trailing comment
        if val in ("", "null", "None", "~"):
            val = None
        elif val.startswith("[") and val.endswith("]"):
            val = [v.strip().strip("'\"") for v in next(csv.reader([val[1:-1]], skipinitialspace=True)) if v.strip()]
        elif len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        last = key.strip()
        meta[last] = val
    return meta, m.group(2)


def section(body, title):
    """Lines of a `## title` section (until the next `## `)."""
    out, on = [], False
    for line in body.splitlines():
        if line.startswith("## "):
            on = line[3:].strip().lower() == title.lower()
            continue
        if on:
            out.append(line)
    return out


def answered(body):
    """True when an `## Answer` (older tickets: `## Verdict`, `## Result ...`) section has content before the next heading."""
    on = False
    for line in body.splitlines():
        if line.startswith("## "):
            on = bool(re.match(r"(answer|verdict|result)\b", line[3:].strip(), re.I))
        elif on and line.strip():
            return True
    return False


def destination(body):
    """First non-empty, non-comment line of `## Destination`."""
    clean = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    for line in section(clean, "Destination"):
        if line.strip():
            return line.strip()
    return ""


def legacy_needs(body):
    """Open `- [ ]` items in an old map's `## Needs you` (new maps hold these as grilling tickets)."""
    items, cur = [], None
    for line in section(body, "Needs you"):
        if line.startswith("- [ ]"):
            cur = [line[5:].strip()]
            items.append(cur)
        elif line.startswith("- "):
            cur = None
        elif cur is not None and line.startswith("  ") and line.strip():
            cur.append(line.strip())
    return [" ".join(i) for i in items]


def map_links(body):
    """Ticket folders linked from the map's Decisions so far and Out of scope (HTML comments ignored)."""
    clean = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    lines = section(clean, "Decisions so far") + section(clean, "Out of scope")
    return set(re.findall(r"\]\(tickets/([^/)\s]+)", "\n".join(lines)))


def claim_age_hours(claimed):
    m = re.search(r"(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}))?", claimed or "")
    if not m:
        return None
    try:
        t = dt.datetime.strptime(m.group(1) + " " + (m.group(2) or "00:00"), "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return (dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - t).total_seconds() / 3600   # claim times are UTC


def bad_claim_date(claimed):
    return bool(re.search(r"\d{4}-\d{2}-\d{2}", claimed or "")) and claim_age_hours(claimed) is None


def map_files(project):
    found = sorted(glob.glob(os.path.join(project, "maps", "*", "map.md")))
    legacy = sorted(glob.glob(os.path.join(project, "tracks", "*", "track.md")))
    seen = {os.path.realpath(os.path.dirname(p)) for p in found}
    return found + [p for p in legacy if os.path.realpath(os.path.dirname(p)) not in seen]


def load(project):
    maps = []
    for mpath in map_files(project):
        meta, body = parse_front_matter(mpath)
        mdir = os.path.dirname(mpath)
        tickets = []
        for kpath in sorted(glob.glob(os.path.join(mdir, "tickets", "*", "ticket.md"))):
            kmeta, kbody = parse_front_matter(kpath)
            kmeta["_path"] = os.path.relpath(kpath, project)
            kmeta["_answered"] = answered(kbody)
            b = kmeta.get("blocked_by") or []
            b = [b] if isinstance(b, str) else b          # a plain number names a ticket on the same map
            kmeta["blocked_by"] = [f"{meta.get('id')}-{int(x):02d}" if str(x).strip().isdigit() else x for x in b]
            tickets.append(kmeta)
        archived = []                     # consolidated tickets still resolve the blockers that name them
        for kpath in sorted(glob.glob(os.path.join(mdir, "archive", "**", "ticket.md"), recursive=True)):
            kmeta, _ = parse_front_matter(kpath)
            kmeta["_path"] = os.path.relpath(kpath, project)
            archived.append(kmeta)
        meta["_path"] = os.path.relpath(mpath, project)
        meta["_legacy"] = mpath.endswith("track.md")
        meta["_destination"] = destination(body)
        meta["_needs"] = legacy_needs(body)
        meta["_map_links"] = map_links(body)
        meta["_tickets"] = tickets
        meta["_archived"] = archived
        maps.append(meta)
    return maps


def blocker_met(b, by_id, seen=()):
    """A blocker is met when it is resolved; a superseded one only when its replacement is."""
    k = by_id.get(b)
    if not k or b in seen:
        return False
    if status_of(k) == "resolved":
        return True
    if status_of(k) == "superseded" and k.get("superseded_by"):
        return blocker_met(k["superseded_by"], by_id, seen + (b,))
    return False


def cycles(tickets):
    graph = {k.get("id"): [b for b in (k.get("blocked_by") or [])] for k in tickets}
    graph = {i: ([v] if isinstance(v, str) else v) for i, v in graph.items()}
    found, state = [], {}
    def visit(n, path):
        state[n] = 1
        for b in graph.get(n, []):
            if state.get(b) == 1:
                found.append(" -> ".join(path[path.index(b):] + [b]) if b in path else f"{n} -> {b}")
            elif b in graph and not state.get(b):
                visit(b, path + [b])
        state[n] = 2
    for n in graph:
        if not state.get(n):
            visit(n, [n])
    return found


def analyse(maps):
    by_id = {k.get("id"): k for m in maps for k in m["_archived"]}
    by_id.update({k.get("id"): k for m in maps for k in m["_tickets"]})
    problems, frontier = [], {}
    seen = {}
    for m in maps:                        # duplicate map ids make every ticket id ambiguous
        prev = seen.get(m.get("id"))
        if prev:
            problems.append(f"{m['_path']}: duplicate map id `{m.get('id')}` (also {prev}) — renumber one")
        seen[m.get("id")] = m["_path"]
    ticket_seen = {}
    for m in maps:
        for k in m["_tickets"]:
            prev = ticket_seen.get(k.get("id"))
            if prev:
                problems.append(f"{k['_path']}: duplicate ticket id `{k.get('id')}` (also {prev})")
            ticket_seen[k.get("id")] = k["_path"]
    for c in cycles([k for m in maps for k in m["_tickets"]]):
        problems.append(f"dependency cycle: {c}")
    for m in maps:
        for f in ("id", "title"):
            if not m.get(f):
                problems.append(f"{m['_path']}: missing `{f}`")
        if m.get("status") and status_of(m) not in MAP_STATUSES:
            problems.append(f"{m['_path']}: unknown map status `{m.get('status')}` ({', '.join(sorted(MAP_STATUSES))})")
        if status_of(m) in HUMAN_ONLY and "(human" not in (m.get("status") or ""):
            problems.append(f"{m['_path']}: `{status_of(m)}` must be the human's: `{status_of(m)} (human, <date>: why)`")
        if status_of(m) == "closed" and not m.get("outcome"):
            problems.append(f"{m['_path']}: closed without an `outcome:` line")
        if bad_claim_date(claim_text(m)):
            problems.append(f"{m['_path']}: claim has an invalid date: {claim_text(m)}")
        fr = []
        for k in m["_tickets"]:
            for f in ("id", "title", "type", "status"):
                if not k.get(f):
                    problems.append(f"{k['_path']}: missing `{f}`")
            if k.get("status") and status_of(k) not in STATUSES:
                problems.append(f"{k['_path']}: unknown status `{k.get('status')}` (one of {', '.join(sorted(STATUSES))})")
            if status_of(k) == "resolved" and not k["_answered"]:
                problems.append(f"{k['_path']}: resolved without an answer under `## Answer`")
            if not m["_legacy"] and k.get("type") and k.get("type") not in TYPES:
                problems.append(f"{k['_path']}: unknown type `{k.get('type')}` (one of {', '.join(sorted(TYPES))})")
            blockers = k.get("blocked_by") or []
            if isinstance(blockers, str):
                blockers = [blockers]
            for b in blockers:
                if b not in by_id:
                    problems.append(f"{k['_path']}: unknown blocker `{b}`")
                elif status_of(k) == "open" and status_of(by_id[b]) == "parked":
                    problems.append(f"{k['_path']}: blocked by parked `{b}`: waive the edge or unpark it")
            if k.get("status") == "superseded" and not k.get("superseded_by"):
                problems.append(f"{k['_path']}: superseded without `superseded_by`")
            # the map records every resolved ticket in Decisions so far, a parked one there or in Out of scope
            folder = os.path.basename(os.path.dirname(k["_path"]))
            if status_of(k) in ("resolved", "parked") and folder not in m["_map_links"]:
                where = ("Decisions so far" if status_of(k) == "resolved" else
                         "Out of scope if ruled out of scope, else Decisions so far with why it is paused")
                problems.append(f"{k['_path']}: {k.get('status')} but not linked from {m['_path']} (add its line to {where})")
            age = claim_age_hours(claim_text(k))
            if status_of(k) in ACTIVE and age is not None and age > STALE_HOURS and not k.get("jobs"):
                problems.append(f"{k['_path']}: claimed {age:.0f} h ago with no jobs (stale?)")
            if bad_claim_date(claim_text(k)):
                problems.append(f"{k['_path']}: claim has an invalid date: {claim_text(k)}")
            if status_of(k) in HUMAN_ONLY and "(human" not in (k.get("status") or ""):
                problems.append(f"{k['_path']}: `held` must be the human's: `held (human, <date>: why)`")
            if k.get("claimed") and status_of(k) not in ACTIVE:
                problems.append(f"{k['_path']}: {status_of(k)} but still `claimed: {k.get('claimed')}` (clear it)")
            if status_of(k) == "superseded" and k.get("superseded_by") and k.get("superseded_by") not in by_id \
                    and k.get("superseded_by") not in seen:
                problems.append(f"{k['_path']}: `superseded_by: {k.get('superseded_by')}` is not a ticket or map id")
            unblocked = all(blocker_met(b, by_id) for b in blockers)
            if status_of(k) == "open" and not k.get("claimed") and unblocked and status_of(m) not in ("paused", "closed"):
                fr.append(k)
        frontier[m.get("id")] = fr
    held_by = {}
    for m in maps:
        for k in m["_tickets"]:
            if status_of(k) == "claimed" and holder(k):
                held_by.setdefault(holder(k), []).append(k.get("id"))
    for who, ids in held_by.items():
        if len(ids) > 1:
            problems.append(f"{who} holds {len(ids)} claims ({', '.join(ids)}); one at a time")
    return problems, frontier


def render_page(project, maps):
    """STATUS.md: the project page. Changes only when a map is opened, re-charted or closed."""
    today = dt.date.today().isoformat()
    out = [f"# Status: {os.path.basename(os.path.abspath(project))}",
           f"_Generated {today} by `research-status` — do not edit. What is live now (waiting on you, running, "
           f"the frontier): `research-status --now`._", ""]
    closed = [m for m in maps if status_of(m) == "closed"]
    out.append("## Milestones (closed maps and their outcomes)")
    if not closed:
        out.append("- none yet")
    for m in closed:
        out.append(f"- [{m.get('id')} {m.get('title')}]({m['_path']}): {m.get('outcome') or '(no outcome recorded)'}")
    out += ["", "## Open maps", "| map | destination | driven by |", "|---|---|---|"]
    for m in [m for m in maps if status_of(m) != "closed"]:
        state = holder(m) or ("paused" if status_of(m) == "paused" else "")
        out.append(f"| [{m.get('id')} {m.get('title')}]({m['_path']}) | {m['_destination']} | {state} |")
    return "\n".join(out) + "\n"


def render_now(maps, frontier, problems):
    """What is live: printed, never stored."""
    out = []
    waiting = [(m.get("id"), f"{k.get('title')} ({k['_path']})") for m in maps for k in m["_tickets"]
               if type_of(k) in HITL and status_of(k) not in CLOSED | HUMAN_ONLY]   # held: the human parked it
    waiting += [(m.get("id"), n) for m in maps for n in m["_needs"]]
    out.append("Waiting on you:")
    out += [f"  {mid}  {w}" for mid, w in waiting[:MAX_WAITING]] or ["  nothing open"]
    if len(waiting) > MAX_WAITING:
        out.append(f"  … {len(waiting) - MAX_WAITING} more")
    running = [k for m in maps for k in m["_tickets"] if status_of(k) in ACTIVE]
    out.append("Running / claimed:")
    for k in running:
        jobs = k.get("jobs") or []
        jobs = jobs if isinstance(jobs, list) else [jobs]
        out.append(f"  {k.get('id')}  {k.get('title')} · {status_of(k)}"
                   + (f" · jobs {', '.join(jobs[-3:])}" if jobs else "") + (f" · {holder(k)}" if holder(k) else ""))
    if not running:
        out.append("  none")
    out.append("Frontier (open, unblocked, unclaimed):")
    fr = [k for m in maps for k in frontier.get(m.get("id")) or []]
    out += [f"  {k.get('id')}  {k.get('title')}" for k in fr] or ["  empty"]
    if problems:
        out.append(f"Tracker warnings ({len(problems)}): research-status --check")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--print", action="store_true")
    ap.add_argument("--now", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--frontier", action="store_true")
    a = ap.parse_args()
    maps = load(a.project)
    if not maps:
        sys.exit(f"no maps/*/map.md under {os.path.abspath(a.project)}")
    problems, frontier = analyse(maps)
    if a.check:
        print("\n".join(problems) if problems else "ok")
        sys.exit(1 if problems else 0)
    if a.frontier:
        for m in maps:
            for k in frontier.get(m.get("id")) or []:
                print(f"{k.get('id')}\t{type_of(k)}\t{k['_path']}\t{k.get('title')}")
        return
    if a.now:
        sys.stdout.write(render_now(maps, frontier, problems))
        return
    text = render_page(a.project, maps)
    if a.print:
        sys.stdout.write(text)
    else:
        with open(os.path.join(a.project, "STATUS.md"), "w") as f:
            f.write(text)
        print(f"wrote {os.path.join(a.project, 'STATUS.md')} ({text.count(chr(10))} lines, "
              f"{len(problems)} warning(s))")


if __name__ == "__main__":
    main()
