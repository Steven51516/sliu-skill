---
name: run-card
description: Write or update a run card, the one-page reproduction record of an important run (data version, code, resolved config, environment, launch command, budget, lineage, milestone results). Use when a run affects a milestone (a reference, a result a map relies on, an artifact later work builds on), or when the user says "document this run". Not for smoke tests, probes or decode variants.
---

# Run card

The ticket holds the question, the pre-registration and the answer. The **run card** holds how one important run was made
and how to make it again: what a reader needs to trust its numbers, compare against it, or resume it, without reading the
ticket's log. Template: [RUN-CARD.md](RUN-CARD.md). Adapted from the user's `experiment-lifecycle` skill.

**Which runs get one:** a run that affects a milestone: one other tickets compare against (a baseline or reference), one
whose numbers back a line in a map's Decisions so far, or one that produces something later work builds on (a tokenizer, a
data version, an encoded store, an init checkpoint). Cost does not decide. Everything else is a row in its ticket's Assets
table; a long run's row gets its launch command and config at launch (the process's environment is gone once it ends), so
it can become a card later.

**Where:** `<ticket folder>/runs/<run-name>.md`, one per run, its name stable for life. The ticket's Assets row links it;
once it is a reference, the map's Contract links it next to its numbers.

## When to write it
1. **At launch** (or right after), for a run known to matter: fill *As launched* from the running process, not from the
   plan. A run promoted later fills it from its Assets row's launch capture.
2. **At milestones and at the end:** add results and lineage entries. Dated, in place.
3. **When it becomes a reference:** set `status: reference`, check *Reproduce* against the current entrypoint, and link the
   card from the map's Contract.

## Capture from the source
- The resolved configuration is what the process actually read: its command line and the config variables in its
  environment (`/proc/<pid>/cmdline`, `/proc/<pid>/environ` filtered to the project's own settings), the trainer's config
  dump, the launch script. Never copy credentials or tokens into the card.
- Code: a commit hash, or, where the code is not in git, the path plus a hash of the scripts the run imported.
- Data: the exact version (path, manifest or receipt, row or token range actually covered, exclusions, counts).
- Init: checkpoint path plus a hash or receipt. Environment: interpreter path and the versions of the packages that change
  numerics or kernels. Hardware: node, GPU type and count.
- Mark every entry **verified** (read from the source just now), **reported** (from a log or a person) or **inferred**.
  Write "unavailable" rather than guessing an identifier, count or path.

## Rules
- **Observed, not planned.** The plan lives in the ticket's pre-registration; the card records what ran. A card written
  after the fact says so.
- **Attempts vs. revisions.** A retry, resume or routine fix under the same protocol is a new lineage entry on the same
  card. A change to data, init, budget, objective or anything that breaks comparability is a new run with its own card,
  linked both ways; say which results stay comparable.
- **Comparable by construction:** record the budget in the project's units (steps, tokens, GPU-hours) with the conversion,
  and what any comparison must match (eval set and N, scorer, decoder). Note the known run-to-run spread when measured.
- **Reproduce** gives the verbatim launch command and how to resume from a checkpoint. If it has not been re-run against
  the current code, say since when.
- Conclusions stay in the ticket's answer and the map. The card states observations and links them.
- Keep it to about one screen. Link logs, dashboards and large tables; never embed them.
- Never launch a run only to complete a card.
