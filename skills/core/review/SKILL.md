---
name: review
description: "Review a ticket's answer before it enters the map, on three axes, by one reviewer with a fresh context: Fair (the rigor rules), Spec (the pre-registered question, no overclaim), Code (the code does what the ticket says). Use when a ticket closes or the user wants a result reviewed."
---

Three-axis review of a ticket's answer, by one reviewer with a fresh context window that has not seen the work:

- **Fair**: does the result follow the `rigor` rules that apply? Every headline number re-derived from the result files,
  with its N.
- **Spec**: is the pre-registered rule (for a `task`, its acceptance) applied exactly as written, and does the answer
  claim no more than its numbers show: no wider scope, no cause credited to one of several changes, no single run treated
  as replicated, no deviation left unrecorded? An `experiment` answer without its four labelled lines (Set, Runs,
  Deviations, Does not show; `research-work`), or with one that disagrees with the files, fails here.
- **Code**: does the code that produced the result do what the ticket says, and nothing else that changes the numbers (a
  default, a filter, a seed, an eval path, a data range)?

The reviewer is the session running this skill, which did not do the work: the one that did delegates it, as
`docs/agents/delegation.md` says. A session that has seen the work or discussed its result runs the review in one
sub-agent instead.

## When to review

On the axes that have something new: **Code** when new code produced the answer, **Spec** and **Fair** when it makes a
claim the map will rely on (a comparison, a cause, a measured answer). A rerun or rebuild on reviewed code that makes no
new claim needs none: its checks suffice (`rigor` rule 1). A claim that enters a map, in its Decisions so far or its
outcome, has passed a review, however its ticket closed: resolved, superseded, or closed with its map. A task's review may
finish beside the tickets that use the task; a FAIL reopens it and stops their runs.

## How

Read the ticket (question, pre-registration, Answer, Assets, Log), the result files its answer cites and the code behind
them, plus the `rigor` rules and the map's Contract; a missing file fails at once. Judge each axis that has something
new, never from the doer's view of the result (a sub-agent gets the files, not that view). Find every finding you can in
one pass, one line each, worst first, each with its evidence (a file and line, a re-derived number, a quoted hunk);
ignore style.

Write one PASS/FAIL line per axis under the Answer, with its worst finding and a pointer. Don't merge or rerank them: an
answer can pass one axis and fail another (a fair comparison that claims more than it measured; a faithful answer built on
code that changed something else; correct code scored on another eval set). Any FAIL keeps the ticket open. A FAIL whose
fix changes only wording is fixed by the doer and noted under its line; a fix that changes code or numbers gets a re-check
of only what changed.
