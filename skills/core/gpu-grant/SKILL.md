---
name: gpu-grant
description: "The user grants GPUs to this project: use every one of them, all the time, until the grant ends. Use when the user says the GPUs (or named nodes) are yours, or a brief or AGENTS.md says a GPU grant is active."
argument-hint: "<which GPUs or nodes> [until when]"
---

The user has granted GPUs to this project. While the grant lasts nobody else uses them, so **a granted GPU that is not
running is wasted time**. Your job is to keep all of them busy with work that moves the map, and to stop work quickly
once it is known to be useless.

## When the user grants (you were given `/gpu-grant ...`)

1. Write the grant where every agent of the project reads it: a dated line under the Machines note of the project's
   `AGENTS.md`, in the user's words: which GPUs, until when, and "GPU grant active: follow the `gpu-grant` skill".
2. Tell every live driver and worker in one line, and put that same line in every brief and dispatch from now on:
   subagents, workers and the sessions they start. A descendant that reads it loads this skill.
3. When the user ends or changes the grant, rewrite that line the same day.

## While a grant is active (every agent)

- **Fill first, then order.** Before waiting on anything, list the granted GPUs and what runs on each. For every idle
  one, start the most useful thing that is ready: the next frontier ticket, the repeats that confirm a one-run answer,
  an evaluation, an encode or data build for the next run. Nothing ready is a finding: say so and prepare the next
  input now.
- **Launch the real run beside its smoke test.** Do not wait for the smoke test: start both, and kill the real run the
  moment the smoke test or the run's own first-steps check fails. The same goes for a run that depends on a check or a
  review still in progress: launch it, label it speculative in the ticket's Assets, and kill it if the premise fails.
- **Kill fast.** A run that fails its first-steps check, diverges, or lost its reason is stopped at once, by PID, and
  its GPUs go to the next job in the same step. A dead run holding a GPU is the same waste as an empty one.
- **Pack and scale.** Several small jobs share a GPU when memory allows; a big run takes more GPUs when it scales.
  Evaluations and encodes never hold GPUs a queued training run is waiting for.
- **Prepare the next run during this one.** Data, configs and launch commands for what comes next are built and checked
  while the current run trains, so the hand-over takes minutes.
- **Look again.** After every launch and every finish, and at each driver pass, read the GPUs' owners and use. A
  granted GPU idle for 15 minutes with nothing queued is reported in one line, with what you started on it.

## What the grant does not change

- **Honest results.** Success and stop criteria are still written before a result is read; a speculative run changes
  when a job starts, never how its answer is judged. Every run, killed ones included, is a row in its ticket's Assets.
- **Other people's processes.** The grant is the user's word about these GPUs. A process there that you did not
  start is still never touched: report it and use the rest.
- **The other always-ask items** in `STYLE.md`: deleting data, changing a destination or Contract, anything outside
  the granted machines. GPU-hours on the granted GPUs, for work inside the map's Contract, need no further ask while the
  grant lasts.
