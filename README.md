# sliu-skill

Agent skills for running research projects with Claude Code (and Codex), built on [Matt Pocock's skills](https://github.com/mattpocock/skills). Where a skill has a counterpart in Matt's repo, its wording follows his as closely as possible; every place it differs **in logic** is listed under [Differences from Matt's skills](#differences-from-matts-skills).

## Install

```bash
git clone https://github.com/Steven51516/sliu-skill ~/research-harness
~/research-harness/install.sh
```

`install.sh` links every skill into `~/.claude/skills` and `~/.agents/skills` (Codex), puts three commands on your PATH (`research-status`, `research-migrate`, `team-up`), and removes links left by skills that were removed or renamed. Edit a file here and the change reaches every project at once; nothing is copied.

## How it fits together

Research is a search, not a build, so the plan never stops changing. The vocabulary is Matt's:

- A **map** charts the way to one **destination**: the decisions made so far, the **fog** not yet sharp enough to ticket (*Not yet specified*), and what is *Out of scope*. Its **Notes** name the benchmark every ticket is scored on.
- A **ticket** is one question on the map, sized to one agent session. An `experiment` ticket resolves by measurement against a **pre-registration**, its success and stop criteria written before anything runs. Runs, arms and smoke tests are **assets** of a ticket, never tickets.
- Maps and tickets live in the project's **issue tracker** (`docs/agents/issue-tracker.md`): GitHub, GitLab, or local markdown under `maps/`.

| You want to… | Run |
|---|---|
| set up a project (scope, issue tracker, team) | `/research-init <name>` |
| pick a project back up ("where are we?") | `/resume` (a new session calls it on its own) |
| open a new map | `/wayfinder "<loose idea>"` |
| add a ticket | `/research-ticket <map> "<question>"` |
| work one ticket | `/research-work <ticket>` |
| work a map's frontier in parallel, or overnight | `/research-drive <map>` (`/loop` it) |
| re-plan a map | `/wayfinder <map> --rechart` |
| run a long-lived team (desk, driver, workers) | `team-up <map>` in a herdr pane, or `/team <role>` |

## Skills

| Skill | Relation to Matt's repo | What it does |
|---|---|---|
| `wayfinder` | adapted from `wayfinder` | chart a map, work through it, re-chart it |
| `research` | copied from `research` | read primary sources in the background, write cited notes |
| `grilling` | copied from `grilling` | interview the user in rounds until shared understanding |
| `codebase-design`, `handoff`, `writing-for-agents` | copied | deep-module vocabulary; compact a session; writing for agents |
| `diagnose` | adapted from `diagnosing-bugs` | a feedback loop before any bug or wrong-looking result is called fixed |
| `domain-modeling`, `retro`, `wait-what`, `improve-codebase-architecture` | adapted | glossary and decisions; retrospectives; re-pitch; deep modules for research code |
| `research-init` | counterpart of `setup-matt-pocock-skills` | set up a project: scope, issue tracker, team |
| `research-ticket` | counterpart of `to-tickets` | tickets with blocking edges and pre-registrations |
| `research-work` | counterpart of `implement` | work one ticket end to end |
| `research-drive` | counterpart of `implement-spec` | keep a map's frontier moving with parallel workers |
| `rigor` | counterpart of `tdd` + `code-review` | check a result is fair before it counts; one review per ticket |
| `run-card`, `diagnosis-record` | none | reproduction record of an important run; diagnosis record of evaluation results |
| `resume`, `team` | none | report where a project stands; run a project as several long-lived sessions |

## Differences from Matt's skills

Only differences in logic; renamed paths, examples and tracker wiring are not listed.

**Maps execute.** Matt's `wayfinder` plans by default and lets an effort's Notes carry execution into the map. A research map always does: its Notes name the benchmark (eval set and N, metric, scorer, decoding), the baselines on it, the reference recipe and what may be done without asking, and an added ticket type, **`experiment`**, resolves by measurement through `research-work`.

**Pre-registration.** An experiment ticket's success and stop criteria are written and approved before it runs, and never edited after results are seen (amendments are appended and dated). Matt's tickets have no such gate.

**Runs are assets.** Every run, arm, smoke test or variant is a row in its ticket's Assets table; a new run never gets a new ticket, a new question does.

**Re-chart.** `wayfinder` has a third mode, `--rechart`: change the destination or Notes on evidence (the human decides), split a second destination into a new map, rebuild Decisions so far, consolidate closed tickets.

**The local tracker keeps code with tickets.** `maps/<id>-<slug>/map.md`, and one *folder* per ticket (`tickets/NN-<slug>/ticket.md` plus its code and small results), with YAML front matter. `research-status` generates `STATUS.md`, lists the frontier and checks the maps. Matt's local tracker is `.scratch/<effort>/map.md` with one file per ticket. `research-init` proposes GitHub or GitLab when the folder has such a remote, else local markdown (Matt defaults to GitHub).

**One review per ticket, on the result.** `rigor` replaces `tdd` and `code-review` for research: while working, the four checks (same benchmark, numbers from files, no leakage, every difference from the reference recorded) and controls only for a new or changed pipeline; at close, one fresh reviewer session writes PASS/FAIL lines for *Fair*, *Answers the question* (no claim beyond the numbers) and *Code*. Matt reviews a diff on Standards and Spec.

**`research-work` runs jobs, not a red-green loop.** Smoke-test only code never run before; otherwise the real run's first steps are the smoke check; jobs run the way the project's scope file says; failures are classified (execution, measurement, data, method, hypothesis) before anything is called negative. No commits per ticket.

**`research-drive` grows the graph.** Matt's `implement-spec` works a fixed set of tickets to completion and merges branches. Here one call is one pass (repeat with `/loop`): merge finished tickets after their review, dispatch the frontier, and when it runs dry, file the next tickets from the fog inside the map's Notes. What needs the human becomes a `grilling` ticket.

**Scope files.** Where a project runs (scheduler, storage, GPUs, network) lives in one scope file the project imports (`scopes/`), so the skills never name a machine.

**Team layer.** `team` and `team-up` run the same skills as long-lived sessions: a desk the human talks to, a driver running `research-drive` under `/loop`, and workers running `research-work`, with a roster and short messages (`skills/team/TEAM-PROTOCOL.md`). Who plans, works and reviews (e.g. Claude plans, Codex works and reviews) is a per-project table, `docs/agents/team.md`.

**Research code, not product code.** `improve-codebase-architecture` and `domain-modeling` keep decisions in `docs/decisions.md` instead of ADRs, scope to the shared research code, and treat checks as the test surface; `diagnose` works on research code and results that look wrong, not only bugs.

**Run cards and diagnosis records.** A run that affects a milestone gets a one-page reproduction record (`run-card`); diagnosing evaluation results gets a structured record (`diagnosis-record`).

## Layout

```
skills/      one folder per skill
rules/       style.md (honesty, what always needs the human's OK, code, docs), layout.md (project folders)
scopes/      where projects run: README.md (what a scope answers), one file per cluster
templates/   files research-init writes into a project: AGENTS.md, CLAUDE.md, OVERVIEW.md, team.md, issue-tracker-*.md
tools/       status.py (research-status), migrate_to_maps.py (research-migrate), team-up.sh
licenses/    licences of copied and adapted third-party skills
install.sh   (re)creates the links; safe to run again
```

## How to change things

| I want to… | Edit |
|---|---|
| change a machine's rules (scheduler, storage, GPU sharing, network) | that scope file, e.g. `scopes/engaging.md` |
| change how the agent writes code, commits, reports, or what always needs my OK | `rules/style.md` |
| change where one project's maps live | that project's `docs/agents/issue-tracker.md` |
| change who plans, works and reviews in one project | that project's `docs/agents/team.md` |
| add a rule for one project only | that project's `AGENTS.md`, under "Project notes" |
| add a skill | `skills/<name>/SKILL.md`, then `./install.sh` |

Skill descriptions load when a session starts, so a new skill or a changed `description:` needs a new session; a changed body applies the next time it is read.

## Credits

From [mattpocock/skills](https://github.com/mattpocock/skills) (MIT, `licenses/mattpocock-skills-MIT.txt`; synced from commit `5beb35b`): copied `research`, `grilling`, `codebase-design`, `handoff`, `writing-for-agents`, the GitHub and GitLab tracker docs; adapted `wayfinder`, `diagnose` (from `diagnosing-bugs`), `domain-modeling`, `retro`, `wait-what`, `improve-codebase-architecture`. Failure classification and the "no viable branch" stop are distilled from [CoAutoResearch](https://github.com/YihongT/CoAutoResearch).
