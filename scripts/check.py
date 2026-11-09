#!/usr/bin/env python3
"""check: the repository's structural checks, run before every commit and in CI. Exits 1 and lists every problem.

  python3 scripts/check.py

- every skill sits at skills/<core|personal|team>/<name>/SKILL.md, with frontmatter whose `name` is the folder name
  and whose `description` is set (at most 1024 characters)
- every relative link in a skill's markdown files points to a file that exists (template placeholders, `[<...>](...)`,
  are skipped)
- every Python tool compiles and every shell script parses (`bash -n`)
- the README names every skill
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GROUPS = {"core", "personal", "team"}   # skills/local/ is gitignored
LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
SKIP = {"node_modules", "archive", "__pycache__", ".git"}


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
        elif len(fm["description"]) > 1024:
            problems.append(f"{rel}: description is {len(fm['description'])} characters (max 1024)")
    for doc in sorted(files("skills/**/*.md")):
        for text, target in LINK.findall(doc.read_text()):
            path = target.split("#", 1)[0]
            if text.startswith("<") or not path or re.match(r"[a-z]+:", path) or path.startswith(("~", "/", "<")):
                continue                              # a template placeholder, a URL, an anchor or an absolute path
            if not (doc.parent / path).exists():
                problems.append(f"{doc.relative_to(ROOT)}: link to a missing file `{target}`")
    for py in sorted(files("tools/**/*.py") + files("scripts/*.py") + files("skills/**/*.py")):
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
    for p in problems:
        print(p)
    print(f"check: {len(names)} skills, {len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
