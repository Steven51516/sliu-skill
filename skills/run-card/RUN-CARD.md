# Run card template

```markdown
---
run: g8-p16-corrupt                 # stable name; the run directory's name if it has one
ticket: T7-08                       # the ticket whose question this run serves (link below)
status: running                     # launched | running | finished | evaluated | reference | superseded | failed
budget: 2000 steps = 6.29 B tokens  # in the project's units, with the conversion
updated: 2026-10-26
---
# g8-p16-corrupt — <one line: what this run is>

Serves: [<the ticket's question>](../ticket.md). Written at launch | after the fact (say which).

## As launched  (verified | reported | inferred on each line)
| | |
|---|---|
| Data | version, path, manifest/receipt, rows or tokens covered, exclusions |
| Init | checkpoint path, sha256 or receipt |
| Code | commit, or path + hash of the imported scripts |
| Config | key hyperparameters: lr + schedule, batch (rows, tokens/step), sequence length, steps, precision, optimizer, loss weights, run-specific flags; full resolved config: <path> |
| Environment | interpreter path; versions of packages that change numerics or kernels |
| Hardware | node, GPU type × count, s/step measured |
| Seeds | seeds and data order |
| Outputs | run dir, checkpoints and retention, logs, dashboard (account/project/run id) |

Launch command (verbatim):
    <command>

## Lineage
- 2026-10-26 08:55 UTC  attempt 1 launched (pid … on node-16)
- <date>  resumed from checkpoint-N after <cause>; comparable: yes/no, why

## Results at milestones
| step | tokens | metric(s) | eval set, N | draw/seed | source |
|---|---|---|---|---|---|
Known spread: <run-to-run or draw-to-draw noise, where measured>. Compare only against runs matching: <eval set, scorer, decoder>.

## Reproduce
1. Environment / data prerequisites.
2. Launch: <command>. Resume: <command from checkpoint>.
Last re-checked against the current entrypoint: <date | never>.

## Known issues
- <traps specific to this run: data coverage limits, retention, flags that silently change behaviour>
```
