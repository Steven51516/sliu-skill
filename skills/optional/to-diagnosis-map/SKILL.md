---
name: to-diagnosis-map
description: "Open a map that improves a model in rounds: diagnose its evaluation results with a diagnosis card, test the top hypotheses as experiment tickets, re-diagnose, repeat. A preset for to-map."
disable-model-invocation: true
argument-hint: "<model> <benchmark or task>"
---

Open a map for improving a model in rounds. Call the Skill tool with "to-map" (or read
[its SKILL.md](../../core/to-map/SKILL.md)) and fill the map as below. Ask the user for anything here the conversation
does not fix; never guess it.

- **Destination**: the target metric on the fixed protocol, or a measured answer that no credible change reaches it.
- **Contract**, fixed before any training:
  - **Benchmark**: the target tasks and metric; the diagnosis, selection and final validation sets, with the scorer
    version. Changes are chosen on the selection set, never on the final validation set.
  - **Reference recipe**: D0 (weights, data version, code commit, config, seed) and its scores on the benchmark.
  - **Without asking**: what may change and what may not; the nodes, the per-round and total budget, the maximum number
    of rounds; what counts as a significant regression, when a round is adopted, and when the map stops (target reached,
    budget or rounds spent, or no gain over the last rounds).
- **Notes**: "After every evaluation, write a diagnosis card (call the Skill tool with `diagnosis-card`); the next round's
  tickets come from its ranked hypotheses."
- **First ticket**: an experiment that diagnoses D0 and writes its diagnosis card.

Each round is then an experiment ticket: its pre-registration is the plan; it continues from the adopted weights, writes
to its own output folder, and is scored against D0 and the previous round; its Answer is the decision (adopt, roll back,
or stop). A significant regression pauses the map until versions, coverage and scoring are verified. Drive the map with
`/loop /research-drive <map>`.
