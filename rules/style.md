# Personal research style

<!-- Starter defaults. Edit freely: this is the file that makes the agent work the way you do. -->

## Scientific honesty (non-negotiable)
- Report what you **ran and saw**, with a pointer to the file or log. Label anything else clearly as an expectation.
- Compare like with like: same data, eval set, scorer, decoding and budget. Name anything else that differs and label the
  comparison. A number from another eval set is not a baseline until re-scored on ours.
- Negative and null results get recorded with the same care as wins. They are how the search prunes.
- A result that looks too good is a bug until ruled out. Check for leakage, eval on train data, wrong baseline config, and seed luck.
- Baselines get the same tuning budget as our method. Report mean ± std over seeds (≥3 for any claim).
- Choose stop or success criteria **before** looking at a result, and keep them.
- Pick settings on validation data. The test set is for final numbers only. Splits and metrics stay fixed once results are in;
  any analysis chosen after seeing results is labeled post-hoc.

## Always ask first
- A single ticket over ~5 GPU-hours, a batch over ~40 GPU-hours, or one submission or sweep over **50 GPU-hours** (edit
  these), plus any limit the project's scope file adds.
- Changing a stop criterion after the fact, or a map's destination or Notes (split, metrics, baselines) once results exist.
- Deleting or overwriting anything outside `scratch/` (consolidating tickets is not deleting).
- Pushing to a remote, posting anything externally, or emailing.


## Communication
- Lead with the result or the decision you need, then the evidence, then the details.
- Use numbers over adjectives: "+2.1 ± 0.4 acc over baseline (3 seeds)", not "clearly better".
- Keep it short. Link files instead of pasting their contents.

## Code
- Python. Config files plus one entrypoint per experiment. Keep command-line flags few.
- Readable over clever. Abstract only after the third use.
- Ticket code is throwaway: no tests, no polish. Code in `common/` that several tickets use is clean enough that a labmate could rerun it.

## Git
- Small commits with messages that say what changed and why. Commit before launching a run that will back a result,
  so the run can record its commit hash.
- Never commit data, checkpoints, or large logs. Small result files (csv/json) that feed figures do get committed.

## Docs upkeep
- `STATUS.md` is generated: after changing a map or ticket, run `research-status`. Never hand-edit it.
- `OVERVIEW.md` (the project's map: destination, one line per phase or map, now, ≤25 lines) and each `map.md` (≤80 lines) are **rewritten** to stay current,
  not appended to. A fact lives in one place (usually a ticket); everything above it is a one-line gist and a link.
- When a finding changes, update its tag in the map; when a ticket's approach dies, its answer says so and its line in the
  map's Decisions so far shows it. Consolidate closed tickets rather than letting indexes grow.
- Decisions: map-level as a line in the map's `## Decisions so far`; cross-map in `docs/decisions.md` (one line each: date,
  decision, why; newest first).
- Refer to tickets by name (their question) in anything a human reads; ids ride inside links.

## Figures
- Every figure comes from a script reading committed result files. Never edit a figure by hand.
- Vector output (pdf). Consistent colors and method names across all figures. Colorblind-safe palette.
