---
name: rigor
description: Check a research result can be trusted before it counts - same established benchmark, numbers taken from files, no leakage, every difference recorded. Use when setting up, comparing or closing an experiment.
---

# Rigor

A result counts when the comparison is fair. Check these four before a number goes into an answer or a map.

1. **Same benchmark.** The runs compared are scored on the same established benchmark: eval set and N, metric, scorer,
   decoding (the map's Contract names it; with `Benchmark: none`, the eval the ticket's pre-registration fixes, the same for every arm).
   A number from another benchmark is not comparable until re-scored on this one.
   When the benchmark itself changes, re-score the reference too.
2. **Numbers from files.** Every number is read from a saved result file, with N checked, and written with its source:
   `0.2699 (rollout TM, eval_ctrl52 N=52, single draw; gate/g7final-2000/ar.dec.score.json)`.
3. **No leakage.** The eval items, or near-duplicates of them, are not in the training data, and no setting was chosen on
   the eval set.
4. **Differences recorded.** A new kind of experiment records its full setup (data, code, config, launch). Otherwise record
   the reference run and every difference from it; a reference other tickets compare against has a `run-card` with its full
   setup. An unrecorded difference makes the comparison unfair.

A gain on a fair comparison is a win when it is larger than the noise between repeat runs (seeds or sampling draws). A
smaller gap needs repeats first.

**Controls only when needed.** A new benchmark or metric, or a new or changed pipeline (any code on the path that produces
the number), needs a positive control (a known answer it must reproduce) and a null (what an information-free input scores).
An established benchmark on unchanged code does not. Add a control when a result looks too good, sits at the floor or
ceiling, or cannot be explained.

**Checked by someone else, once per ticket.** Before an answer goes into the map, a review is delegated as `docs/agents/delegation.md`
says, to a fresh session that did not do the work, briefed with this file, the ticket, its result paths and the code diff that
produced the numbers. It writes one PASS/FAIL line each under the answer, in three parts:
- **Fair:** checks 1-4 and the noise rule.
- **Answers the question:** the pre-registered rule applied as written, and no claim beyond what the numbers show.
- **Code:** the diff does what the ticket says and nothing that changes the numbers otherwise.
