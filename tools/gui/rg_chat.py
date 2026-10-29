"""Chat items from an agent's session transcript: Claude Code (~/.claude/projects/<folder>/<session id>.jsonl) or Codex
(~/.codex/sessions/YYYY/MM/DD/rollout-<time>-<session id>.jsonl).

The transcript is append-only JSONL; readers keep a byte offset and ask for what came after it. Only the main thread is
shown (sidechain = subagents), as items: user, cmd, from (another session's message), assistant, tool, result, note.
"""
import glob
import json
import os
import re

INITIAL_BYTES = 6 << 20      # first read: the transcript's last 6 MB
MAX_ITEMS = 400              # first read: the last 400 items
RESULT_CHARS = 4000
INPUT_CHARS = 3000
_paths = {}


def transcript_path(session_id, agent="claude"):
    """The JSONL file for a session id (cached once found)."""
    if not session_id or not re.fullmatch(r"[0-9a-fA-F-]{8,64}", session_id):
        return None
    p = _paths.get(session_id)
    if p and os.path.exists(p):
        return p
    pattern = (f"~/.codex/sessions/*/*/*/rollout-*-{session_id}.jsonl" if agent == "codex"
               else f"~/.claude/projects/*/{session_id}.jsonl")
    hits = glob.glob(os.path.expanduser(pattern))
    if hits:
        _paths[session_id] = max(hits, key=os.path.getmtime)
        return _paths[session_id]
    return None


def read(path, after=None):
    """Items after byte offset `after` (None: the tail), the new offset, and whether earlier items were cut."""
    size = os.path.getsize(path)
    if after is not None and after > size:          # file replaced: start over
        after = None
    with open(path, "rb") as f:
        start = after if after is not None else max(0, size - INITIAL_BYTES)
        f.seek(start)
        data = f.read(size - start)
    cut = after is None and start > 0
    if cut:                                         # drop the partial first line
        nl = data.find(b"\n")
        data, start = data[nl + 1:], start + nl + 1
    end = data.rfind(b"\n")
    if end < 0:
        return [], start, cut
    items, parse = [], codex_items if "/.codex/" in path else entry_items
    for line in data[:end].split(b"\n"):
        try:
            items += parse(json.loads(line))
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
    if after is None and len(items) > MAX_ITEMS:
        items, cut = items[-MAX_ITEMS:], True
    return items, start + end + 1, cut


def strip_tags(text):
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.S)
    return text.strip()


def user_text_item(uid, ts, text):
    m = re.search(r"<command-name>(.*?)</command-name>", text, re.S)
    if m:
        args = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
        return {"k": "cmd", "id": uid, "ts": ts, "text": (m.group(1).strip() + " " + (args.group(1).strip() if args else "")).strip()}
    m = re.match(r"\s*<cross-session-message([^>]*)>(.*?)(</cross-session-message>|$)", text, re.S)
    if m:
        who = re.search(r'from-name="([^"]*)"', m.group(1))
        return {"k": "from", "id": uid, "ts": ts, "who": who.group(1) if who else "another session", "text": m.group(2).strip()}
    if text.startswith(("<local-command-stdout>", "<local-command-stderr>", "<local-command-caveat>")):
        out = re.sub(r"</?local-command-\w+>", "", text).strip()
        return {"k": "note", "id": uid, "ts": ts, "text": out} if out else None
    if text.startswith("<task-notification>"):
        summ = re.search(r"<summary>(.*?)</summary>", text, re.S)
        return {"k": "note", "id": uid, "ts": ts, "text": "background task: " + (summ.group(1).strip() if summ else "update")}
    if text.startswith("[Request interrupted"):
        return {"k": "note", "id": uid, "ts": ts, "text": "interrupted"}
    text = strip_tags(text)
    return {"k": "user", "id": uid, "ts": ts, "text": text} if text else None


def tool_summary(name, inp):
    if not isinstance(inp, dict):
        return ""
    for key in ("description", "file_path", "pattern", "command", "skill", "prompt", "url", "query", "path", "to", "message"):
        v = inp.get(key)
        if isinstance(v, str) and v.strip():
            v = v.strip().splitlines()[0]
            if key == "skill" and inp.get("args"):
                v += " " + str(inp["args"])
            return v[:200]
    return ""


def result_text(content):
    if isinstance(content, str):
        return content
    out = []
    for c in content or []:
        if isinstance(c, dict):
            if c.get("type") in ("text", "input_text", "output_text"):
                out.append(c.get("text", ""))
            elif c.get("type") == "image":
                out.append("[image]")
            elif c.get("type") == "tool_reference":
                out.append(f"[loaded tool {c.get('tool_name')}]")
    return "\n".join(out)


def entry_items(d):
    if d.get("isSidechain") or d.get("isMeta"):
        return []
    t, uid, ts = d.get("type"), d.get("uuid"), d.get("timestamp")
    if t == "system":
        if d.get("subtype") == "compact_boundary":
            return [{"k": "note", "id": uid, "ts": ts, "text": "context compacted"}]
        if d.get("subtype") == "turn_duration":            # the end of a turn: drawn as a divider
            return [{"k": "turn", "id": uid, "ts": ts, "ms": d.get("durationMs")}]
        return []
    if t == "attachment":
        # messages that arrive while the agent is busy (yours, another session's, a background task's) are queued
        # and delivered as attachments, not as user lines
        att = d.get("attachment") or {}
        if att.get("type") == "queued_command":
            p = att.get("prompt")
            text = p if isinstance(p, str) else result_text(p)
            it = user_text_item(uid, ts, text or "")
            return [it] if it else []
        return []
    if t not in ("user", "assistant"):
        return []
    content = d["message"].get("content")
    if t == "user":
        if isinstance(content, str):
            it = user_text_item(uid, ts, content)
            return [it] if it else []
        items = []
        for i, c in enumerate(content or []):
            if c.get("type") == "text":
                it = user_text_item(f"{uid}:{i}", ts, c.get("text", ""))
                if it:
                    items.append(it)
            elif c.get("type") == "image":
                items.append({"k": "user", "id": f"{uid}:{i}", "ts": ts, "text": "[image]"})
            elif c.get("type") == "tool_result":
                text = result_text(c.get("content"))
                items.append({"k": "result", "id": c.get("tool_use_id"), "ts": ts, "error": bool(c.get("is_error")),
                              "text": text[:RESULT_CHARS], "more": max(0, len(text) - RESULT_CHARS)})
        return items
    items = []
    for i, c in enumerate(content or []):
        if c.get("type") == "text" and c.get("text", "").strip():
            items.append({"k": "assistant", "id": f"{uid}:{i}", "ts": ts, "text": c["text"]})
        elif c.get("type") == "tool_use":
            inp = c.get("input")
            raw = json.dumps(inp, indent=1, ensure_ascii=False) if inp is not None else ""
            items.append({"k": "tool", "id": c.get("id"), "ts": ts, "name": c.get("name"),
                          "summary": tool_summary(c.get("name"), inp), "input": raw[:INPUT_CHARS]})
    return items


def codex_items(d):
    """Codex rollout lines: user and assistant messages, tool calls and their outputs (reasoning and setup skipped)."""
    if d.get("type") != "response_item":
        return []
    p, ts = d.get("payload") or {}, d.get("timestamp")
    t, uid = p.get("type"), p.get("id") or f"{ts}:{d.get('ordinal')}"
    if t == "message":
        text = "\n".join(c.get("text", "") for c in p.get("content") or [] if c.get("type") in ("input_text", "output_text"))
        if p.get("role") == "assistant" and text.strip():
            return [{"k": "assistant", "id": uid, "ts": ts, "text": text}]
        if p.get("role") == "user" and text.strip() and not text.lstrip().startswith(("<environment_context>", "<user_instructions>", "# AGENTS.md")):
            return [{"k": "user", "id": uid, "ts": ts, "text": strip_tags(text)}]
        return []
    if t in ("function_call", "custom_tool_call", "local_shell_call"):
        raw = p.get("arguments") if t == "function_call" else p.get("input") or p.get("action")
        try:
            inp = json.loads(raw) if isinstance(raw, str) and t == "function_call" else raw
        except ValueError:
            inp = raw
        summary = tool_summary(p.get("name"), inp) if isinstance(inp, dict) else str(inp or "").strip().splitlines()[0][:200] if inp else ""
        if isinstance(inp, dict) and isinstance(inp.get("cmd") or inp.get("command"), list):
            summary = " ".join(inp.get("cmd") or inp.get("command"))[:200]
        body = json.dumps(inp, indent=1, ensure_ascii=False) if isinstance(inp, (dict, list)) else str(inp or "")
        return [{"k": "tool", "id": p.get("call_id") or uid, "ts": ts, "name": p.get("name") or t, "summary": summary,
                 "input": body[:INPUT_CHARS]}]
    if t in ("function_call_output", "custom_tool_call_output", "local_shell_call_output"):
        out = p.get("output")
        if isinstance(out, dict):
            out = out.get("content") or out.get("output") or json.dumps(out)
        text = result_text(out) if not isinstance(out, str) else out
        return [{"k": "result", "id": p.get("call_id"), "ts": ts, "error": False, "text": text[:RESULT_CHARS],
                 "more": max(0, len(text) - RESULT_CHARS)}]
    return []
