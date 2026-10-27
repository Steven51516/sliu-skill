# Team protocol: desk (A), driver (B), workers (C)

Several agent sessions (Claude Code, Codex, or a mix) on one project, each with one job, so none of them fills its context.
Started with the `team` skill (`/team <role>` in Claude Code), or all at once by typing `team-up <map>`
(e.g. `team-up T8`) in a herdr pane in the project folder.
Every pane is a session of the planner in the project's `docs/agents/team.md` (Claude Code by default); worker panes hand
their ticket's work to that file's worker (Codex by default), and the driver calls its reviewer per check.
The human talks to the desk day to day, and to a map's driver for wayfinder work on that map (charting,
re-charting, choosing the next questions), since the driver owns the map.

| role | started with | does | writes | never |
|---|---|---|---|---|
| **desk** (A) | `/team desk` | the human's partner: reports state, discusses results, diagnoses and the route, turns the human's decisions into instructions for the driver, relays what the driver reports | its roster line | ticket work, maps |
| **driver** (B) | `/team driver <map>` | runs `/research-drive <map>` under `/loop`, with the worker panes as its workers and the desk as the human: approves and sends tickets within the map's Notes, merges reviewed answers into the map, carries out the desk's instructions | `map.md`, new ticket drafts, the Now line of `OVERVIEW.md` for its map, `STATUS.md` (generated), `scratch/agents/driver.log` | ticket work |
| **worker** (C) | `/team worker` | `/research-work <ticket>` on each `work` message; hands the work to the worker in `docs/agents/team.md` (Codex by default) | its ticket folder | `map.md`, other tickets |

## Control
- **A map runs on its own inside its Notes.** The driver approves each ticket's pre-registration within the Notes (a
  dated line), sends approved tickets to idle workers, and records results. Anything on the always-ask list in
  `rules/style.md`, or outside the Notes, goes to the desk first.
- **The human steers** by planning with the driver (wayfinder: destination, route, new questions, what the Notes allow)
  and through the desk: `hold` a ticket, `pause` or `stop` the map.

## Roster
`scratch/agents/roster.md`, one line per session: `<role> | <agent> | <session name> | <herdr pane or -> | <YYYY-MM-DD HH:MM> |
<map or ->`. `<agent>` is `claude` or `codex`. A session learns its own name (Claude Code: the ListAgents tool; Codex: its
session name in `codex agents`) and, inside herdr, its pane (`herdr pane current`); it appends its line on start and finds
the others there. A line whose session no longer exists is stale; the next session of that role replaces it.

## Messages
Sent with SendMessage to a session name. Short, and a **pointer**, never the result itself:
- desk → driver: `hold <ticket>` · `release <ticket>` · `reopen <ticket>: <why>` (the human challenges a result) · `new <question>` (draft a ticket with `research-ticket`) ·
  `rechart: <what to change>` (the `wayfinder --rechart` procedure) · `pause` · `resume` · `stop`
- driver → desk: `map: <what changed>` (after the human worked on the map with the driver) · `propose <ticket>: <why next>` · `needs-you <pointer>: <one line>` · `closed <ticket name>: <answer in
  one line>` · `progress <ticket name>: <one line>` (relayed from a worker) · `stopped: <why>`
- driver → worker: `work <ticket>`
- worker → driver: `ready` · `progress <ticket>: <one-line finding>` (an Assets row got its first result) ·
  `done <ticket>` · `running <ticket>: <jobs>` · `blocked <ticket>: <one line>` · `propose <draft ticket path>: <question>`

**How a message travels**, by the receiver's agent:
- Claude Code → Claude Code: the SendMessage tool, to the session name.
- Codex → Codex: `codex queue --thread <session name> --message "<text>"`.
- across agents, or when the above fails: through the receiver's terminal, `herdr agent prompt <pane> "<text>"` in herdr or
  `tmux send-keys -t <pane> "<text>" Enter` in tmux.

**Files are the truth.** A receiver opens the pointer before acting, so a lost or duplicated message loses nothing. All
sessions of a team run on the same machine.

## Running it
- One tab (or tmux window) per role, every session started in the project folder (`cd <project> && claude`).
- The driver's schedule: in Claude Code, `/loop` (the `team` skill starts it). Codex has no loop command: put a timer in
  another pane that wakes the driver, e.g. `while sleep 1500; do herdr agent prompt <driver pane> "tick"; done`.
- The driver runs on this machine: keep it awake while the driver runs (`caffeinate -dimsu` in a pane on macOS).
- Long GPU jobs run detached on the server per the scope file, never inside any of these sessions.
