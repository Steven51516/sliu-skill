---
name: resume
description: Resume a research project at the start of a session, or when asked "where are we" - report its maps against their destinations, what waits on the human, what is running, and the recommended next step, and route to the right skill. Also explains the research harness.
---

1. If the working directory is not a project (no `CLAUDE.md` with a harness header), list the project folders under the projects root (the scope file's, else `~/projects/`), each with the date in its `STATUS.md`, and ask which one. Point out `/research-init` for starting a new one.
2. Read the project's maps through its issue tracker (`docs/agents/issue-tracker.md`; on the local tracker, read `STATUS.md` for the milestones and open maps, and run `research-status --now` and `--check`), and check the jobs of running tickets the way the scope file says. If the research skills are missing on this machine (no `research-work` skill loaded), say so and point at the harness's `install.sh`. If the project has no tracker doc yet, or still uses the old `tracks/` layout, say so and offer `/research-init` to adopt it.
3. Report briefly, naming tickets by their question: each map's destination and the next ticket on its frontier; what waits on the human (open `grilling` and `prototype` tickets, restated with your recommendation); what is running or claimed, and by whom; **one recommended next step**. Then ask. Don't start a grilling interview unless asked.
4. Route: `research-work` for one ticket; `research-drive` to work a map's frontier in parallel or overnight; recommend that the user run `/to-map` to open a new map from what was discussed, or `/wayfinder "<idea>"` from a loose idea, or `/wayfinder <map> --rechart` when the tracker reports resolved tickets missing from a map or a map has two destinations (wayfinder is user-invoked); `to-tickets` to add tickets; `diagnose` for a bug or a result that looks wrong; `run-card` for an important run.

If the user asks how the harness works or how to change it, read the harness's `README.md` and answer from it.
