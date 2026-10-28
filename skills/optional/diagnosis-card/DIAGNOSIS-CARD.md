# Diagnosis card template

```markdown
---
diagnosis: 20261026T120000Z_ana_parse-failures     # <UTC time>_<owner>_<topic>; stable for life
model: <revision> (<weights path>)
tasks: [<task ids from the benchmark manifest>]
protocol: <evaluation protocol version, scorer version>
status: draft                                        # draft | complete | superseded
updated: 2026-10-26
---
# <one line: which results, and the question>

## Binding
Model revision ↔ result folder; split; prompt; representation; decoding; scorer; denominator; baseline version, units,
protocol. Mismatches found: <none | which comparison was stopped>.

## Counts
| task | n expected | completed | parsed | scored | primary metric (full set) | valid-subset metric | scale |
|---|---|---|---|---|---|---|---|

## Benchmark problems
yes | no | undetermined. Each: the class it affects, evidence, the proposed class-level fix, re-score or re-inference needed.

## Failure modes (full set)
| mode | count | share of denominator | slices most affected |
|---|---|---|---|
Case pack: <path to cases.jsonl>, <n failures / n successes>, selection method and seed.

## Hypotheses
- **A:** observation · support · counter-evidence · minimal check · expected change · stop condition
- **B:** …

## Conclusion and limits
What the evidence supports, under which conditions; what it does not establish.

## Next step
re-score | more evidence | fix proposal | training proposal: <the one recommended action>

## Done in this round
Checks that ran (commands, outputs, paths) vs checks only planned.
```
