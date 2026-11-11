---
name: run-card
description: "Write or update the one-page reproduction record of a run that affects a milestone (a reference, a result a map relies on, an artifact later work builds on), or when the user says \"document this run\"."
---

# Run card

The ticket holds the question, the pre-registration and the answer. The **run card** holds how one important run was made
and how to make it again: what a reader needs to trust its numbers, compare against it, or resume it, without reading the
ticket's log. Format: [RUN-CARD.md](RUN-CARD.md).

**Which runs get one:** a run that affects a milestone: one other tickets compare against (a baseline or reference), one
whose numbers back a line in a map's Decisions so far, or one that produces something later work builds on (a tokenizer, a
data version, an encoded store, an init checkpoint). Cost does not decide. Everything else is a row in its ticket's Assets
table; a long run's row gets its launch command and config at launch (the process's environment is gone once it ends), so
it can become a card later.

**Where:** `<ticket folder>/runs/<run-name>.md`, one per run, its name stable for life. What is too long for the card (the
full resolved config, a long flag list, a launch script) sits beside it as `runs/<run-name>.*`, linked. The ticket's Assets
row links the card; once it is a reference, the map's Contract links it next to its numbers.

## When to write it
1. **At launch** (or right after), for a run known to matter: fill *As launched* from the running process, not from the
   plan. A run promoted later fills it from its Assets row's launch capture.
2. **At milestones and at the end:** add results and lineage lines, dated, and move `status`.
3. **When it becomes a reference:** set `status: reference`, re-check *Reproduce* against the current entrypoint, and link
   the card from the map's Contract.

## Capture from the source
- The configuration is what the process actually read: its command line and the project's settings in its environment
  (`/proc/<pid>/cmdline`, `/proc/<pid>/environ`), the trainer's config dump, the launch script. Never copy credentials or
  tokens into the card.
- Code: a commit hash, or, where the code is not in git, the path plus a hash of the scripts the run imported.
- Data: the exact version (path, manifest or receipt, rows or tokens actually covered, exclusions, counts).
- Init: checkpoint path plus a hash or receipt. Environment: interpreter path and the versions of the packages that change
  numerics or kernels. Hardware: node, GPU type and count.
- Every entry was read from its source on the card's `checked` date unless it is marked **(reported)**, from a log or a
  person, or **(inferred)**. Write "unavailable" rather than guessing an identifier, count or path.

## Rules
- **Observed, not planned.** The plan lives in the ticket's pre-registration; the card records what ran. A card written
  after the fact says so.
- **Differences, not repeats.** A run that differs from a reference run says `= <reference card> except:` and lists only
  the differences (`rigor` rule 5); only a new kind of run records its full setup.
- **Attempts vs. revisions.** A retry, resume or routine fix under the same protocol is a new lineage line on the same
  card. A change to data, init, budget, objective or anything that breaks comparability is a new run with its own card,
  linked both ways; say which results stay comparable.
- **Comparable by construction.** The line under the title names what a comparison must match (eval set and N, scorer,
  decoder, budget in the project's units with the conversion) and the known run-to-run spread, or "not measured".
- **Reproduce** gives the verbatim launch command and how to resume from a checkpoint, and when it was last re-checked
  against the current code ("never" is an answer).
- **Status** is one word from the format's list; why it moved goes in Lineage.
- **One screen, about 4,000 characters.** A table cell holds values and paths, not a paragraph. A lineage line is time,
  host and pid, how the attempt ended, and its log path; an error is cited by its log line, not pasted.
- Conclusions stay in the ticket's answer and the map. The card states observations and links them.
- Never launch a run only to complete a card.
