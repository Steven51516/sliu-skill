# Run card format

```markdown
---
run: arm-b-lr3e-4                   # stable name; the run directory's name if it has one
ticket: M3-04                       # the ticket whose question this run serves
status: running                     # one word (list below)
budget: 2000 steps = 6.29 B tokens  # in the project's units, with the conversion
checked: 2026-10-26                 # when the As launched entries were last read from their sources
updated: 2026-10-26
---
# arm-b-lr3e-4: <one line: what this run is>

Serves: [<the ticket's question>](../ticket.md). Written at launch | after the fact.
Compare only with runs matching: <eval set and N, scorer, decoder, budget units>. Known spread: <value and source | not measured>.

## As launched
= [<reference run>](<its card>) except the rows below.   (a new kind of run: every row, and drop this line)

| | |
|---|---|
| Data | version, path, manifest or receipt, rows or tokens covered, exclusions |
| Init | checkpoint path, sha256 or receipt |
| Code | commit, or path + hash of the imported scripts |
| Config | key settings: lr + schedule, batch (rows, tokens), sequence length, steps, precision, optimizer, loss weights; full: `runs/<run>.args` |
| Environment | interpreter path; versions of packages that change numerics or kernels |
| Hardware | node, GPU type × count, s/step measured |
| Seeds | seeds and data order |
| Outputs | run dir, checkpoints and retention, logs, dashboard (account/project/run id) |

Launch: `<verbatim command, or the script that holds it>`

## Lineage
- 2026-10-26 08:55Z  attempt 1 on <host>, pid <n>: died at step 103, NCCL timeout (`logs/a1.log:812`)
- 2026-10-26 09:40Z  attempt 2 resumed from checkpoint-100 (execution fix; comparable: yes)

## Results at milestones
| step | tokens | metric(s) | eval set, N | seed or draw | source file |
|---|---|---|---|---|---|

## Reproduce
1. Environment and data prerequisites.
2. Launch: `<command>`. Resume: `<command from a checkpoint>`.

Last re-checked against the current entrypoint: <date | never>.

## Known issues
- <traps specific to this run: data coverage limits, retention, flags that silently change behaviour>
```

**Status**, one word: `launched` (started, not yet seen moving) · `running` · `paused` (stopped on purpose, resumable) ·
`stopped` (ended on purpose before its budget) · `failed` · `finished` (budget reached) · `evaluated` · `reference`
(others compare against it) · `superseded` (the card that replaces it is named in Lineage). `research-status --check`
reports any other word, a card missing `run`, `ticket` or `status`, and a card its ticket does not link.
