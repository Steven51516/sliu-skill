---
name: research-ticket
description: Create one or more tickets (one sharp question each) on a research map, with blocking edges and, for an experiment, a pre-registration; or break a map's fog into tickets. Use when the user proposes a test or an idea inside an existing map, or says "make this a ticket".
argument-hint: "<map id> \"<question>\"  |  <map id> --breakdown"
---

A **ticket** is one question on a map, stated sharply, whose answer changes what we do next: verifiable on its own, sized to one fresh agent session, declaring the tickets that **block** it. Draft from the conversation; don't interview.

The issue tracker should have been provided to you. If not, tell the user to run `/research-init`.

**Not a ticket: the work done to answer one.** Runs, arms, smoke tests, preflights, re-runs, decode or sampling variants, probes, scripts and plots are **assets** of the ticket whose question they serve, rows in its `## Assets` table. A new run never gets a new ticket; a new _question_ does.

## Process

1. **Orient.** Read the map (destination, Notes, Decisions so far, fog) and the tickets the new one may depend on. Stop and say which applies if the idea is:
   - already answered (a line in Decisions so far) or already an open ticket;
   - **an asset of an existing ticket**: a run, arm, smoke test, re-run or variant serving a question that already has a ticket. Add it to that ticket's Assets instead;
   - **fog**: it can't yet be stated as a precise question. Add it to the map's Not yet specified instead;
   - beyond the destination: out of scope, or the start of a different map.
2. **Draft** each ticket and publish it to the issue tracker: the title is the question in plain words; a type (`experiment`, `research`, `prototype`, `grilling`, `task`); blocking edges (only tickets whose **result or code** this one needs); for an experiment, a cost cap and the body below, its pre-registration proposed from the map's Notes.
   - `--breakdown`: draft the set as a numbered list first (question · type · blocked by · what it decides). Only questions that are sharp now become tickets; the rest goes to Not yet specified. Iterate with the user on granularity and edges, then publish the approved ones. Prefer the cheapest decisive question first.
3. **Gate.** An experiment's criteria are fixed before anything runs: this is the one gate it passes. With the user in the session, show the pre-registration and ask them to approve or edit it. When a session drives the map (`research-drive`), it approves the ticket if it fits the map's Notes (a dated line); anything on the always-ask list in the style rules still goes to the user.
4. If it graduates fog, remove that patch from the map's Not yet specified, and update the tracker as its doc says.
5. Say who will pick it up: the map's driver (`/research-drive <map>`), or a window (`/research-work <ticket>`). A `grilling` or `prototype` ticket is worked with the user.

## Experiment ticket body

```markdown
## Question

<one sentence: what would change what we do next>

## Pre-registration

Written and dated before any run; never edited afterwards (amendments are appended, dated, with the reason).
- Reference recipe and deviations: what this follows (from the map's Notes) and each deviation, with why
- Arms / comparison: the reference run and every difference from it, on the map's benchmark (`rigor`); controls only if the benchmark or pipeline is new
- Primary metric and test:
- Success:
- Stop: the result that retires the idea
- Deviations allowed without asking (e.g. execution fixes before any result):

## Assets

| name | what it is | where | result |
|---|---|---|---|

## Answer

<one line with numbers against the pre-registration, then the `rigor` check's PASS/FAIL lines. Every number traceable to its source file, e.g. `0.2699 (rollout TM, eval_ctrl52 N=52, single draw; gate/g7final-2000/ar.dec.score.json)`>

## Log

<setup, exact commands, job ids, results tables, surprises, amendments; leaving mid-ticket, a dated **Where I stopped**>
```

Other ticket types need only `## Question`, then `## Answer` and `## Log` as they resolve.
