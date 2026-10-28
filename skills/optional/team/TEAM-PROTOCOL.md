# Team protocol: desk (A) and driver (B)

Long-lived agent sessions on one project, each with one job, so none of them fills its context: the **desk**, which the
human talks to, and one **driver** per active map. Started with the `team` skill (`/team <role>` in Claude Code), or all
at once by typing `team-up <map>` (e.g. `team-up T8`) in a herdr pane in the project folder.

The driver runs `research-drive` as a single session would: its implementers are its own background subagents
(`docs/agents/delegation.md`), a fresh one per ticket, seen by the driver only; the human reads their work in the
tickets. One verb resolves to the team: when a skill says **"ask the user" / "tell the user"**, the driver sends the desk
`needs-you <pointer>: <one line>` and the desk puts it to the human. Delegation inside any role follows
`docs/agents/delegation.md` as usual.

The human talks to the desk day to day, and to a map's driver for wayfinder work on that map (charting, re-charting,
choosing the next questions), since the driver owns the map.

| role | started with | does | writes | never |
|---|---|---|---|---|
| **desk** (A) | `/team desk` | the human's partner: reports state, discusses results, diagnoses and the route, turns the human's decisions into instructions for a driver, relays what drivers report | its roster line; handoff notes, summaries for the human, typos | ticket work, edits that change the project's course |
| **driver** (B) | `/team driver <map>` | runs `/research-drive <map>` under `/loop`: approves and dispatches tickets within the map's Contract to its implementer subagents, merges reviewed answers into the map, carries out the desk's instructions | `map.md`, new ticket drafts, trivial edits (no ticket needed), `STATUS.md` (generated), `scratch/agents/driver.log` | ticket work |

## Control
- **A map runs on its own inside its Contract.** The driver approves each ticket's pre-registration within the Contract (a
  dated line), dispatches approved tickets, and records results. Anything on the always-ask list in `STYLE.md`, or
  outside the Contract, goes to the desk first.
- **The human steers** by planning with the driver or the desk (wayfinder, grilling: destination, route, new questions, what
  the Contract allows) and through the desk: `hold` a ticket, `pause` or `stop` the map. Only the human's own words change a
  destination, a Contract or a pre-registered criterion, or waive a blocker; the desk relays them, it never decides.
- **Launches and kills** are done by the session working the ticket, on a go recorded in a file (the Contract, an approved
  pre-registration, the human's dated line); no message carries one. If a permission check refuses it, the subagent returns
  `blocked`; the human says yes in the driver's pane, and the driver runs the command recorded in the ticket.
- **A ticket the human wants to watch** runs in a tab of its own: the human opens one with `/research-work <ticket>` (or asks
  the driver to leave that ticket to them). The driver picks up its result from the ticket on its next pass.

## Roster
`scratch/agents/roster.md`, one line per session: `<role> | <agent> | <herdr pane or -> | <session name> | <YYYY-MM-DD HH:MM> |
<map or ->`. `<agent>` is `claude` or `codex`. The pane is the address: a session's name changes when it resumes, so a
session that starts or resumes rewrites its line (a driver also sends the desk `driver up for <map>`), and a send that
fails re-reads the roster. A session learns its own name (Claude Code: the ListAgents tool; Codex: its session name in
`codex agents`) and, inside herdr, its pane (`herdr pane current`).

## Messages
Communication between sessions should be sparse. Communicate primarily through **context pointers**: to the map, tickets,
research notes, and result files. Don't duplicate information already available via pointers. A message is one line and
a path, sent after the action it reports has happened, never in the same batch:
- desk → driver: `hold <ticket>` · `release <ticket>` · `reopen <ticket>: <why>` (the human challenges a result) · `new <question>` (draft a ticket with `to-tickets`) ·
  `rechart: <what to change>` (the `wayfinder --rechart` procedure) · `pause` · `resume` · `stop`
- driver → desk: `driver up for <map>` · `map: <what changed>` (after the human worked on the map with the driver) ·
  `propose <ticket>: <why next>` · `needs-you <pointer>: <one line>` · `closed <ticket name>: <answer in one line>` ·
  `progress <ticket name>: <one line>` (an Assets row got its first result) · `stopped: <why>`

**How a message travels**, by the receiver's agent:
- Claude Code → Claude Code: the SendMessage tool, to the session name.
- Codex → Codex: `codex queue --thread <session name> --message "<text>"`.
- across agents, or when the above fails: through the receiver's terminal, `herdr agent prompt <pane> "<text>"` in herdr or
  `tmux send-keys -t <pane> "<text>" Enter` in tmux.

**Files are the truth.** A receiver opens the pointer before acting, so a lost or duplicated message loses nothing. All
sessions of a team run on the same machine.

## Running it
- One tab (or tmux window) per role, every session started in the project folder (`cd <project> && claude`); a second
  active map gets a second driver tab.
- The driver's schedule: in Claude Code, `/loop` (the `team` skill starts it). Codex has no loop command: put a timer in
  another pane that wakes the driver, e.g. `while sleep 1500; do herdr agent prompt <driver pane> "tick"; done`.
- The driver runs on this machine: keep it awake while the driver runs (`caffeinate -dimsu` in a pane on macOS).
- Long GPU jobs run detached on the server per the scope file, never inside any of these sessions.
