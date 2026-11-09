---
name: away
description: "The user is stepping away (sleep, a meeting, a trip) until their next message: keep the maps moving and park what needs them, prepared. Use when the user says they are going away, going to sleep, or leaving it running."
---

The user is away until their next message, whatever it says.

**When they go:** check that the machine stays awake and, in a team, that `team-watch` runs. Write one line to
`scratch/agents/away.md`, `<UTC time> (human: "<their words>")`, and nothing else; in a team, send each driver `away`.
Reply in one line: what keeps running, what will wait.

**While away**, drive each map as usual (`research-drive` under `/loop`), with three changes:
- A decision only they can make waits as a `grilling` ticket with your pick. Only the work that depends on it waits;
  where it is cheap, prepare both answers.
- After 2 hours, go ahead on your pick if the decision can be undone, sits inside the Contract and is off the always-ask
  list in `STYLE.md`. Record it in the ticket: `(driver, <UTC time>: took the recommended answer, the human away)`.
- Log each decision you take without them as an `away:` line in `scratch/agents/driver.log`.

**When they write again:** delete `scratch/agents/away.md`; in a team, send each driver `back`. Answer their message as
usual, with one line naming any decision you went ahead on. No brief unless they ask (`/ketchup`).
