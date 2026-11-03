# One reviewer per axis

A review is done by one reviewer with a fresh context that checks all three axes (Fair, Spec, Code), not by three
parallel sub-agents.

## Why this is out of scope

For a result of ordinary size, sub-agents multiply cost and latency, and a second opinion does not make the review
smarter; Claude Code's own `/code-review` uses a single fresh sub-agent. The per-axis PASS/FAIL lines are kept, so an
answer can still pass one axis and fail another.

## Prior discussion

- 2026-11-02: changed from three parallel sub-agents, after Addy Osmani's "You're probably overprompting Claude".
