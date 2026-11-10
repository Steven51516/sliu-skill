# Team protocol: desk (A), driver (B), workers

Long-lived agent sessions on one project, each with one job, so none of them fills its context: the **desk**, which the
human talks to; one **driver** per active map, each in its own tab; and **workers**, a fresh session per ticket that the driver opens and
closes. Started with the `team` skill (`/team <role>` in Claude Code), or by typing `team-up <map>` (e.g. `team-up T8`)
in a herdr pane in the project folder; workers' tabs come and go as tickets start and finish.

The roles run the same skills as a single session, with two swaps:
- **"use implementer subagents"** (the driver): open a worker per ticket (below). A worker runs `research-work` in a
  session of its own, so it can open subagents itself (a subagent cannot), and the human can watch or answer it in its tab.
- **"ask the user" / "tell the user"**: the driver sends the desk `needs-you <pointer>: <one line>` and writes the same
  line once in `driver.log`, from where `team-watch` passes it once to the human's alert command, if one is set; a worker sends the
  driver `ask` and keeps working (`blocked` once nothing is left that doesn't need the answer), and the driver tells the desk. The desk puts it to the human (STYLE.md) and relays
  the answer to the driver.

Delegation inside any role follows `docs/agents/delegation.md` as usual. The human talks to the desk day to day, and to a
map's driver for wayfinder work on that map (charting, re-charting, choosing the next questions), since the driver owns
the map.

| role | started with | does | writes | never |
|---|---|---|---|---|
| **desk** (A) | `/team desk` | the human's partner: reports state, discusses results, diagnoses and the route, turns the human's decisions into instructions for a driver, relays what drivers report | its roster line; handoff notes, summaries for the human, typos | ticket work, edits that change the project's course |
| **driver** (B) | `/team driver <map>` | runs `/research-drive <map>` under `/loop`: approves tickets within the map's Contract, opens a worker per ticket, merges reviewed answers into the map, carries out the desk's instructions | `map.md`, new ticket drafts, trivial edits (no ticket needed), `STATUS.md` (generated), `scratch/agents/driver.log` | ticket work |
| **worker** | opened by the driver | `/research-work <ticket>` in a fresh session, delegating inside it as `docs/agents/delegation.md` says | its ticket folder | `map.md`, other tickets |

## Workers
- **Open** one per ticket, at most as many as `research-drive` allows at once: `team-worker <ticket path>`. It opens
  a tab labelled with the ticket id on the driver's own agent (Claude Code on Opus 5.5 at medium effort, logged in, or Codex), tells it
  to work the ticket and report back to you, and fails loudly if the worker did not start.
- **On `done` or `running`**: the driver checks the ticket as `research-drive` says, then ends the worker
  (`herdr agent prompt <ticket id> "/exit"`, then `herdr tab close <tab>`). First check that no job depends on that
  session: a session's cleanup can stop jobs it launched.
- **On `ask` or `blocked`**: the tab stays open; the driver tells the desk which tab, and the human answers there.
- **On `handback`** (the human asked the worker, in its tab, for something beyond its ticket): the driver takes it as the
  human's request: a trivial edit it does itself, anything else becomes a ticket draft (`to-tickets`).
- **Idle without its line**: read its screen (`herdr agent read <ticket id>`). If Claude's safeguards stopped its reply
  (often a false positive on biology wording), `team-worker --rescue <ticket id>` resumes its own session on Sonnet 5.5
  at high effort, keeping its chat; `team-watch` does this once by itself and tells you when a worker stops again. New
  workers still start on Opus 5.5.

## Control
- **A map runs on its own inside its Contract.** The driver approves each ticket's pre-registration within the Contract (a
  dated line), opens workers for approved tickets, and records results. Anything on the always-ask list in `STYLE.md`,
  or outside the Contract, goes to the desk first.
- **The human steers** by planning with the driver or the desk (wayfinder, grilling: destination, route, new questions, what
  the Contract allows) and through the desk: `hold` a ticket, `pause` or `stop` the map. Only the human's own words change a
  destination, a Contract or a pre-registered criterion, or waive a blocker; the desk relays them, it never decides.
- **Launches and kills** are done by the worker on its ticket, on a go recorded in a file (the Contract, an approved
  pre-registration, the human's dated line); no message carries one. If a permission check refuses it, the worker reports
  `blocked` and the human approves in its tab.

## Roster
`scratch/agents/roster.md`, one line per desk or driver session: `<role> | <agent> | <herdr pane or -> | <session name> |
<YYYY-MM-DD HH:MM> | <map or ->`. `<agent>` is `claude` or `codex`. The pane is the address: a session's name changes when it
resumes, so a session that starts or resumes rewrites its line (a Claude Code session is reminded by the SessionStart hook
`tools/team-roster-hook.py`; a driver also sends the desk `driver up for <map>`), and a
send that fails re-reads the roster. A session learns its own name (Claude Code: the ListAgents tool; Codex: the session
id in `herdr pane current`) and, inside herdr, its pane (`herdr pane current`). Workers are not on the roster: their driver
knows their tabs.

## Messages
Communication between sessions should be sparse. Communicate primarily through **context pointers**: to the map, tickets,
research notes, and result files. Don't duplicate information already available via pointers. A message is one line and
a path, sent after the action it reports has happened, never in the same batch:
- desk → driver: `hold <ticket>` · `release <ticket>` · `reopen <ticket>: <why>` (the human challenges a result) · `new <question>` (draft a ticket with `to-tickets`) ·
  `rechart: <what to change>` (the `wayfinder --rechart` procedure) · `pause` · `resume` · `stop`
- driver → desk: `driver up for <map>` · `map: <what changed>` (after the human worked on the map with the driver) ·
  `propose <ticket>: <why next>` · `needs-you <pointer>: <one line>` · `closed <ticket name>: <answer in one line>` ·
  `progress <ticket name>: <one line>` (an Assets row got its first result) · `stopped: <why>`
- worker → driver: `done <ticket>: <path>` · `running <ticket>: <path>` · `ask <ticket>: <path>` · `blocked <ticket>: <path>`,
  the path of the file that holds the result, jobs or question, never the content itself · `handback <ticket>: <request>`

**How a message travels**, by the receiver's agent:
- Claude Code → Claude Code: the SendMessage tool, to the session name; a worker uses `herdr agent prompt <driver pane>`.
- Codex → Codex: `codex queue --thread <session name> --message "<text>"`.
- across agents, or when the above fails: through the receiver's terminal, `herdr agent prompt <pane> "<text>"` in herdr or
  `tmux send-keys -t <pane> "<text>" Enter` in tmux.

**Files are the truth.** A receiver opens the pointer before acting, so a lost or duplicated message loses nothing. All
sessions of a team run on the same machine.

## Running it
- One tab (or tmux window) for the desk and one per driver, every session started in the project folder
  (`cd <project> && claude`); a second active map gets a second driver tab, opened with
  `team-up --driver <map>` (never a bare `claude`, which takes whatever model and effort are saved as defaults). Worker tabs open and close with their tickets.
- A team is all Claude Code (`team-up <map>`) or all Codex (`team-up --codex <map>`); Research Desk's Start team offers
  both. Workers run on their driver's agent. In a Codex team, a delegation rule that sends work to Codex is the session's
  own work, and one that names a Claude subagent goes to a fresh Codex session (`codex-run`) instead.
- Team sessions run for days and re-read their whole context on every call: set a compaction window in your Claude Code
  settings (`"autoCompactWindow": 400000`) instead of the model's default near the full window.
- The driver's schedule: in Claude Code, `/loop` (the `team` skill starts it). Codex has no loop command: `team-watch`
  types `tick` into an idle Codex driver every 25 minutes.
- The driver runs on this machine: keep it awake while the driver runs (`caffeinate -dimsu` in a pane on macOS).
- Nobody watching (a night): `team-watch` runs in a tab of its own (`team-up` starts it; otherwise run
  `caffeinate -dimsu team-watch` once in the project folder). It watches every driver on the roster and shows the driver's log. A driver stopped by Claude's safeguards is resumed in its own
  session on Sonnet 5.5, keeping its chat, at most 3 times; a worker is rescued once the same way. A driver waiting on
  a permission prompt is left for the human. A driver idle with nothing written by its own session for 90 minutes has
  lost its loop: it is not restarted, the human gets one alert (so a pass written only to look alive is never needed).
  Each open `grilling` or `prototype` ticket and each `needs-you` line in `driver.log` goes once to the human's alert
  command (`~/.config/research-harness/notify`, if set).
- Long GPU jobs run detached on the server per the scope file, never inside any of these sessions.
