# Contributing

Issues are welcome: a bug in a skill or tool, a step that confused you, or an idea. Describe the problem and how to
reproduce it; the fix is easier to design from the problem than from a finished rewrite. Some mechanisms were tried or
weighed and left out on purpose; an issue that proposes one may get a short answer saying why.

## How a change is made

- **Start from a real failure.** A change answers something that went wrong in a real project (a log line, a message, a
  tool's output), not a hypothetical. Write it in the commit message.
- **A check before a sentence.** A mistake that recurs is fixed with something that fails (a `research-status --check`
  rule, a guard in a tool, `scripts/check.py`), not another instruction. Instructions are for judgment calls.
- **Matt's wording first.** A skill with a counterpart in [mattpocock/skills](https://github.com/mattpocock/skills) keeps
  his wording where the logic is the same; every difference in logic goes in the README's "Differences from Matt's
  skills".
- **Short skills.** `SKILL.md` holds the steps; details go in a linked file next to it. The `writing-for-agents` skill has
  the rules. Frontmatter: `name` equal to the folder name, a `description` that says what it does and when to use it,
  `disable-model-invocation: true` for a skill only the user should start.
- **No specifics.** Machines, people, fields and projects belong in scope files, `STYLE.md` or a project's `AGENTS.md`.

## Checking a change

1. `python3 scripts/check.py`: skill frontmatter, links inside skills, tool syntax, the README's skill lists. CI runs it
   on every push.
2. A skill or tool that touches the tracker: `research-status <project> --check` on a real or throwaway project.
3. A change to team mode: start a team on a throwaway project with two tiny tickets (`team-up <map>`, or `--codex`), and
   watch a worker open, answer and report.
4. Add a line under **Unreleased** in `CHANGELOG.md`. A release moves those lines under a version and tags it (`vX.Y.Z`).

## Layout

`skills/core/` is the research loop every project needs; `skills/personal/` holds everyday helpers; `skills/optional/`
holds what a project opts into. A new skill goes in one of them, then `./install.sh` links it.
