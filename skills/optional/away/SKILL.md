---
name: away
description: "The user is stepping away (sleep, a meeting, a trip): keep the maps moving without them, park what needs them with everything prepared, and brief them when they are back. Use when the user says they are going away, going to sleep, or leaving it running."
argument-hint: "[--go] [map]"
---

The user is stepping away. Work keeps going on everything that does not need them; what needs them waits, prepared, for
one brief when they are back.

## Before they go

Unless the user said `--go`, propose the plan for the time away in one short message: per map, the tickets you will work,
the runs you will start, and what you will leave for them. Wait for their yes ("yes" accepts it as proposed). With
`--go`, skip this and carry on with the current maps as they stand.

Then make sure nothing will stall unattended work: a launch the map's Contract does not already allow is approved now or
left out; the machine stays awake; in a team, `team-watch` is running. Record the start as one dated line in each map's
Decisions so far, `(human, <UTC time>: "away")`, and in `scratch/agents/away.md` with the agreed plan (or "current maps").

## While they are away

Work each map with `research-drive` under `/loop`; in a team, send each driver `away` (it reads `scratch/agents/away.md`).

- Never block on reversible work inside the Contract: do it.
- **Push right**: a decision only the user can make (the always-ask list in `STYLE.md`, anything outside the Contract)
  becomes a `grilling` ticket with your recommended answer and what it unblocks. Only what depends on it waits; keep
  everything else moving.
- Prepare both sides of a waiting decision where that is cheap, so the user's answer takes effect at once.
- New questions the results raise become tickets inside the Contract (`to-tickets`), and are worked like the rest.
- Results enter a map as `[tentative]` until reviewed, as always.
- Log each decision you take without the user as one dated `away:` line in `scratch/agents/driver.log`.

## When they are back

When the user says they are back, give one **brief**: decision-ready, read in two minutes.

1. What each map achieved: one line per ticket closed or run finished, with its number and the file that holds it.
2. Decisions you took without them (the `away:` lines), so they can veto any.
3. Their questions, numbered, each with your pick, so "yes" accepts it.
4. What is running now.

Then delete `scratch/agents/away.md`; in a team, send each driver `back`.
