---
name: review
description: "Review a ticket's answer before it enters the map along three axes: Fair (does the result follow the rigor rules?), Spec (does it answer the pre-registered question, and claim no more?) and Code (does the code behind it do what the ticket says?). Runs them in parallel sub-agents and reports them side by side. Use when a ticket closes, or the user wants a result reviewed."
---

Three-axis review of a ticket's answer:

- **Fair**: does the result follow the `rigor` rules that apply to this ticket?
- **Spec**: does the answer apply the ticket's pre-registered rule as written, and claim no more than its numbers show?
- **Code**: does the code that produced the result do what the ticket says, and nothing else that changes the numbers?

The axes run as **parallel sub-agents** so they don't pollute each other's context, then this skill aggregates their findings. Run this skill in a session that did not do the work: the one that did delegates it, as `docs/agents/delegation.md` says.

## Process

### 1. Pin the ticket

Read the ticket: its question, pre-registration, Answer, Assets and Log. Collect the result files the answer cites and the code behind them: a diff against the last commit or snapshot, or the paths the delegate's brief changed (on a server, read them there).

Before going further, confirm the answer exists and every result file it cites resolves. A missing file should fail here, not inside the sub-agents.

### 2. Pick the axes

Read the `rigor` skill and its table: which rules apply to this ticket type, and which axes run. An `experiment` gets all three; a `task` that builds something later tickets use gets Spec and Code; a ticket with no code behind its result skips Code. Read the map's Contract (benchmark, baselines, reference recipe).

### 3. Spawn the sub-agents in parallel

Issue the sub-agent calls together, in the foreground, and aggregate the reports they return. Each brief asks for every finding the sub-agent can see in one pass, one line each, worst first: a review that stops at the first FAIL costs a round per bug.

**Fair sub-agent prompt** should include:

- The `rigor` rules that apply, pasted in full, and the map's Contract.
- The paths of the result files and the ticket's Assets.
- The brief: "For each rule, report PASS or FAIL with its evidence: a file and line, or a number you re-derived from the result files. Re-derive every headline number in the answer, with its N. Under 400 words."

**Spec sub-agent prompt** should include:

- The ticket's question, its pre-registration (with any dated amendments) or, for a `task`, its acceptance, and its Answer.
- The brief: "Report: (a) is the pre-registered rule applied exactly as written (the metric, the comparison, the threshold), or for a task, does the output meet its acceptance, checked on the output itself? (b) any claim beyond what the numbers show: a wider scope, a cause credited to one of several changes, a single run treated as replicated; (c) deviations made but not recorded. Quote the pre-registration for each finding. Under 400 words."

**Code sub-agent prompt** should include:

- The code diff or changed paths, and the ticket's question and one stated difference.
- The brief: "Report: (a) places where the code does not do what the ticket says; (b) anything that changes the numbers beyond the ticket's stated difference: a changed default, a filter, a seed, an eval path, a data range; (c) bugs on the path that produces the numbers. Quote the hunk for each. Under 400 words."

### 4. Aggregate

Write one PASS/FAIL line per axis under the ticket's Answer, each with its worst finding and a pointer. Do **not** merge or rerank findings, because the axes are deliberately separate (see _Why three axes_). Any FAIL keeps the ticket open.

## Why three axes

An answer can pass one axis and fail another:

- A fair comparison whose conclusion claims more than it measured → **Fair pass, Spec fail.**
- A conclusion that follows the pre-registration, built on a run whose code changed something else too → **Spec pass, Code fail.**
- Correct code scored on a different eval set than the baseline → **Code pass, Fair fail.**

Reporting them separately stops one axis from masking another.
