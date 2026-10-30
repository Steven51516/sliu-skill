# Personal research style

<!-- Starter defaults. Edit freely: this is the file that makes the agent work the way you do. -->

## Scientific honesty (non-negotiable)
- Report what you **ran and saw**, with a pointer to the file or log. Label anything else clearly as an expectation.
- A claim that something happened (sent, launched, running, fixed) quotes its evidence: a PID, message id or log line.
  One passed on from another agent names that agent and whether you checked it.
- A time, cost or size estimate that drives a decision comes from a timed sample, with its n and rate, or is labelled a guess.
- Compare like with like: same data, eval set, scorer, decoding and budget. Name anything else that differs and label the
  comparison. A number from another eval set is not a baseline until re-scored on ours.
- Negative and null results get recorded with the same care as wins. They are how the search prunes.
- A result that looks too good is a bug until ruled out. Check for leakage, eval on train data, wrong baseline config, and seed luck.
- Baselines get the same tuning budget as our method. Report the spread over repeats; when a gap counts as a claim is `rigor`'s rule.
- Choose stop or success criteria **before** looking at a result, and keep them.
- Pick settings on validation data. The test set is for final numbers only. Splits and metrics stay fixed once results are in;
  any analysis chosen after seeing results is labeled post-hoc.

## Always ask first
- A single ticket over ~5 GPU-hours, a batch over ~40 GPU-hours, or one submission or sweep over **50 GPU-hours** (edit
  these), plus any limit the project's scope file adds.
- Changing a stop criterion after the fact, or a map's destination or Contract (benchmark, baselines, what may be done without asking) once results exist.
- Deleting or overwriting data, results, checkpoints or code outside `scratch/` (rewriting a map or ticket record is routine;
  consolidating tickets is not deleting); the request names what can no
  longer be resumed or reproduced afterwards.
- Pushing to a repository the human does not own, posting anything externally, or emailing.
- Opening a network listener, relay or remote command channel on a shared machine.
- Stopping a process you did not start. Stop your own by PID, never by a name pattern.


## Communication
- Lead with the result or the decision you need, then the evidence, then the details.
- A question for the human with fixed answers (yes/no, or one of 2-5 options) goes through
  `ask-human "<question>" <your pick> <other options>` and you carry on: in Moshi mode it reaches the human's phone as
  buttons, and the answer arrives later as a message starting `Answer from the human`. When it says to ask in plain
  text (Moshi mode off), do that. Open questions are always plain text.
- Use numbers over adjectives: "+2.1 ± 0.4 acc over baseline (3 seeds)", not "clearly better".
- Keep it short. Link files instead of pasting their contents.

## Code
- Python. Config files plus one entrypoint per experiment. Keep command-line flags few.
- Readable over clever. Abstract only after the third use.
- Ticket code is throwaway: no test suites, no polish, but check what a claim rests on (`rigor`). Code in `common/` that several tickets use is clean enough that a labmate could rerun it.

## Git
- Small commits with messages that say what changed and why. Commit before launching a run that will back a result,
  so the run can record its commit hash.
- Never commit data, checkpoints, or large logs. Small result files (csv/json) that feed figures do get committed.

## Docs upkeep
- `STATUS.md` is generated: after opening, re-charting, pausing or closing a map, run `research-status`. Never hand-edit it.
- Each `map.md` (≤80 lines) is **rewritten** to stay current,
  not appended to. A fact lives in one place (usually a ticket); everything above it is a one-line gist and a link.
- When a finding changes, update its tag in the map; when a ticket's approach dies, its answer says so and its line in the
  map's Decisions so far shows it. Consolidate closed tickets rather than letting indexes grow.
- Decisions: map-level as a line in the map's `## Decisions so far`; cross-map in `docs/decisions.md` (one line each: date,
  decision, why; newest first).
- Refer to tickets by name (their question) in anything a human reads; ids ride inside links.

## Figures
- Every figure comes from a script reading committed result files. Never edit a figure by hand.
- Vector output (pdf). Consistent colors and method names across all figures. Colorblind-safe palette.
