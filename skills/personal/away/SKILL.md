---
name: away
description: "The user is stepping away (sleep, a meeting, a trip): keep the maps moving without them and park what needs them, prepared, until their next message. Use when the user says they are going away, going to sleep, or leaving it running."
---

The user is stepping away until their next message. Work keeps going on everything that does not need them; what needs
them waits, prepared.

## When they go

Don't plan with them: carry on with the current maps as they stand. Make sure nothing will stall unattended work: the
machine stays awake, and in a team `team-watch` is running. Record the start as one dated line in each map's Decisions so
far, `(human, <UTC time>: "away")`, and in `scratch/agents/away.md`. Reply in one line: what keeps running and what will
wait for them.

## While they are away

Work each map with `research-drive` under `/loop`; in a team, send each driver `away` (it reads `scratch/agents/away.md`).

- Never block on reversible work inside the Contract: do it.
- **Push right**: a decision only the user can make (the always-ask list in `STYLE.md`, anything outside the Contract)
  becomes a `grilling` ticket with your recommended answer and what it unblocks. Only what depends on it waits; keep
  everything else moving.
- Prepare both sides of a waiting decision where that is cheap, so the user's answer takes effect at once.
- **Go ahead on your pick** when such a decision has waited 2 hours and can be undone: inside the Contract, not on the
  always-ask list (a Contract change, an over-budget run and deleted data are never yours to take). Record it in the
  ticket as `(driver, <UTC time>: took the recommended answer, the human away)` and keep it easy to reverse.
- New questions the results raise become tickets inside the Contract (`to-tickets`), and are worked like the rest.
- Results enter a map as `[tentative]` until reviewed, as always.
- Log each decision you take without the user as one dated `away:` line in `scratch/agents/driver.log`.

## When they write again

Their next message, whatever it says, ends away mode: delete `scratch/agents/away.md`; in a team, send each driver
`back`. Then answer the message as usual, adding one line that names any decision you went ahead on, so they can
undo it. No brief unless they ask for one (`/ketchup`).
