---
name: diagnosis-card
description: "Write a diagnosis card: what a model's evaluation results (failed, suspicious or regressed scores) mean, why they fail, and the smallest checks that would tell the explanations apart."
argument-hint: "<task or result to diagnose> [model revision]"
---

# Diagnosis card

The counterpart of a run card for **results**: what a model's evaluation numbers mean, why they fail, and the smallest
checks that would tell the explanations apart. Template: [DIAGNOSIS-CARD.md](DIAGNOSIS-CARD.md). Distilled from the
Scinetics diagnosis SOP v0.12, without its campaign-specific paths and findings.

**Where the record goes:** if the project's scope defines record conventions (shared experiment folders, naming), follow
them; writing to a shared team root needs the human's OK. Otherwise
`<ticket folder>/diagnosis/<UTC time>_<owner>_<topic>.md`, linked from the ticket's Assets.

**Default read-only.** Read data, configs, logs and existing predictions. Never overwrite references, raw results or the
source's working folders. Diagnosis does not authorise training or new predictions; those are proposals (improving a
model in rounds is a map: `to-diagnosis-map`). Where evidence is missing, list the gap and finish the parts that can be checked.

## Principles
- **Verify the measurement first:** a score depends on input, reference, prediction and scorer; check all four before
  judging the model.
- **Validity is not accuracy:** a well-formed answer can be wrong; a format failure alone does not prove missing knowledge.
- **Respect the information boundary:** an answer cannot contain what the input does not determine; check that input,
  reference and task semantics agree.
- **Correlation is not cause:** when data, budget, model and metric changed together, no single cause is established.
- **Keep the full denominator:** invalid, unfinished and label-less samples stay counted; a valid-subset score never stands
  in for the full score. Missing, `null` and undefined are not zero.
- **Independent evidence:** source data, run records and domain tools; model explanations and majority votes are not label
  evidence.
- **Guard against evaluation adaptation:** a public test used for diagnosis is no longer an independent final check; never
  add its answers or near-duplicates to training.
- **Traceable:** every important claim carries the model revision, task, sample ids, protocol and evidence path.

## Steps
1. **Bind versions.** Read the completion/acceptance record and the evaluation config; match the model revision to the
   result folder; record split, prompt, representation, decoding, scorer and denominator; check the baseline's version,
   units and training protocol. A mismatch stops that comparison, not the other read-only checks.
2. **Check the benchmark.** Pull inputs, references, raw outputs and scoring records; check task wording, label meaning,
   units and output shape; look for missing labels, misalignment, duplicates, masking and scorer bugs; verify suspicious
   cases with domain tools. A reference or scorer problem gets a **class-level** fix proposal that applies to every case of
   that class (including ones the model got right), under a new protocol version: re-score cached predictions first; a
   change to inputs or generation needs re-inference, reported as such.
3. **Split the failure modes.** First: not finished, API error, truncation, parse error, reference problem, scientific error.
   Then capability slices (length, complexity, class, endpoint, species, input representation). Per metric type:
   classification adds class balance, confusion matrix, per-class P/R/F1 and MCC; multi-label goes per endpoint; regression
   checks units, error distribution, bias and the train-mean baseline; ranking needs continuous scores; generation reports
   parse, validity, constraint satisfaction, accuracy and coverage separately; structure checks residue correspondence,
   geometry, stereo and which samples were actually scored. Keep scales explicit (0-1 vs percent).
4. **Build a case pack.** Count all errors against the denominator first; sample failures per mode plus successes from the
   same slices, with a fixed seed or stable ids (start with 20 failures and 10 successes; keep all if fewer). Per case: task,
   id, input, reference, raw output, parsed output, metric contribution, failure label, evidence path. Check training
   coverage of the same endpoint; a positive "neighbour" is not label evidence for this sample. Case-pack frequencies are not
   full-set frequencies.
5. **Compete hypotheses.** Two or three per main failure mode, each with: observation, supporting evidence, counter-evidence,
   minimal check, expected change, stop condition. Cheap checks first (re-scoring the cache, a label audit, a truncation
   analysis). A training check is a small continuation proposal. Data changes report coverage, class ratio, token budget and
   duplicate entities, and keep the filtering gain apart from the coverage change. No operator or reliable label: report a
   capability gap instead of inventing a data mix.
6. **Write the card** from the template; say which checks ran and which are only planned.

## Records
Metrics: one JSON object per line with experiment id, model revision, task, metric, slice, split, protocol version, value,
unit, direction, n_expected / n_completed / n_parsed / n_scored, status (valid / undefined / blocked / incomplete), reason,
source path. Cases: stable sample ids with input, reference, raw output, parsed output, failure mode (`none` for successes),
evidence, source path. Never overwrite a finished result: revisions are new files (`result-v2.md`). Unknown is `null`,
never 0 or blank.
