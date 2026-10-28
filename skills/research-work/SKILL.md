---
name: research-work
description: "Work one research ticket based on its question and pre-registration."
argument-hint: "<ticket>"
---

Work the ticket described by the user.

If the user passes a ticket reference, fetch it from the issue tracker and state its title before starting. If the reference is ambiguous, ask. If it names a map rather than a ticket, call the Skill tool with "research-drive" instead (or read [its SKILL.md](../research-drive/SKILL.md) if that skill isn't loaded). The issue tracker should have been provided to you. If not, tell the user to run `/research-init`.

Claim the ticket before any work. An `experiment` runs only once its pre-registration is approved; if it isn't, call the Skill tool with "to-tickets" to put it to the user.

Do the work yourself, or delegate parts of it as you judge; work that matches a rule in `docs/agents/delegation.md` goes where the rule says. Follow the `rigor` skill while you set up, run and write up, and on what comes back from a delegate.

Run jobs the way the scope file says. Smoke-test only code never run before (train, predict and score on a tiny config); anything else launches on its real config, and its first steps are the smoke check. A launch waits only on the inputs it reads, so granted GPUs never sit idle; stop only processes you started, by PID. Record each job in `jobs:`, and each run, arm or variant as a row in the ticket's Assets, with a long run's launch command and config; so is every process that runs beside it (an auto-eval, a watcher). Each running row names the file that shows it progressing, and the ticket's status is `running (since <time>)` while jobs outlive you; a run that will affect a milestone gets a run card (call the Skill tool with "run-card").

An execution fix before any result is yours: append it, dated, under the pre-registration. Criteria never change after results are seen; a design change goes back to the user.

Once done, write the answer against the pre-registration, with numbers. Before calling a failure negative, classify it: execution, measurement, data, method or hypothesis; only the last two are negative, the rest are inconclusive, with the fix. Then have it reviewed, if `rigor`'s table says so: delegate the review (`docs/agents/delegation.md`) to a session that calls the Skill tool with "review". Any FAIL keeps the ticket open.

Resolve the ticket as the tracker doc says, tagging its line in Decisions so far `[tentative]` (a screen) or `[established]` (confirmed, as `rigor` says). If another session drives the map, leave the map to it and end with one line: `done <ticket>: <answer>`, or `running <ticket>: <jobs>` while jobs still run. Leaving before the ticket resolves, write a dated **Where I stopped** at the end of its Log.
