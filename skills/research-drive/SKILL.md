---
name: research-drive
description: "Work a research map's tickets in parallel: dispatch the frontier, merge answers into the map, and file the next tickets as the fog clears. One pass per call."
argument-hint: "<map>"
---

You have been provided a map. Its tickets describe the questions on the way to its destination.

The issue tracker should have been provided to you. If not, tell the user to run `/research-init`.

The goal is the map's destination reached, or a measured answer that it can't be, with every ticket resolved the way the issue tracker resolves work.

The tickets are not a list of steps. They are a **task graph** with blocking relationships between them. This means there is always a **frontier** of tickets which are ready to be grabbed. Unlike a spec's tickets, the graph keeps growing: each answer clears fog, and the next questions become sharp.

Communication to and from subagents should be sparse. Communicate primarily through **context pointers**: to the map, tickets, research notes, and result files. Don't duplicate information already available via pointers.

**Implementer subagents** should be run in the background where possible for maximum concurrency, at most 6 at once; spin them up as `docs/agents/delegation.md` says.

Research runs for hours, so this skill works in **passes**: one call is one pass, and `/loop /research-drive <map>` repeats it. You do no ticket work yourself, so any fresh session can take over from the tracker.

## Steps

Each pass:

1. Read the map and its tickets to understand the task graph. On the first pass, claim the map; if another live session holds it, stop and say so.

2. Check each running job the way the scope file says (alive, the progress file its Assets row names still moving, finished), and the GPUs of the nodes in use (owner, utilization, foreign processes on ours, step time against its reference). Idle granted GPUs are a finding. A finished job whose ticket nobody is working goes back to an implementer for its evaluation or close.

3. Once an **implementer subagent** reports `done`, open the ticket and trust it, not the report. If its review passed (or `rigor`'s table says it needs none, or lets it finish later), resolve it and advance the map as the wayfinder skill's "Work through the map" steps 4-5 say. A FAIL goes back to an implementer; on a task already resolved, it reopens the task and stops the runs that use it.

4. Use **implementer subagents** to work each frontier ticket that fits the map's Contract and is not on hold. Approve an experiment's pre-registration first (a dated line: approved by the driver, within the Contract). `grilling` and `prototype` tickets go to the user instead (ask the user). At most one GPU-heavy ticket at a time unless the scope file allows more; a no-GPU ticket never waits behind a GPU one.

5. If the frontier is empty and the destination not reached, draft the next tickets from the fog and the latest answers (call the Skill tool with "to-tickets"), approve those inside the Contract, and kick off more **implementer subagents** on them. If every ticket is dead and nothing credible is left, recommend closing or re-scoping the map.

6. Put what needs the user on the map as a `grilling` ticket, and tell the user in one line with a pointer: a decision, a cost on the always-ask list, a failure, nothing left inside the Contract, or, at once and even while tickets remain, enough evidence that the destination or Contract should change (the benchmark cannot show the effect, a baseline turns out invalid, the destination looks unreachable, results point to a better route). The user decides; re-charting is `/wayfinder <map> --rechart`.

7. Past ~10 closed tickets, consolidate as `wayfinder --rechart` describes. It changes no decision, so do it without asking.

8. Log one line in `scratch/agents/driver.log` (time, what changed). Under `/loop`, wake at the next thing worth seeing (a job's expected finish or milestone), else in 20-30 min, and hourly when everything waits on the user. When the destination is reached, or a measured answer says it can't be, close the map as the tracker doc says and end the loop; also end it when the user says stop.
