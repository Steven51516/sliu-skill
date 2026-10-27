---
name: research-drive
description: Drive one research map's frontier - hand ready tickets to parallel workers, merge their answers into the map, file the next tickets inside the map's Notes, and escalate what needs the human. One pass per call. Use when the user wants a map worked in parallel or overnight.
argument-hint: "<map>"
---

A map's tickets form a **task graph**: each declares the tickets that block it, so there is always a **frontier** of tickets ready to start. Unlike a build plan, the graph keeps growing: each answer clears fog, and the next questions become sharp. Driving keeps the frontier moving: ready tickets go to workers, finished ones are merged into the map, and new ones are filed when the frontier runs dry.

One call is one **pass**. Repeat it with `/loop /research-drive <map>`. You do no ticket work yourself, so your context stays small and any fresh session can take over from the tracker.

The issue tracker should have been provided to you. If not, tell the user to run `/research-init`. Consult the tracker doc's "Wayfinding operations" section for the frontier query, claims and resolution.

**Workers** are background subagents in this session, at most 6 at once, each told: "Call the Skill tool with `research-work` on <ticket> in <project>. End with one line: `done | running | blocked <ticket>: <one line>`." In a team, the `team` skill swaps them for worker panes and the human for the desk.

## Process

On the first pass, claim the map; if another live session holds it, stop and say so. Only the claimant writes the map. Then, every pass, in order:

1. **State from the tracker:** the map, the frontier, and the Assets, jobs and Log of every running ticket.
2. **Jobs and GPUs:** each running job the way the scope file says (alive, step moving, finished), and the GPUs of the nodes in use (owner, utilization, foreign processes on ours, step time against its reference). Idle granted GPUs are a finding. A finished job whose ticket nobody is working goes back to a worker for its evaluation or close.
3. **Merge:** for each `done`, open the ticket and trust it, not the report. If its `rigor` review passed, resolve it and advance the map as the wayfinder skill's "Work through the map" steps 4-5 say. A FAIL goes back to a worker.
4. **Dispatch:** each frontier ticket that fits the map's Notes and is not on hold goes to a free worker, once you approve its pre-registration (a dated line: approved by the driver, within the Notes). HITL tickets (`grilling`, `prototype`) go to the human instead. At most one GPU-heavy ticket at a time unless the scope file allows more; a no-GPU ticket never waits behind a GPU one.
5. **Frontier empty, destination not reached:** draft the next tickets from the fog and the latest answers (call the Skill tool with "research-ticket"), approve those inside the Notes and dispatch them. Patterns across answers become a map line or fog. If every ticket is dead and nothing credible is left, recommend closing or re-scoping the map.
6. **Escalate** to the human as a `grilling` ticket on the map, and tell them in one line with a pointer: a decision, a cost on the always-ask list, a failure, nothing left inside the Notes (`re-chart`), or, at once and even while tickets remain, enough evidence that the destination or Notes should change (the benchmark cannot show the effect, a baseline turns out invalid, the destination looks unreachable, results point to a better route). The human decides; re-charting is `/wayfinder <map> --rechart`.
7. **Keep it small:** past ~10 closed tickets, consolidate as `wayfinder --rechart` describes. It changes no decision, so do it without asking.
8. **Log and next wake:** one line in `scratch/agents/driver.log` (time, what changed). Under `/loop`, wake at the next thing worth seeing (a job's expected finish or milestone), else in 20-30 min, and hourly when everything waits on the human. End the loop when the destination is reached or the human says stop.
