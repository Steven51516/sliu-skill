---
name: research-work
description: Work one research ticket end to end - run it against its pre-registration, write the answer, get it reviewed, and record it on the map. Use when the user points at a ticket, or a driver hands one over.
argument-hint: "<ticket>"
---

Work **one ticket**: a single question on a map, whose success and stop criteria were fixed before anything ran. A session works one ticket and resolves at most one. Who does the hands-on work and who reviews is in `docs/agents/team.md`.

The issue tracker should have been provided to you. If not, tell the user to run `/research-init`. Consult the tracker doc's "Wayfinding operations" section for how to claim, resolve and record.

Given a map instead of a ticket, call the Skill tool with "research-drive" (if it isn't loaded in this session, read [its SKILL.md](../research-drive/SKILL.md) and follow it).

## Process

1. **Claim and gate.** Read the ticket and its map once, at low resolution. **Claim it** before anything else; a ticket claimed by another live session is read-only. An experiment's pre-registration must be approved, as a dated line, before any run: if it isn't, show it and ask (call the Skill tool with "research-ticket").
2. **Run.** Hand each bounded task to the worker in `team.md`, and check what comes back by calling the Skill tool with "rigor". Jobs run the way the scope file says.
   - Code never run before gets a tiny-config smoke test first: train, predict and score. Anything else launches on its real config, and its first steps are the smoke check (loss finite, step time as expected, one eval pass); stop it if they fail.
   - A launch waits only on the inputs it reads. Other prep and evals run beside it, so granted GPUs never sit idle. Share GPUs by the scope file's rule; stop only processes you started, by PID.
   - Record job ids in `jobs:` and set `status: running`. Every smoke test, run, arm or variant is a row in `## Assets`, never a new ticket; a long run's row gets its launch command and config at launch. A run that will affect a milestone gets a run card (call the Skill tool with "run-card").
   - A `task` follows its checklist; its answer records the facts later tickets need (paths, row counts).
3. **Deviations.** An execution fix before any result is yours: append it, dated, under the pre-registration. Criteria never change after results are seen; a design change goes back to the human.
4. **Answer** against the pre-registration, with numbers, under `## Answer`; for an experiment set `verdict:` (`positive`, `negative`, `null`, `inconclusive`). Before calling a failure `negative`, classify it: execution, measurement, data, method or hypothesis. Only the last two are negative; the rest are `inconclusive`, with the fix. Then the `rigor` review: its PASS/FAIL lines go under the answer, and any FAIL keeps the ticket open.
5. **Record.** If another session drives the map (its `claimed` names one), leave the map to it and end with one line: `done <ticket>: <answer>`. Otherwise resolve the ticket and advance the map as the wayfinder skill's "Work through the map" steps 4-5 say, tagging the Decisions-so-far line `[tentative]` (one seed or draw) or `[established]` (replicated). A run that became a reference gets its run card completed and linked from the map's Notes.
6. **Leaving before it closes.** Write a dated **Where I stopped** at the end of the Log (state, what is running, next action) and release the claim, or say why you hold it. With jobs still running, end with `running <ticket>: <jobs>`.

Anything on the always-ask list in the style rules goes to the human first.
