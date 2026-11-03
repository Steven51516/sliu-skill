# sliu-skill (the research harness)

You are editing the harness itself: skills, tools and docs that research projects use. You are not in a project.

- **Read first:** `README.md` (what each part is for) and `CONTRIBUTING.md` (how a change is made and checked).
- **Matt's wording first.** A skill with a counterpart in [mattpocock/skills](https://github.com/mattpocock/skills)
  follows his wording; every change in logic is listed in the README's "Differences from Matt's skills".
- **Lean.** Every line a session loads costs every session. Prefer deleting to adding; a skill body stays short and links
  its details. A mistake that recurs gets a check that fails (`research-status --check`, a tool guard,
  `scripts/check.py`), not another sentence.
- **No specifics in skills.** A machine, a person, a field or a project goes in a scope file, `STYLE.md` or a project's
  `AGENTS.md`, never in a skill.
- **Rejected ideas** are in `.out-of-scope/`; read the matching one before proposing something similar.
- **Before committing:** `python3 scripts/check.py` passes, and `CHANGELOG.md` has a line under Unreleased.
- `tools/gui/` (the Research Desk app) has its own README; keep changes there small unless the app is the task.
- Problems found while using the harness go to `FEEDBACK.md` (local, gitignored), one line each; delete the line when
  its fix lands.
