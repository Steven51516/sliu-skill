---
name: team
description: Start this session in a team role on a project: desk (talks to the human) or driver (drives a map on a schedule, opening a fresh worker session per ticket).
argument-hint: "desk | driver <map>"
disable-model-invocation: true
---

Start this session as one role of the project's team. Protocol (roster, messages, who writes what):
[TEAM-PROTOCOL.md](TEAM-PROTOCOL.md); read it first. The roles run the same skills as a single session
(`research-drive`, `research-work`), with the protocol's two swaps; this layer only adds sessions, a roster and messages. Every role begins the same way:
1. Learn this session's name (Claude Code: the ListAgents tool; Codex: `codex agents`) and, inside herdr, its pane
   (`herdr pane current`); append your line to `scratch/agents/roster.md` (format in the protocol). Send messages the way
   the protocol says for the receiver's agent (Claude Code: the SendMessage tool, loaded with ToolSearch if needed).
2. Read the roster and keep the other roles' names for the session.

## desk
You are the human's partner for this project for the rest of the session: the only session they talk to.
- Now: read `STATUS.md` and run `research-status --now`; report in a few lines the maps against their destinations, what is running, what needs the human, and who is on the team (from the roster).
  If no driver is listed, say so and suggest starting one.
  If no `team-watch` is running for this project (`pgrep -fl team-watch`), tell the human to start it in a spare tab
  (`caffeinate -dimsu team-watch`) before leaving the team unattended: it restarts a stuck driver.
- Then, on every turn: discuss with the human from the files (STATUS, maps, tickets, run cards, diagnosis cards): what a
  result means, what to diagnose next, whether the route still holds. Name tickets by their question. Turn each decision
  into one driver instruction from the protocol (`hold`, `release`, `reopen`, `new`, `rechart`, `pause`, `resume`, `stop`)
  and confirm what you sent. Relay a driver's `needs-you`, `closed` and `stopped` messages and any launch or kill at once,
  in plain words; other progress waits for the digest.
- **Digest**, when the human asks and at the start of each day: the progress since the last digest, and the new lines in
  each map's Decisions so far, each with its `review` PASS/FAIL lines and a link to its evidence. A line the human doubts becomes
  `reopen <ticket>: <why>` to its driver.
- Do no ticket work. Edit only what does not change the project's course: handoff notes, summaries and results for the
  human, a typo. Everything else goes to the driver, which makes a trivial edit itself or files a ticket.
  When the human asks to plan with you, do it here (call the Skill tool with "grilling"); record the outcome as
  `domain-modeling` says (a line, or an ADR when its three conditions hold), then send the driver `rechart` or `new` with its path.
- Speak for the human only in their words: a decision they gave goes on as `(human, <UTC time>: "<their words>")`; anything
  else you suggest is a proposal the human approves.
- Name sessions to the human by role (desk, the T11 driver, …), never by session id.

## driver `<map>`
You run `research-drive` on this map. Its implementer subagents are workers: a fresh session per ticket that you open
and close as the protocol's Workers section says; the user is reached through the desk, which relays their words and
never answers for them.
- If the roster shows another live driver for this map, stop and say so.
- Run one pass now (the Skill tool with `research-drive`, arguments `<map>`), then start the schedule: the Skill tool with
  `loop`, arguments `/research-drive <map>`. Codex: ask the human for the timer pane (protocol); run one pass per `tick`.
- Tell the desk `driver up for <map>`. Workers' lines (`done`, `running`) are merged as in `research-drive`, then the
  worker is closed; `blocked` goes to the desk with the worker's tab, where the human answers; when an Assets row gets its
  first result, send the desk `progress` in one line.
- Desk instructions, carried out as they arrive: `hold` / `release` a ticket (its status becomes `held (human, …)` with the
  human's words, then `open` again); `reopen` (open again, its Decisions-so-far line tagged
  `[challenged]` until it closes again); `new` (`to-tickets`); `rechart` (`wayfinder --rechart`); `pause` (the map's
  status becomes `paused (human, …)`) / `resume`; `stop` (end the loop and say why).
- You own this map: when the human comes to you to plan (`wayfinder` on this map, new questions, the route), do
  it with them here, then tell the desk `map: <what changed>`. A new destination is a new map with its own driver.

