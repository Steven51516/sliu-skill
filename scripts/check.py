#!/usr/bin/env python3
"""check: the repository's structural checks, run before every commit and in CI. Exits 1 and lists every problem.

  python3 scripts/check.py

- every skill sits at skills/<core|personal|team>/<name>/SKILL.md, with frontmatter whose `name` is the folder name
  and whose `description` is set (at most 1024 characters)
- every relative link in a skill's markdown files points to a file that exists (template placeholders, `[<...>](...)`,
  are skipped)
- every Python tool compiles and every shell script parses (`bash -n`)
- every preset (presets/<name>/preset.json) parses, has an `about`, and names only presets and files that exist
- the README names every skill and every preset
- Research Desk never floods a remote host with ssh (tools/gui/tests/remote_calls_test.py, ~20 s)
- closing a worker never types an exit over and over (tools/tests/team_close_test.py)
- every module of Research Desk's page parses as a module, when `node` is installed (a name declared twice in one
  scope is caught here, not in the browser)
- every skill another file calls by name (`Skill tool with "x"`, "the `x` skill", `/x` in a code span or a prompt string)
  exists in git: a removed, renamed or local-only skill fails here instead of in a user's session
"""
import json
import pathlib
import re
import shutil
import subprocess
import tempfile
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GROUPS = {"core", "personal", "team"}   # skills/local/ is gitignored
LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
SKIP = {"node_modules", "archive", "__pycache__", ".git"}
BUILTIN = {"loop", "btw", "effort", "model", "exit", "clear", "compact", "autocompact", "config", "hooks", "resume", "login"}
NAMED = [re.compile(r"Skill tool with [\"`]([a-z0-9-]+)[\"`]"), re.compile(r"the `([a-z0-9-]+)` skill")]
SPAN = re.compile(r"`([^`\n]+)`")
SLASH = re.compile(r"(?:^|\s)/([a-z][a-z0-9-]*)(?=\s|$)")            # `/name ...` in a code span, never a path
PROMPT = re.compile(r"[\"'`]/([a-z][a-z0-9-]*)[ {]")                 # a prompt string in code: "/team $3"


def skill_refs(text, code=False):
    """(line, name) for each skill a file calls by name."""
    for i, line in enumerate(text.splitlines(), 1):
        found = PROMPT.findall(line) if code else [n for r in NAMED for n in r.findall(line)]
        if not code:
            found += [n for span in SPAN.findall(line) for n in SLASH.findall(span)]
        for n in found:
            yield i, n


def frontmatter(text):
    if not text.startswith("---\n"):
        return None
    head = text[4:].split("\n---", 1)[0]
    out = {}
    for line in head.splitlines():
        m = re.match(r"([A-Za-z-]+):\s*(.*)", line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"')
    return out


def files(pattern):
    """Files git tracks that match the pattern: local-only skills (gitignored) and untracked scratch are skipped."""
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True).stdout.split("\n")
    tracked = {ROOT / p for p in out if p}
    return [p for p in ROOT.glob(pattern) if p in tracked and not SKIP & set(p.relative_to(ROOT).parts)]


def main():
    problems, names = [], []
    for skill in sorted(files("skills/*/*/SKILL.md")):
        group, name = skill.parent.parent.name, skill.parent.name
        rel = skill.relative_to(ROOT)
        names.append(name)
        if group not in GROUPS:
            problems.append(f"{rel}: group `{group}` is not one of {sorted(GROUPS)}")
        fm = frontmatter(skill.read_text())
        if fm is None:
            problems.append(f"{rel}: no frontmatter")
            continue
        if fm.get("name") != name:
            problems.append(f"{rel}: name `{fm.get('name')}` differs from its folder `{name}`")
        if not fm.get("description"):
            problems.append(f"{rel}: no description")
        for line in skill.read_text().split("\n---", 1)[0].splitlines()[1:]:    # as a strict YAML parser reads it
            m = re.match(r"([A-Za-z-]+):\s*(.+)", line)
            if m and m.group(2)[0] not in "\"'[" and (": " in m.group(2) or m.group(2)[0] in "{}*&!|>%@`#"):
                problems.append(f"{rel}: `{m.group(1)}` needs quotes (it holds \": \" or starts with a YAML sign), or a "
                                f"strict installer skips the skill")
        if fm.get("description") and len(fm["description"]) > 1024:
            problems.append(f"{rel}: description is {len(fm['description'])} characters (max 1024)")
    for doc in sorted(files("skills/**/*.md")):
        for text, target in LINK.findall(doc.read_text()):
            path = target.split("#", 1)[0]
            if text.startswith("<") or not path or re.match(r"[a-z]+:", path) or path.startswith(("~", "/", "<")):
                continue                              # a template placeholder, a URL, an anchor or an absolute path
            if not (doc.parent / path).exists():
                problems.append(f"{doc.relative_to(ROOT)}: link to a missing file `{target}`")
    for py in sorted(files("tools/**/*.py") + files("extras/*.py") + files("scripts/*.py") + files("skills/**/*.py")):
        try:
            compile(py.read_text(), str(py), "exec")
        except SyntaxError as e:
            problems.append(f"{py.relative_to(ROOT)}:{e.lineno}: does not compile: {e.msg}")
    for sh in sorted(files("**/*.sh")):
        r = subprocess.run(["bash", "-n", str(sh)], capture_output=True, text=True)
        if r.returncode:
            problems.append(f"{sh.relative_to(ROOT)}: does not parse: {r.stderr.strip()[:200]}")
    readme = (ROOT / "README.md").read_text()
    problems += [f"README.md: skill `{n}` is not named" for n in names if f"`{n}`" not in readme]
    for pj in sorted(files("presets/*/preset.json")):
        rel, name = pj.relative_to(ROOT), pj.parent.name
        try:
            m = json.loads(pj.read_text())
        except ValueError as e:
            problems.append(f"{rel}: not valid JSON: {e}")
            continue
        if not m.get("about"):
            problems.append(f"{rel}: no `about`")
        if f"`{name}`" not in readme:
            problems.append(f"README.md: preset `{name}` is not named")
        problems += [f"{rel}: includes `{i}`, which is not a preset" for i in m.get("includes", [])
                     if not (ROOT / "presets" / i / "preset.json").exists()]
        problems += [f"{rel}: `{k}` file `{m[k]}` is missing" for k in ("claude_md", "codex_md", "delegation")
                     if m.get(k) and not (pj.parent / m[k]).exists()]
        problems += [f"{rel}: `{c}` links to `{p}`, which is missing" for c, p in m.get("path", {}).items() if not (ROOT / p).exists()]
        problems += [f"{rel}: file `{s}` for `{d}` is missing" for d, s in m.get("files", {}).items() if not (pj.parent / s).exists()]
        problems += [f"{rel}: `{k}` must be an object of keys and values" for k in ("settings", "files", "path")
                     if k in m and not isinstance(m[k], dict)]
        cmds = [h.get("command", "") for gs in m.get("hooks", {}).values() for g in gs for h in g.get("hooks", [])]
        problems += [f"{rel}: hook runs `{t}`, which is missing" for c in cmds for t in c.split()
                     if "research-harness/" in t and not (ROOT / t.split("research-harness/", 1)[1]).exists()]
    docs = [f for f in files("**/*.md") if f.name != "CHANGELOG.md"]   # the changelog names removed skills on purpose
    code = files("tools/**/*.py") + files("tools/**/*.sh") + files("tools/gui/web/js/*.js")
    for f in sorted(docs + code):
        for line, n in skill_refs(f.read_text(errors="replace"), code=f not in docs):
            if n not in names and n not in BUILTIN:
                problems.append(f"{f.relative_to(ROOT)}:{line}: calls skill `{n}`, which is not in skills/ (removed, renamed or local only)")
    test = ROOT / "tools/gui/tests/remote_calls_test.py"
    if test.exists():
        r = subprocess.run([sys.executable, str(test)], capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL)
        if r.returncode:
            problems += [l for l in r.stdout.splitlines() if l.startswith("remote_calls_test:") and "FAILED" not in l] \
                or [f"remote_calls_test: exit {r.returncode}: {(r.stderr or r.stdout).strip()[-300:]}"]
    node = shutil.which("node")
    if node:                               # as .mjs: `node --check x.js` takes a file for a script and passes such an error
        with tempfile.TemporaryDirectory() as tmp:
            for f in files("tools/gui/web/js/*.js"):
                copy = pathlib.Path(tmp) / (f.stem + ".mjs")
                copy.write_text(f.read_text())
                r = subprocess.run([node, "--check", str(copy)], capture_output=True, text=True, timeout=60)
                if r.returncode:
                    why = next((l for l in r.stderr.splitlines() if "Error" in l), r.stderr.strip()[-200:])
                    problems.append(f"{f.relative_to(ROOT)}: does not parse as a module: {why}")
    test = ROOT / "tools/tests/team_close_test.py"
    if test.exists():
        r = subprocess.run([sys.executable, str(test)], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        if r.returncode:
            problems += [l for l in r.stdout.splitlines() if l.startswith("team_close_test:") and "FAILED" not in l] \
                or [f"team_close_test: exit {r.returncode}: {(r.stderr or r.stdout).strip()[-300:]}"]
    for p in problems:
        print(p)
    print(f"check: {len(names)} skills, {len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
