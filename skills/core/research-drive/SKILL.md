---
name: research-drive
description: "Work a research map's tickets in parallel: dispatch the frontier, merge answers into the map, and file the next tickets as the fog clears. One pass per call."
argument-hint: "<map>"
---

You drive one map. Its tickets are a **task graph**: there is always a **frontier** ready to start, and each
answer clears fog for the next questions. The goal is its destination reached, or a measured answer that it can't be.
The issue tracker should have been provided to you; if not, tell the user to run `/research-init`.

One call is one **pass**; `/loop /research-drive <map>` repeats it. Keep your own context small: each ticket goes to a
fresh **implementer subagent** (as `docs/agents/delegation.md` says, in the background, at most 6 at once), you talk to
them through pointers (map, ticket, result files), and you trust the files over their reports. A small task with no run
and no number for the map (a check, a count, a trivial edit) you may do yourself and log in one line; anything bigger, or
anything that changes a number, a claim, the Contract or a job, is a ticket.

Each pass:

1. **State:** read the map and its tickets. On the first pass claim the map; if another live session holds it, stop and
   say so. A paused map gets only steps 2 and 6; a closed one ends the loop.
2. **Jobs:** check each running job the way the scope file says (alive, its progress file moving, finished) and the GPUs
   in use; idle granted GPUs are a finding. A finished job nobody is working goes back to an implementer.
3. **Merge:** a ticket reported done is resolved once its review passed (or `review` says it needs none, or can finish
   later); advance the map as wayfinder's "Work through the map" says. A FAIL goes back to an implementer; a FAIL on a
   resolved task reopens it and stops the runs that use it (your subagents' runs are yours; others need the user's yes).
4. **Dispatch:** each frontier ticket inside the Contract and not on hold goes to a fresh implementer subagent, an
   experiment once you approve its pre-registration (a dated line). `grilling` and `prototype` tickets go to the user.
   One GPU-heavy ticket at a time unless the scope file allows more; a no-GPU ticket never waits behind one.
5. **Next:** frontier empty and destination not reached: draft the next tickets from the fog and the latest answers
   (`to-tickets`). When two tickets sharing one premise failed the same check, the next ticket tests that premise. Nothing
   credible left: recommend closing or re-scoping. What needs the user (a decision, an always-ask cost, a failure, evidence
   that the destination or Contract should change) becomes a `grilling` ticket and one line to them. Past ~10 closed
   tickets, consolidate as `wayfinder --rechart` says.
6. **Log:** one line in `scratch/agents/driver.log` (time, what changed), and end the pass with that line. Under `/loop`,
   wake when the next thing is expected (a job's estimated finish or milestone), at most an hour away.
   The destination reached, or measured unreachable: close the map as the tracker doc says and end the loop; also end it
   when the user says stop.
