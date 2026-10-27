#!/usr/bin/env python3
"""research-status: generate a project's STATUS.md from maps/*/map.md, maps/*/tickets/*/ticket.md and docs/decisions.md.

The local issue tracker's view and checker (docs/agents/issue-tracker.md). STATUS.md is a VIEW: nobody edits it by hand.
Edit the map/ticket files and docs/decisions.md, then rerun, so parallel sessions never collide on one shared file.
Projects still on the old layout (tracks/*/track.md) are read too.

Usage (from the project root, or pass it):
    research-status [PROJECT] [--print] [--check] [--frontier]
      --print     write to stdout instead of STATUS.md
      --check     only report problems (unknown or unmet blockers, dependency cycles, unknown statuses, stale claims,
                  missing fields, resolved tickets missing from their map or their answer); exit 1 if any
      --frontier  only list the frontier (open, unblocked, unclaimed tickets), one per line
Pure standard library.
"""
import argparse
import datetime as dt
import glob
import os
import re
import sys

CLOSED = {"resolved", "parked", "superseded"}     # off the frontier
STATUSES = {"open", "claimed", "running", "resolved", "parked", "superseded"}
MAP_STATUSES = {"open", "closed"}
MAX_MILESTONES = 6
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


def status_of(k):
    s = k.get("status")
    return STATUS_ALIASES.get(s, s)


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
        if line.startswith((" ", "\t")) and line.strip().startswith("- ") and last and meta.get(last) in (None, []):
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
            val = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
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


def destination(body):
    """First non-empty, non-comment line of `## Destination`."""
    clean = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    for line in section(clean, "Destination"):
        if line.strip():
            return line.strip()
    return ""


def milestones(project):
    """Newest one-line entries of docs/decisions.md (cross-map decisions and milestones)."""
    path = os.path.join(project, "docs", "decisions.md")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        text = re.sub(r"<!--.*?-->", "", f.read(), flags=re.S)
    return [l[2:].strip() for l in text.splitlines() if l.startswith("- ")][:MAX_MILESTONES]


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
    return (dt.datetime.now() - t).total_seconds() / 3600


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
            kmeta["_answered"] = bool(re.search(r"^## (Answer|Verdict|Result)\b.*\n\s*\S", kbody, re.M))   # Verdict/Result: older tickets
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
        if m.get("status") and m.get("status") not in MAP_STATUSES:
            problems.append(f"{m['_path']}: unknown map status `{m.get('status')}` (open or closed)")
        age = claim_age_hours(m.get("claimed"))
        if age is not None and age > STALE_HOURS:
            problems.append(f"{m['_path']}: claim is {age:.0f} h old (stale?)")
        if bad_claim_date(m.get("claimed")):
            problems.append(f"{m['_path']}: `claimed` has an invalid date: {m.get('claimed')}")
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
            age = claim_age_hours(k.get("claimed"))
            if k.get("status") in ACTIVE and age is not None and age > STALE_HOURS and not k.get("jobs"):
                problems.append(f"{k['_path']}: claimed {age:.0f} h ago with no jobs (stale?)")
            if bad_claim_date(k.get("claimed")):
                problems.append(f"{k['_path']}: `claimed` has an invalid date: {k.get('claimed')}")
            unblocked = all(blocker_met(b, by_id) for b in blockers)
            if status_of(k) == "open" and not k.get("claimed") and unblocked and m.get("status") != "closed":
                fr.append(k)
        frontier[m.get("id")] = fr
    return problems, frontier


def render(project, maps, frontier, problems):
    today = dt.date.today().isoformat()
    out = [f"# Status: {os.path.basename(os.path.abspath(project))}",
           f"_Generated {today} by `research-status` — do not edit; edit the maps under `maps/` and "
           f"`docs/decisions.md`, then rerun._", ""]
    ms = milestones(project)
    if ms:
        out += ["## Decisions and milestones (newest first, from docs/decisions.md)"] + [f"- {x}" for x in ms] + [""]

    waiting = [(m.get("id"), f"[{k.get('title')}]({k['_path']})") for m in maps for k in m["_tickets"]
               if type_of(k) in HITL and status_of(k) not in CLOSED]
    waiting += [(m.get("id"), n) for m in maps for n in m["_needs"]]
    out.append("## Waiting on you")
    if not waiting:
        out.append("- nothing open")
    for mid, w in waiting[:MAX_WAITING]:
        out.append(f"- **{mid}** {w}")
    if len(waiting) > MAX_WAITING:
        out.append(f"- … {len(waiting) - MAX_WAITING} more")
    out.append("")

    out += ["## Maps", "| map | destination | next on the frontier | claimed |", "|---|---|---|---|"]
    for m in [m for m in maps if m.get("status") != "closed"]:
        link = f"[{m.get('id')} {m.get('title')}]({m['_path']})"
        fr = frontier.get(m.get("id")) or []
        nxt = f"[{fr[0].get('title')}]({fr[0]['_path']})" if fr else ""
        out.append(f"| {link} | {m['_destination']} | {nxt} | {m.get('claimed') or ''} |")
    closed = [m for m in maps if m.get("status") == "closed"]
    if closed:
        out.append("")
        out.append("Closed: " + "; ".join(f"[{m.get('id')} {m.get('title')}]({m['_path']})" for m in closed))
    out.append("")

    running = [k for m in maps for k in m["_tickets"] if k.get("status") in ACTIVE]
    out.append("## Running / claimed")
    if not running:
        out.append("- none")
    for k in running:
        jobs = k.get("jobs") or []
        jobs = jobs if isinstance(jobs, list) else [jobs]
        who = k.get("claimed") or ""
        out.append(f"- [{k.get('id')}]({k['_path']}) {k.get('title')} · {k.get('status')}"
                   + (f" · jobs {', '.join(jobs[-3:])}" if jobs else "") + (f" · {who}" if who else ""))
    out.append("")

    out.append("## Frontier (open, unblocked, unclaimed)")
    anyf = False
    for m in maps:
        fr = frontier.get(m.get("id")) or []
        if fr:
            anyf = True
            out.append(f"- **{m.get('id')}**: " + "; ".join(f"[{k.get('id')}]({k['_path']}) {k.get('title')}" for k in fr[:5])
                       + (f"; … +{len(fr) - 5}" if len(fr) > 5 else ""))
    if not anyf:
        out.append("- empty")
    out.append("")

    counts = {}
    for m in maps:
        for k in m["_tickets"]:
            counts[k.get("status")] = counts.get(k.get("status"), 0) + 1
    out.append("_Tickets: " + ", ".join(f"{v} {s}" for s, v in sorted(counts.items(), key=lambda x: str(x[0]))) + "._")
    if problems:
        out += ["", "## Tracker warnings"] + [f"- {p}" for p in problems[:10]]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--print", action="store_true")
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
    text = render(a.project, maps, frontier, problems)
    if a.print:
        sys.stdout.write(text)
    else:
        with open(os.path.join(a.project, "STATUS.md"), "w") as f:
            f.write(text)
        print(f"wrote {os.path.join(a.project, 'STATUS.md')} ({text.count(chr(10))} lines, "
              f"{len(problems)} warning(s))")


if __name__ == "__main__":
    main()
