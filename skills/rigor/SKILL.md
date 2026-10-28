---
name: rigor
description: Make a research answer trustworthy while you produce it - verify the measurement, compare on the same benchmark, take numbers from files with the full denominator, rule out leakage, record every difference. Use when setting up, running or writing up a ticket's result.
---

# Rigor

An answer counts when it can be trusted. This skill is the reference for producing one: what makes a result trustworthy, and the rules to follow while you work, not after. At close, someone else checks the same rules (call the Skill tool with "review").

## What each ticket needs

| ticket | apply |
|---|---|
| `experiment` (compares runs, or computes numbers from our own data or results) | all of the rules below |
| `task` that builds something later tickets use (a data version, an encoded store, a tokenizer, a launcher) | the measurement, numbers from files |
| `research` (reading only), `grilling`, `prototype`, any other `task` (getting access, setting up an environment) | none |

**Review** (call the Skill tool with "review") runs on the axes that have something new: **Code** when new code produced the answer, **Spec** and **Fair** when it makes a claim the map will rely on (a comparison, a cause, a measured answer). A rerun or rebuild on reviewed code that makes no new claim needs none: its checks suffice (rule 1). A claim that enters a map, in its Decisions so far or its outcome, has passed a review, however its ticket closed: resolved, superseded, or closed with its map. A task's review may finish beside the tickets that use the task; a FAIL reopens it and stops their runs.

## The rules

1. **Verify the measurement first.** A score depends on the input, the reference, the prediction and the scorer. Check all four before judging the model: labels present and aligned with the inputs, units and scale, the scorer on a known case. A new benchmark or metric, or a new or changed pipeline (any code on the path that produces the number), needs a positive control (a known answer it must reproduce) and a null (what an information-free input scores). Code that has already passed does not: on a repeat, check only what varies between repeats and would fail silently. Add a control when a result looks too good, sits at the floor or ceiling, or cannot be explained.
2. **Same benchmark.** The runs compared are scored on the same benchmark: eval set and N, metric, scorer, decoding (the map's Contract names it; with `Benchmark: none`, the eval the ticket's pre-registration fixes, the same for every arm). A number from another benchmark is not comparable until re-scored on this one. When the benchmark itself changes, re-score the reference too.
3. **Numbers from files, with the full denominator.** Every number is read from a saved result file and written with its source: `0.2699 (rollout TM, eval_ctrl52 N=52, single draw; gate/g7final-2000/ar.dec.score.json)`. Failed, invalid and unscored items stay in the count; a score on the valid subset never stands in for the full one. Missing is not zero. Validity (parsed, complete, well-formed) is reported apart from accuracy. Never average different metrics or scales.
4. **No leakage.** The eval items, or near-duplicates of them, are not in the training data, and no setting was chosen on the eval set. A set you choose settings on or iterate against becomes a selection set and stops being independent evidence: final claims use a held-out set.
5. **Differences recorded.** A new kind of experiment records its full setup (data, code, config, launch). Otherwise record the reference run and every difference from it; a reference other tickets compare against has a run card with its full setup. When several things changed together (data, budget, model, metric), the result belongs to all of them: credit one only if it was varied alone.

## Rules of the result

- **Screen, then confirm.** A single run or a fixed cheap budget is a **screen**: its answer is `[tentative]`. A claim the map stands on is **confirmed**: before results, the pre-registration fixes the repeats (seeds or draws; 3 by default), the comparison (paired where possible), the smallest gap that matters, and how the spread is reported. It is `[established]` when the gap clears both that threshold and the spread between repeats.
- **Criteria before results.** The pre-registration's success and stop rules are fixed before anything runs; amendments are dated and come before the numbers they touch.
- **Classify a failure before calling it negative.** Execution, measurement, data, method or hypothesis: only the last two are negative; the rest are inconclusive, with the fix.
