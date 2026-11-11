#!/usr/bin/env python3
"""research-preset: optional setup in named presets (presets/<name>/preset.json). The research workflow needs none of
them; each is a choice that can be taken back.

  research-preset                                       list the presets and whether each is applied here
  research-preset <name> [--dry-run]                    apply its machine part (and the presets it includes)
  research-preset <name> --project DIR --topic FIELD    also its project part: rows in DIR/docs/agents/delegation.md
  research-preset <name> --remove [--project DIR ...]   take it out again

A preset may: put a harness file on your PATH (`path`); add Claude Code hooks to ~/.claude/settings.json (`hooks`;
matched by command, never added twice; the old file is kept as settings.json.bak-<time>); add a block of rules,
between marker lines, to ~/.claude/CLAUDE.md (`claude_md`) and ~/.codex/AGENTS.md (`codex_md`); add rows to a project's
delegation table (`delegation`, with `<topic>` filled from --topic); write config files (`files`, {destination: source}:
a file that exists and differs is yours and is left alone; removing takes out, with `trash`, only one still unchanged);
set Claude Code settings (`settings`, dotted keys: a list gains or loses entries, a value is set or, on removal, taken
out if it still equals the preset's) and top-level keys of ~/.codex/config.toml (`codex_config`); name other presets
(`includes`). Presets sharing a `group` (the permission profiles) exclude each other: applying one takes out the
others' rule lists and sets its own values over theirs. Applying twice changes nothing. Pure standard library.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

HARNESS = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
PRESETS = os.path.join(HARNESS, "presets")
HOME = os.path.expanduser("~")
STABLE = os.path.join(HOME, "research-harness")          # links go through ~/research-harness when it is this harness
LINK_BASE = STABLE if os.path.realpath(STABLE) == HARNESS else HARNESS
SETTINGS = os.path.join(HOME, ".claude", "settings.json")
DOCS = {"claude_md": os.path.join(HOME, ".claude", "CLAUDE.md"), "codex_md": os.path.join(HOME, ".codex", "AGENTS.md")}
BIN = os.path.join(HOME, ".local", "bin")
CODEX_CONFIG = os.path.join(HOME, ".codex", "config.toml")


def names():
    return sorted(d for d in os.listdir(PRESETS) if os.path.exists(os.path.join(PRESETS, d, "preset.json")))


def load(name, out=None):
    """[(name, folder, manifest)]: the preset and every preset it includes, includes first, each once."""
    out = [] if out is None else out
    folder = os.path.join(PRESETS, name)
    if not os.path.exists(os.path.join(folder, "preset.json")):
        sys.exit(f"research-preset: no preset `{name}` (presets: {', '.join(names())})")
    m = json.load(open(os.path.join(folder, "preset.json")))
    for inc in m.get("includes", []):
        if inc not in [n for n, _, _ in out]:
            load(inc, out)
    if name not in [n for n, _, _ in out]:
        out.append((name, folder, m))
    return out


def same_cmd(a, b):
    norm = lambda c: " ".join(os.path.expanduser(t) for t in (c or "").split())   # noqa: E731
    return norm(a) == norm(b)


def short(path):
    return path.replace(HOME, "~", 1)


class Plan:
    """What applying (or removing) presets would change, file by file, kept in memory until write()."""

    def __init__(self, remove):
        self.remove, self.lines, self.links, self.conflicts, self.drop = remove, [], [], 0, []
        self.texts = {}                                   # path -> [old, new]
        self.settings = self.settings_old = None

    def text(self, path):
        if path not in self.texts:
            old = open(path).read() if os.path.exists(path) else ""
            self.texts[path] = [old, old]
        return self.texts[path]

    def say(self, changed, what, remove=None, quiet=False):
        if changed or not quiet:
            self.lines.append(f"  {('-' if (self.remove if remove is None else remove) else '+') if changed else '='} {what}")

    def path(self, cmd, rel):
        src, dst = os.path.join(LINK_BASE, rel), os.path.join(BIN, cmd)
        ours = os.path.islink(dst) and os.path.realpath(dst) == os.path.realpath(src)
        if self.remove:
            self.say(ours, f"{short(dst)} -> {rel}" + ("" if ours else " (not there)"))
            if ours:
                self.links.append((None, dst))
        elif ours:
            self.say(False, f"{short(dst)} -> {rel} (already)")
        elif os.path.lexists(dst) and not os.path.islink(dst):
            self.lines.append(f"  ! {short(dst)} exists and is not a link: left alone")
        else:
            self.say(True, f"{short(dst)} -> {rel}")
            self.links.append((src, dst))

    def load_settings(self):
        if self.settings is None:
            try:
                self.settings = json.load(open(SETTINGS)) if os.path.exists(SETTINGS) else {}
            except ValueError as e:
                sys.exit(f"research-preset: {short(SETTINGS)} is not valid JSON ({e}); fix it first, nothing changed")
            self.settings_old = json.dumps(self.settings, sort_keys=True)
        return self.settings

    def set_values(self, values, remove=None, quiet=False, keep=None):
        """Claude Code settings by dotted key. `keep` ({key: value}) is what the preset being applied sets: taking out
        another profile's entries never takes out one of those."""
        remove, keep = self.remove if remove is None else remove, keep or {}
        for key, val in values.items():
            *parents, last = key.split(".")
            node = self.load_settings()
            for k in parents:
                if not isinstance(node.get(k), dict):
                    if remove:
                        node = None
                        break
                    node[k] = {}
                node = node[k]
            cur = None if node is None else node.get(last)
            if isinstance(val, list):
                have = cur if isinstance(cur, list) else []
                for item in val:
                    present = item in have
                    if remove and present and item not in (keep.get(key) or []):
                        have.remove(item)
                        self.say(True, f"{key}: {item}", remove, quiet)
                    elif not remove and not present:
                        node[last] = have = have + [item]
                        self.say(True, f"{key}: {item}", remove, quiet)
                    else:
                        self.say(False, f"{key}: {item}" + (" (already)" if present else " (not there)"), remove, quiet)
                if remove and node is not None and last in node and not node[last]:
                    del node[last]
            elif remove:
                ours = cur == val and key not in keep
                if ours:
                    del node[last]
                self.say(ours, f"{key} = {json.dumps(val)}" + ("" if ours else " (not there)" if cur is None else
                                                                 f" (now {json.dumps(cur)}, left)"), remove, quiet)
            elif cur == val:
                self.say(False, f"{key} = {json.dumps(val)} (already)", remove, quiet)
            else:
                node[last] = val
                self.say(True, f"{key} = {json.dumps(val)}" + (f" (was {json.dumps(cur)})" if cur is not None else ""), remove, quiet)
        for k in [k for k, v in self.settings.items() if v == {}]:
            del self.settings[k]

    def codex(self, values, remove=None, quiet=False, keep=None):
        """Top-level `key = value` lines of ~/.codex/config.toml (above its first [table])."""
        remove, keep = self.remove if remove is None else remove, keep or {}
        t = self.text(CODEX_CONFIG)
        lines = t[1].split("\n") if t[1] else []
        if lines and lines[-1] == "":
            lines.pop()
        top = next((i for i, l in enumerate(lines) if l.lstrip().startswith("[")), len(lines))
        for key, val in values.items():
            want = f"{key} = {json.dumps(val)}"
            idx = next((i for i in range(top) if re.match(rf"\s*{re.escape(key)}\s*=", lines[i])), None)
            cur = lines[idx].strip() if idx is not None else None
            where = f"{short(CODEX_CONFIG)}: {want}"
            if remove:
                ours = cur == want and key not in keep
                if ours:
                    del lines[idx]
                    top -= 1
                self.say(ours, where + ("" if ours else " (not there)" if cur is None else f" (now `{cur}`, left)"), remove, quiet)
            elif cur == want:
                self.say(False, where + " (already)", remove, quiet)
            else:
                if idx is None:
                    lines.insert(top, want)
                    top += 1
                else:
                    lines[idx] = want
                self.say(True, where + (f" (was `{cur}`)" if cur else ""), remove, quiet)
        t[1] = "\n".join(lines) + ("\n" if lines else "")

    def hooks(self, hooks):
        table = self.load_settings().setdefault("hooks", {})
        for event, groups in hooks.items():
            for g in groups:
                for h in g["hooks"]:
                    have = any(same_cmd(h["command"], x.get("command")) for grp in table.get(event, [])
                               for x in grp.get("hooks", []))
                    if self.remove and have:
                        for grp in table.get(event, []):
                            grp["hooks"] = [x for x in grp.get("hooks", []) if not same_cmd(h["command"], x.get("command"))]
                        table[event] = [grp for grp in table[event] if grp["hooks"]]
                        if not table[event]:
                            del table[event]
                    elif not self.remove and not have:
                        table.setdefault(event, []).append({**{k: v for k, v in g.items() if k != "hooks"}, "hooks": [h]})
                    changed = have if self.remove else not have
                    self.say(changed, f"hook {event}: {h['command']}" + ("" if changed else " (already)" if have else " (not there)"))
        if not table:
            del self.settings["hooks"]

    def block(self, path, name, body):
        start, end = f"<!-- research-harness preset: {name} -->", f"<!-- /research-harness preset: {name} -->"
        t = self.text(path)
        i, j = t[1].find(start), t[1].find(end)
        new = "" if self.remove else f"{start}\n{body.rstrip()}\n{end}\n"
        if i >= 0 and j > i:
            j += len(end) + (t[1][j + len(end):j + len(end) + 1] == "\n")
            current = t[1][i:j]
            t[1] = t[1][:i] + new + t[1][j:]
            changed = current != new
        else:
            changed = not self.remove
            if changed:
                t[1] += ("" if not t[1] else "\n" if t[1].endswith("\n") else "\n\n") + new
        self.say(changed, f"{short(path)}: rules of `{name}`" + ("" if changed else " (already)" if not self.remove else " (not there)"))

    def file(self, dest, body):
        path = os.path.expanduser(dest)
        t = self.text(path)
        exists = os.path.exists(path)
        if self.remove:
            ours = exists and t[0] == body
            self.say(ours, short(path) + ("" if ours else " (not there)" if not exists else " (yours: changed, left alone)"))
            if ours:
                self.drop.append(path)
        elif not exists:
            t[1] = body
            self.say(True, short(path))
        elif t[0] == body:
            self.say(False, f"{short(path)} (already)")
        else:
            self.conflicts += 1
            self.lines.append(f"  ! {short(path)} exists and differs (yours): left alone; to take the preset's, move it "
                              f"aside with `trash` and apply again")

    def rows(self, path, rows):
        t = self.text(path)
        if not t[0]:
            sys.exit(f"research-preset: no {path} (run research-init in the project first)")
        lines = t[1].split("\n")
        head = next((i for i, l in enumerate(lines) if l.strip().startswith("|---")), None)
        if head is None:
            sys.exit(f"research-preset: {path} has no delegation table (| work | goes to | how |)")
        have = {l.strip() for l in lines}
        if self.remove:
            lines = [l for l in lines if l.strip() not in rows]
        else:
            end = head + 1
            while end < len(lines) and lines[end].strip().startswith("|"):
                end += 1
            lines[end:end] = [r for r in rows if r not in have]
        t[1] = "\n".join(lines)
        for r in rows:
            changed = (r in have) == self.remove
            self.say(changed, f"{short(path)}: row `{r[:70]}…`" + ("" if changed else " (already)" if r in have else " (not there)"))

    def changed(self):
        return any(o != n for o, n in self.texts.values()) or bool(self.links) or bool(self.drop) or (
            self.settings is not None and json.dumps(self.settings, sort_keys=True) != self.settings_old)

    def write(self):
        """Write every change. Returns the backup of ~/.claude/settings.json it made before rewriting it, if any."""
        backup = None
        if self.settings is not None and json.dumps(self.settings, sort_keys=True) != self.settings_old:
            os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
            if os.path.exists(SETTINGS):
                backup = base = f"{SETTINGS}.bak-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
                n = 1
                while os.path.exists(backup):          # two applies in one second must not overwrite the first backup
                    backup, n = f"{base}~{n}", n + 1
                shutil.copy2(SETTINGS, backup)
            with open(SETTINGS + ".tmp", "w") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.replace(SETTINGS + ".tmp", SETTINGS)
        for path, (old, new) in self.texts.items():
            if old != new:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    f.write(new)
        for path in self.drop:                      # unchanged since the preset wrote it: nothing of yours is lost
            subprocess.run([sys.executable, os.path.join(HARNESS, "extras", "trash.py"), path], check=True,
                           stdout=subprocess.DEVNULL)
        for src, dst in self.links:
            if os.path.lexists(dst):
                os.remove(dst)                      # a link only: path() leaves a real file alone
            if src:
                os.chmod(src, os.stat(src).st_mode | 0o111)
                os.makedirs(BIN, exist_ok=True)
                os.symlink(src, dst)
        return backup


def group_members(group):
    return [n for n in names() if json.load(open(os.path.join(PRESETS, n, "preset.json"))).get("group") == group]


def plan(name, remove=False, project=None, topic=None, quiet_project=False):
    p = Plan(remove)
    for n, folder, m in load(name):
        if m.get("group") and not remove:                # one profile at a time: take out the others' rules first
            for other in group_members(m["group"]):
                if other != n:
                    om = json.load(open(os.path.join(PRESETS, other, "preset.json")))
                    before = len(p.lines)
                    rules = {k: v for k, v in om.get("settings", {}).items() if isinstance(v, list)}   # values: overwritten below
                    p.set_values(rules, remove=True, quiet=True, keep=m.get("settings", {}))
                    if len(p.lines) > before:
                        p.lines.insert(before, f"{other} (same group `{m['group']}`): taken out")
        p.lines.append(f"{n}: {m.get('about', '')}")
        if m.get("settings"):
            p.set_values(m["settings"])
        if m.get("codex_config"):
            p.codex(m["codex_config"])
        for cmd, rel in m.get("path", {}).items():
            p.path(cmd, rel)
        if m.get("hooks"):
            p.hooks(m["hooks"])
        for dest, src in m.get("files", {}).items():
            p.file(dest, open(os.path.join(folder, src)).read())
        for key, doc in DOCS.items():
            if m.get(key):
                p.block(doc, n, open(os.path.join(folder, m[key])).read())
        if m.get("delegation"):
            text = open(os.path.join(folder, m["delegation"])).read()
            if not project:
                if not quiet_project:
                    p.lines.append(f"  · project part skipped: give --project <dir>" + (" --topic <field>" if "<topic>" in text else ""))
                continue
            if "<topic>" in text and not topic:
                sys.exit(f"research-preset: `{n}` needs --topic <field>: the field whose work goes to Codex (e.g. biology)")
            rows = [r.strip() for r in text.replace("<topic>", topic or "").splitlines() if r.strip().startswith("|")]
            p.rows(os.path.join(project, "docs", "agents", "delegation.md"), rows)
        for tool in m.get("needs", []):
            if not shutil.which(tool):
                p.lines.append(f"  ! `{tool}` is not on PATH here: this preset assumes it")
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--project")
    ap.add_argument("--topic")
    a = ap.parse_args()
    if not a.name:
        for n in names():
            m = json.load(open(os.path.join(PRESETS, n, "preset.json")))
            p = plan(n, quiet_project=True)
            only_project = all(not (k in mm) for _, _, mm in load(n)
                               for k in ("path", "hooks", "claude_md", "codex_md", "files", "settings", "codex_config"))
            state = ("project preset" if only_project else "not fully applied" if p.changed() else
                     "yours differs" if p.conflicts else "applied")
            print(f"{n:16} [{state}]  {m.get('about', '')}" + (f" (group `{m['group']}`: pick one)" if m.get("group") else ""))
        print("\nresearch-preset <name> --dry-run shows what applying one would change.")
        return
    p = plan(a.name, a.remove, a.project, a.topic)
    print("\n".join(p.lines))
    if not p.changed():
        print("nothing to change")
    elif a.dry_run:
        print("dry run: nothing changed")
    else:
        backup = p.write()
        print("done" + (f"; the old settings are kept as {short(backup)}" if backup else ""))


if __name__ == "__main__":
    main()
