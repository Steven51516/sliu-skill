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

- A **map** charts the way to one **destination**: the decisions made so far, the **fog** not yet sharp enough to ticket (*Not yet specified*), and what is *Out of scope*. Its **Notes** hold the domain and standing preferences; its **Contract** names the benchmark every ticket is scored on (or `none`), the reference recipe, and what may be done without asking.
- A **ticket** is one question on the map, sized to one agent session. An `experiment` ticket resolves by measurement against a **pre-registration**, its success and stop criteria written before anything runs. Runs, arms and smoke tests are **assets** of a ticket, never tickets.
- Maps and tickets live in the project's **issue tracker** (`docs/agents/issue-tracker.md`): GitHub, GitLab, or local markdown under `maps/`.

| You want to… | Run |
|---|---|
| set up a project (scope, issue tracker, delegation) | `/research-init <name>` |
| pick a project back up ("where are we?") | `/resume` (a new session calls it on its own) |
| open a new map from what you already discussed | `/to-map` |
| open a new map from a loose idea (it interviews you) | `/wayfinder "<loose idea>"` |
| add a ticket | `/to-tickets <map> "<question>"` |
| work one ticket | `/research-work <ticket>` |
| work a map's frontier in parallel, or overnight | `/research-drive <map>` (`/loop` it) |
| re-plan a map | `/wayfinder <map> --rechart` |
| run a long-lived team (desk, driver, implementers) | `team-up <map>` in a herdr pane, or `/team <role>` |

## Skills

| Skill | Relation to Matt's repo | What it does |
|---|---|---|
| `wayfinder` | adapted from `wayfinder` | chart a map, work through it, re-chart it |
| `research` | copied from `research` | read primary sources in the background, write cited notes |
| `grilling` | copied from `grilling` | interview the user in rounds until shared understanding |
| `prototype` | copied from `prototype` | a throwaway prototype that answers a design question (a `prototype` ticket) |
| `codebase-design`, `handoff`, `writing-for-agents` | copied | deep-module vocabulary; compact a session; writing for agents |
| `diagnose` | adapted from `diagnosing-bugs` | a feedback loop before any bug or wrong-looking result is called fixed |
| `domain-modeling`, `retro`, `wait-what`, `improve-codebase-architecture` | adapted | glossary and decisions; retrospectives; re-pitch; deep modules for research code |
| `research-init` | counterpart of `setup-matt-pocock-skills` | set up a project: scope, issue tracker, delegation |
| `to-map` | adapted from `to-spec` | turn the conversation into a map, without an interview |
| `to-tickets` | adapted from `to-tickets` | question tickets with blocking edges and pre-registrations |
| `research-work` | counterpart of `implement` | work one ticket end to end |
| `research-drive` | counterpart of `implement-spec` | keep a map's frontier moving with parallel implementer subagents |
| `rigor` | counterpart of `tdd` | the rules for a trustworthy answer, followed while you work |
| `review` | adapted from `code-review` | review an answer on three axes (Fair, Spec, Code) before it enters the map |
| `run-card`, `diagnosis-record` | none | reproduction record of an important run; diagnosis record of evaluation results |
| `resume`, `team` | none | report where a project stands; run a project as several long-lived sessions |

## Differences from Matt's skills

Only differences in logic; renamed paths, examples and tracker wiring are not listed.

**Maps execute, under a Contract.** Matt's `wayfinder` plans by default and lets an effort's Notes carry execution into the map. A research map always does, through a section Matt doesn't have, `## Contract`, after his Notes: the **benchmark** (eval set and N, metric, scorer, decoding) and the baselines on it, or `none` when the map measures nothing or hasn't chosen yet; the **reference recipe**; and what may be done **without asking**. Only the user changes it. Matt's Notes keep their meaning (domain, skills to consult, standing preferences). An added ticket type, **`experiment`**, resolves by measurement through `research-work`.

**Pre-registration.** An experiment ticket's success and stop criteria are written and approved before it runs, and never edited after results are seen (amendments are appended and dated). Matt's tickets have no such gate.

**Runs are assets.** Every run, arm, smoke test or variant is a row in its ticket's Assets table; a new run never gets a new ticket, a new question does.

**Re-chart.** `wayfinder` has a third mode, `--rechart`: change the destination or Contract on evidence (the human decides), split a second destination into a new map, rebuild Decisions so far, consolidate closed tickets.

**The local tracker keeps code with tickets.** `maps/<id>-<slug>/map.md`, and one *folder* per ticket (`tickets/NN-<slug>/ticket.md` plus its code and small results), with YAML front matter. `research-status` generates `STATUS.md`, lists the frontier and checks the maps. Matt's local tracker is `.scratch/<effort>/map.md` with one file per ticket. `research-init` proposes GitHub or GitLab when the folder has such a remote, else local markdown (Matt defaults to GitHub).

**Rigor and review, on the result.** `rigor` stands where `tdd` does: rules followed while working (verify the measurement, same benchmark, numbers from files with the full denominator, no leakage, every difference recorded, gains beat the noise), applied by ticket type: all of them for an experiment, the measurement and numbers for a task that builds something later tickets use, none for reading, grilling or other tasks. `review` adapts `code-review`: Matt's Standards and Spec axes become **Fair** (the `rigor` rules) and **Spec** (the pre-registered rule, and no claim beyond the numbers), plus a **Code** axis on the code behind the result, each in a parallel sub-agent; it runs once per ticket whose answer later work relies on.

**`research-work` runs jobs, not a red-green loop.** Smoke-test only code never run before; otherwise the real run's first steps are the smoke check; jobs run the way the project's scope file says; failures are classified (execution, measurement, data, method, hypothesis) before anything is called negative. No commits per ticket.

**`research-drive` grows the graph.** Matt's `implement-spec` works a fixed set of tickets to completion and merges branches. Here one call is one pass (repeat with `/loop`): merge finished tickets after their review, dispatch the frontier, and when it runs dry, file the next tickets from the fog inside the map's Contract. What needs the human becomes a `grilling` ticket.

**Milestones and closing maps.** A map closes (`status: closed`) when its destination is reached or a measured answer says it can't be, as Matt's map issue closes. A Decisions-so-far line whose answer changes the project's route is tagged `[milestone]`, in the map that produced it; the local tracker's generated `STATUS.md` opens with every such line, then the open maps, what waits on the user, what is running and the frontier. `research-status --check` also catches dependency cycles, unknown statuses, prerequisites that are parked or superseded by an unfinished replacement, and resolved tickets without an answer.

**Scope files.** Where a project runs (scheduler, storage, GPUs, network) lives in one scope file the project imports (`scopes/`), so the skills never name a machine.

**Delegation is a project setting, not a role.** The skills only use a few verbs: *delegate* a task, *spin up a subagent* or *a background agent*, *use implementer subagents* (sessions that each work one ticket), *review*, *ask the user*. The project's `docs/agents/delegation.md` says where each goes, the way Matt's issue-tracker doc says where a ticket is published. Delegating is optional: each session does a task itself or delegates it as it judges. The doc only holds the project's rules, each a must for the work it matches: by topic, kind of work or role (e.g. biology-related coding, analysis, paper reading and review go to Codex). Any session may delegate, including an implementer.

**Team layer, optional and separate.** `team` and `team-up` run the same skills as long-lived sessions: a desk the human talks to, a driver running `research-drive` under `/loop`, and implementers running `research-work`, with a roster and short messages (`skills/team/TEAM-PROTOCOL.md`). Two verbs resolve to the team inside team sessions: an implementer subagent becomes an implementer pane, and asking the user goes through the desk. The core skills never mention the team, and the team layer only depends on them.

**Per-skill differences**, beyond the vocabulary above:

- `to-map` (vs `to-spec`): it writes a map, not a spec: the benchmark replaces the test seams, the questions you can see coming (Not yet specified) replace the user stories, the decisions already made open Decisions so far, and it ends by calling `to-tickets` for the questions that are already sharp.
- `to-tickets`: tickets are questions, not vertical slices; the fog-or-ticket test and "runs are assets" replace the slicing and wide-refactor rules; the quiz also checks success and stop criteria; an experiment's body carries its pre-registration.
- `research-work` (vs `implement`): no TDD or commits per ticket; jobs, smoke checks, failure classification, `rigor` and `review` as above.
- `to-tickets`, `research-work` and `research-drive` can be called by the model, not only by the user (Matt's counterparts are user-invoked), because a driver files and dispatches tickets itself.
- `research-init` (vs `setup-matt-pocock-skills`): adds the scope and delegation sections and drops triage labels; the domain docs record decisions in `docs/decisions.md`; it keeps both `AGENTS.md` and `CLAUDE.md` (Codex reads only `AGENTS.md`), where Matt edits one of them.
- `diagnose` (vs `diagnosing-bugs`): also covers results that look wrong; a tiny-config run and an invariant probe replace the HTTP and browser loops; the regression check is a check script, re-run on the production path (real launcher, data and GPU count); a bug that invalidated results is a failure class, not a negative answer.
- `domain-modeling`: every cross-map decision is one line in `docs/decisions.md`, with a longer note only when Matt's three ADR conditions hold; terms are defined on first use.
- `improve-codebase-architecture`: checks are the test surface, the scope is the shared research code (ticket code is throwaway), code may live on a remote server, and a refactor waits for live runs that import the code.
- `retro`: four research categories (orientation, repeated instructions, judgement slips, vocabulary); each fix names where it lands.
- `wait-what`: also defines each project term on first use.

**Run cards and diagnosis records.** A run that affects a milestone gets a one-page reproduction record (`run-card`); diagnosing evaluation results gets a structured record (`diagnosis-record`).

## Layout

```
skills/      one folder per skill
rules/       style.md (honesty, what always needs the human's OK, code, docs), layout.md (project folders)
scopes/      where projects run: README.md (what a scope answers), one file per cluster
templates/   project scaffold research-init writes: AGENTS.md, CLAUDE.md, STATUS.md, docs/decisions.md (seeds for docs/agents/ live in skills/research-init/)
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
| change where delegated work and reviews go in one project | that project's `docs/agents/delegation.md` |
| add a rule for one project only | that project's `AGENTS.md`, under "Project notes" |
| add a skill | `skills/<name>/SKILL.md`, then `./install.sh` |

Skill descriptions load when a session starts, so a new skill or a changed `description:` needs a new session; a changed body applies the next time it is read.

## Credits

From [mattpocock/skills](https://github.com/mattpocock/skills) (MIT, `licenses/mattpocock-skills-MIT.txt`; synced from commit `5beb35b`): copied `research`, `grilling`, `prototype`, `codebase-design`, `handoff`, `writing-for-agents`, the GitHub and GitLab tracker docs; adapted the domain doc rules (`docs/decisions.md` instead of ADRs); adapted `wayfinder`, `to-tickets`, `to-map` (from `to-spec`), `review` (from `code-review`), `diagnose` (from `diagnosing-bugs`), `domain-modeling`, `retro`, `wait-what`, `improve-codebase-architecture`. Failure classification and the "no viable branch" stop are distilled from [CoAutoResearch](https://github.com/YihongT/CoAutoResearch).
