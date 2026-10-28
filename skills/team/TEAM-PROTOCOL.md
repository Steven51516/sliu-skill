# Team protocol: desk (A), driver (B), implementers (C)

Several agent sessions (Claude Code, Codex, or a mix) on one project, each with one job, so none of them fills its context.
Started with the `team` skill (`/team <role>` in Claude Code), or all at once by typing `team-up <map>`
(e.g. `team-up T8`) in a herdr pane in the project folder.
The roles run the same skills as a single session, with two swaps (below); delegation inside any role follows the
project's `docs/agents/delegation.md` as usual.
The human talks to the desk day to day, and to a map's driver for wayfinder work on that map (charting,
re-charting, choosing the next questions), since the driver owns the map.

| role | started with | does | writes | never |
|---|---|---|---|---|
| **desk** (A) | `/team desk` | the human's partner: reports state, discusses results, diagnoses and the route, turns the human's decisions into instructions for the driver, relays what the driver reports | its roster line | ticket work, maps |
| **driver** (B) | `/team driver <map>` | runs `/research-drive <map>` under `/loop`, with the implementer panes as its implementer subagents; the human is reached through the desk: approves and sends tickets within the map's Contract, merges reviewed answers into the map, carries out the desk's instructions | `map.md`, new ticket drafts, `STATUS.md` (generated), `scratch/agents/driver.log` | ticket work |
| **implementer** (C) | `/team implementer` | `/research-work <ticket>` on each `work` message, delegating inside it as `docs/agents/delegation.md` says | its ticket folder | `map.md`, other tickets |

## The two swaps
In a team session, two verbs in the skills resolve to the team instead of `docs/agents/delegation.md`'s defaults:
- **"use implementer subagents"** (the driver): send `work <ticket>` to an idle implementer on the roster.
- **"ask the user" / "tell the user"**: the driver sends the desk `needs-you <pointer>: <one line>`; an implementer sends
  its driver `blocked` or `progress`, which the driver relays. The desk puts it to the human.

## Control
- **A map runs on its own inside its Contract.** The driver approves each ticket's pre-registration within the Contract (a
  dated line), sends approved tickets to idle implementers, and records results. Anything on the always-ask list in
  `rules/style.md`, or outside the Contract, goes to the desk first.
- **The human steers** by planning with the driver or the desk (wayfinder, grilling: destination, route, new questions, what
  the Contract allows) and through the desk: `hold` a ticket, `pause` or `stop` the map. Only the human's own words change a
  destination, a Contract or a pre-registered criterion, or waive a blocker; the desk relays them, it never decides.

## Roster
`scratch/agents/roster.md`, one line per session: `<role> | <agent> | <session name> | <herdr pane or -> | <YYYY-MM-DD HH:MM> |
<map or ->`. `<agent>` is `claude` or `codex`. A session learns its own name (Claude Code: the ListAgents tool; Codex: its
session name in `codex agents`) and, inside herdr, its pane (`herdr pane current`); it appends its line on start and finds
the others there. A line whose session no longer exists is stale; the next session of that role replaces it.

## Messages
Communication between sessions should be sparse. Communicate primarily through **context pointers**: to the map, tickets,
research notes, and result files. Don't duplicate information already available via pointers. A message is one line and
a path, sent after the action it reports has happened, never in the same batch:
- desk → driver: `hold <ticket>` · `release <ticket>` · `reopen <ticket>: <why>` (the human challenges a result) · `new <question>` (draft a ticket with `to-tickets`) ·
  `rechart: <what to change>` (the `wayfinder --rechart` procedure) · `pause` · `resume` · `stop`
- driver → desk: `map: <what changed>` (after the human worked on the map with the driver) · `propose <ticket>: <why next>` · `needs-you <pointer>: <one line>` · `closed <ticket name>: <answer in
  one line>` · `progress <ticket name>: <one line>` (relayed from an implementer) · `stopped: <why>`
- driver → implementer: `work <ticket>`
- implementer → driver: `ready` · `progress <ticket>: <one-line finding>` (an Assets row got its first result) ·
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
