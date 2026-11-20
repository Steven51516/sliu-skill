#!/usr/bin/env python3
"""rg_trace: what the sessions of one ticket did, step by step (Research Desk's Trace tab).

A ticket's sessions are those whose first prompt names its folder (`/research-work maps/<map>/tickets/<ticket>/...`,
as team-worker and the app start them) and that ran inside the project, plus any session ids given. For each: its
commands, file edits, reads, web searches, delegations, the messages it got and what it said, each with its time,
whether it failed, and the id of its line (the app opens the conversation there).

Standard library only, one file: the app imports it, and for a session on a herdr machine sends this file over ssh
(`python3 - <args>`), so only the steps cross, not the conversations.

  python3 rg_trace.py <project folder> <ticket needle> [<session id> ...]   → JSON on stdout
"""
import glob
import json
import os
import re
import sys
import time

MAX_EVENTS = 1500           # per session: the first 200 and the last 1300 beyond that
HEAD_LINES = 300            # the first prompt is near the top
HEAD_BYTES = 256 << 10      # a file whose first 256 KB doesn't name the ticket isn't one of its sessions
TEXT = 400                  # characters kept of a command, a message, a reply
CODEX_DAYS = 90


def enc(path):
    return re.sub(r"[^A-Za-z0-9-]", "-", path)


def inside(cwd, root):
    cwd, root = (cwd or "").rstrip("/"), root.rstrip("/")
    return cwd == root or cwd.startswith(root + "/")


def short(text, n=TEXT):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[:n - 1] + "…"


def user_text(content):
    """A user line as the person or another session wrote it: slash commands as typed, hook and command noise
    dropped (None)."""
    if isinstance(content, list):
        if any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content):
            return None
        content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    if not isinstance(content, str) or not content.strip():
        return None
    name = re.search(r"<command-name>(.*?)</command-name>", content, re.S)
    if name:
        args = re.search(r"<command-args>(.*?)</command-args>", content, re.S)
        return f"{name.group(1).strip()} {args.group(1).strip() if args else ''}".strip()
    if content.lstrip().startswith(("<local-command", "<system-reminder", "<command-message", "<task-notification",
                                    "Caveat:", "<bash-")):
        return None
    return content


def head(path):
    """(first prompt, cwd, agent) of a conversation, from its first lines."""
    cwd, first, agent, users = "", None, "claude", []
    try:
        with open(path, errors="replace") as f:
            for i, line in enumerate(f):
                if i > HEAD_LINES:
                    break
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("type") == "session_meta":                       # a Codex rollout
                    agent, cwd = "codex", (d.get("payload") or {}).get("cwd") or ""
                    continue
                if agent == "codex":
                    p = d.get("payload") or {}
                    if d.get("type") == "response_item" and p.get("type") == "message" and p.get("role") == "user":
                        text = "\n".join(c.get("text", "") for c in p.get("content") or [] if isinstance(c, dict))
                        if not text.lstrip().startswith(("<environment_context>", "<user_instructions>", "# AGENTS.md")):
                            users.append(text)
                            if len(users) >= 2:
                                break
                    continue
                cwd = cwd or d.get("cwd") or ""
                if d.get("type") == "user" and not d.get("isMeta"):
                    t = user_text((d.get("message") or {}).get("content"))
                    if t:
                        first = t
                        break
    except OSError:
        return None, "", agent
    return ("\n".join(users) if agent == "codex" else first), cwd, agent


TOOLS = {"Bash": "run", "Write": "edit", "Edit": "edit", "MultiEdit": "edit", "NotebookEdit": "edit", "Read": "read",
         "Grep": "read", "Glob": "read", "WebSearch": "web", "WebFetch": "web", "Task": "agent", "Agent": "agent",
         "Skill": "agent"}
SKIP = {"TodoWrite", "ToolSearch", "ExitPlanMode", "EnterPlanMode"}


def tool_event(name, inp, cwd):
    if name in SKIP:
        return None
    inp = inp if isinstance(inp, dict) else {}
    rel = lambda p: p[len(cwd) + 1:] if cwd and isinstance(p, str) and p.startswith(cwd + "/") else p
    k = TOOLS.get(name, "tool")
    if name == "Bash":
        text, why = inp.get("command") or "", inp.get("description") or ""
        return {"k": k, "text": short(text), "why": short(why, 160), "bg": bool(inp.get("run_in_background"))}
    if k == "edit":
        return {"k": k, "text": rel(inp.get("file_path") or inp.get("notebook_path") or ""), "verb": "wrote" if name == "Write" else "edited"}
    if name == "Read":
        return {"k": k, "text": rel(inp.get("file_path") or "")}
    if name in ("Grep", "Glob"):
        return {"k": k, "text": short(f"{name.lower()} {inp.get('pattern', '')} {rel(inp.get('path') or '')}".strip(), 200)}
    if name == "WebSearch":
        return {"k": k, "text": short(inp.get("query") or "", 200)}
    if name == "WebFetch":
        return {"k": k, "text": short(inp.get("url") or "", 200)}
    if name == "Skill":
        return {"k": k, "text": short(f"skill {inp.get('skill', '')} {inp.get('args') or ''}", 200)}
    if k == "agent":
        return {"k": k, "text": short(inp.get("description") or inp.get("prompt") or "", 200)}
    return {"k": k, "text": name}


def codex_patch_files(text):
    return re.findall(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", text or "", re.M)


def events_of(path, cwd):
    """The steps of one conversation (Claude Code or Codex), oldest first."""
    out, calls, agent = [], {}, "claude"
    with open(path, errors="replace") as f:
        for line in f:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t, ts = d.get("type"), d.get("timestamp")
            if t == "session_meta":
                agent = "codex"
                continue
            if agent == "codex":
                p = d.get("payload") or {}
                pt = p.get("type")
                if t != "response_item":
                    continue
                if pt == "message" and p.get("role") in ("user", "assistant"):
                    text = "\n".join(c.get("text", "") for c in p.get("content") or [] if isinstance(c, dict))
                    if p["role"] == "user" and text.lstrip().startswith(("<environment_context>", "<user_instructions>", "# AGENTS.md")):
                        continue
                    if text.strip():
                        out.append({"k": "prompt" if p["role"] == "user" else "say", "text": short(text), "t": ts, "uuid": p.get("id")})
                elif pt in ("function_call", "custom_tool_call", "local_shell_call"):
                    raw = p.get("arguments") if pt == "function_call" else p.get("input") or p.get("action")
                    try:
                        inp = json.loads(raw) if isinstance(raw, str) and pt == "function_call" else raw
                    except ValueError:
                        inp = raw
                    files = codex_patch_files(raw if isinstance(raw, str) else "")
                    if files:
                        for fp in files:
                            out.append({"k": "edit", "text": fp, "verb": "patched", "t": ts, "uuid": p.get("call_id")})
                        continue
                    cmd = (inp or {}).get("cmd") or (inp or {}).get("command") if isinstance(inp, dict) else inp
                    cmd = " ".join(cmd) if isinstance(cmd, list) else str(cmd or p.get("name") or pt)
                    ev = {"k": "run", "text": short(cmd), "t": ts, "uuid": p.get("call_id")}
                    calls[p.get("call_id")] = ev
                    out.append(ev)
                elif pt in ("function_call_output", "custom_tool_call_output", "local_shell_call_output"):
                    ev, o = calls.get(p.get("call_id")), p.get("output")
                    if ev is not None:
                        code = re.search(r'"exit_code"\s*:\s*(-?\d+)|Process exited with code (-?\d+)', o if isinstance(o, str) else json.dumps(o))
                        if code:
                            ev["ok"] = (code.group(1) or code.group(2)) == "0"
                elif pt == "web_search_call":
                    out.append({"k": "web", "text": short(((p.get("action") or {}).get("query")) or "web search", 200), "t": ts})
                continue
            m = d.get("message") or {}
            if t == "assistant":
                for c in m.get("content") or []:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "tool_use":
                        ev = tool_event(c.get("name"), c.get("input"), cwd)
                        if ev:
                            ev.update(t=ts, uuid=d.get("uuid"))
                            calls[c.get("id")] = ev
                            out.append(ev)
                    elif c.get("type") == "text" and c.get("text", "").strip():
                        out.append({"k": "say", "text": short(c["text"]), "t": ts, "uuid": d.get("uuid")})
            elif t == "user" and not d.get("isMeta"):
                content = m.get("content")
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("tool_use_id") in calls:
                            calls[c["tool_use_id"]]["ok"] = not c.get("is_error")
                if d.get("isCompactSummary"):
                    out.append({"k": "compact", "text": "context compacted", "t": ts, "uuid": d.get("uuid")})
                    continue
                text = user_text(content)
                if text:
                    out.append({"k": "prompt", "text": short(text), "t": ts, "uuid": d.get("uuid")})
    cut = len(out) > MAX_EVENTS
    if cut:
        out = out[:200] + [{"k": "gap", "text": f"{len(out) - MAX_EVENTS} steps not shown"}] + out[-(MAX_EVENTS - 200):]
    return out, cut


def title(path):
    """The session's name (custom title or agent name), if it was given one."""
    name = None
    try:
        with open(path, errors="replace") as f:
            for line in f:
                if '"custom-title"' in line or '"agent-name"' in line:
                    try:
                        d = json.loads(line)
                        name = d.get("customTitle") or d.get("agentName") or name
                    except ValueError:
                        pass
    except OSError:
        pass
    return name


def trace(project, needle, sids=(), extra=()):
    """The ticket's sessions found here: Claude Code conversations in the project's folders (and `extra` files, e.g. the
    app's mirrors), Codex rollouts of the last 90 days, matched by first prompt (or by session id)."""
    base = os.path.expanduser("~/.claude/projects")
    e = enc(project.rstrip("/"))
    files = set(extra)
    for d in glob.glob(os.path.join(base, e + "*")):
        if os.path.basename(d) == e or os.path.basename(d).startswith(e + "-"):
            files.update(glob.glob(os.path.join(d, "*.jsonl")))
    cutoff = time.time() - CODEX_DAYS * 86400
    files.update(f for f in glob.glob(os.path.expanduser("~/.codex/sessions/*/*/*/rollout-*.jsonl")) if os.path.getmtime(f) > cutoff)
    want, out, raw = set(sids), [], needle.encode()
    for path in files:
        sid = re.sub(r"^rollout-\d{4}-\d\d-\d\dT\d\d-\d\d-\d\d-", "", os.path.basename(path))[:-6]
        if sid not in want:
            try:
                with open(path, "rb") as f:
                    if raw not in f.read(HEAD_BYTES):      # most conversations: not this ticket's, no JSON read
                        continue
            except OSError:
                continue
        first, cwd, agent = head(path)
        if not inside(cwd, project):
            continue
        if sid not in want and not (first and needle in first):
            continue
        events, cut = events_of(path, cwd)
        times = [x["t"] for x in events if x.get("t")]
        out.append({"sid": sid, "agent": agent, "title": title(path) if agent == "claude" else None, "path": path,
                    "first": times[0] if times else None, "last": times[-1] if times else None, "events": events, "cut": cut})
    return sorted(out, key=lambda s: s["first"] or "")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    json.dump(trace(sys.argv[1], sys.argv[2], sys.argv[3:]), sys.stdout)
