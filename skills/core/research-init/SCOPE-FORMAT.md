# Scopes

A **scope file** holds the facts about where a project runs: the machine or cluster, its scheduler, storage, GPUs and
network. The harness skills and rules never name a scheduler, partition or path; they say "the way the scope file says".
A project's `CLAUDE.md` imports exactly one scope file (`@<path>`), so every session in that project loads it.

A scope file answers these questions (any headings, one short file):

1. **Storage:** the projects root, where artifacts (kept checkpoints, datasets) and scratch (regenerable, I/O-heavy) live,
   shared datasets and models to check before downloading, and anything never to write.
2. **Where work runs:** what may run interactively and what must be a job (a login node, a shared GPU box, your laptop).
3. **Jobs:** how to run a smoke test and a real run, how sweeps are launched, how a job is recorded in a ticket's `jobs:`
   (a scheduler id, or `pid:<n>@<host>` where there is no scheduler), how to check its state and progress, and how to stop it.
4. **GPUs:** how many, who else uses them, the lock or gate that shares them, and the one command that shows occupancy
   (owner, utilization, foreign processes) per node. Which nodes to use **now** is one dated line the human updates each
   launch round, never a standing ban (a ban outlives its situation and blocks launches).
5. **Network:** internet access, proxy rules, and what needs the human's OK (large downloads).
6. **Limits that need the human's OK** beyond the always-ask list in `STYLE.md` (e.g. a partition's long runs).
7. **New project:** the environment variables for `research-init` (`PROJECTS_ROOT`, `POOL_ROOT`, `SCRATCH_ROOT`,
   `SCOPE_FILE`).

Keep a scope file with the workspace it describes (an organisation's servers in that organisation's folder or repo), or
in the harness's `scopes/` folder, which git ignores; import it by path. Never put one in a public repository.
