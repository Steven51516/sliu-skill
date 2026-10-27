---
name: to-tickets
description: Break a map's fog, a plan, or the current conversation into a set of question tickets, each declaring its blocking edges and, for an experiment, a pre-registration, published to the configured tracker.
argument-hint: "<map> [\"<question>\"]"
---

# To Tickets

Break a map's fog, a plan, or a conversation into a set of **tickets**: one sharp question each, each declaring the tickets that **block** it.

The issue tracker should have been provided to you. If not, tell the user to run `/research-init`.

## Process

### 1. Gather context

Work from whatever is already in the conversation context. If the user passes a reference (a map, a ticket id or path) as an argument, fetch it and read its full body: the map's Destination, Notes, Decisions so far and Not yet specified, and the tickets the new ones may depend on. Ticket titles should use the project's domain glossary vocabulary (`GLOSSARY.md`).

### 2. Explore the code and results (optional)

If you have not already explored the code and results the questions touch, do so, to know what is cheap to measure and what has already been measured.

### 3. Draft questions

Break the work into **questions**.

<question-rules>

- Each ticket asks one question whose answer changes what we do next
- Make it a ticket when the question can be stated precisely now, even if it's blocked; otherwise it is fog and stays in the map's Not yet specified. Don't pre-slice the fog
- A run, arm, smoke test, re-run or variant is an **asset** of the ticket whose question it serves, never a ticket of its own
- Each ticket is sized to fit in a single fresh context window
- The cheapest decisive question comes first

</question-rules>

Give each ticket its **blocking edges**: the other tickets whose result or code it needs. A ticket with no blockers can start immediately. Give it a type (`experiment`, `research`, `prototype`, `grilling`, `task`); an `experiment` also gets a cost cap and a **pre-registration** proposed from the map's Notes.

Stop and say which applies if an idea is already answered (a line in Decisions so far) or already an open ticket; an asset of an existing ticket (add it to that ticket's Assets instead); or beyond the destination (out of scope, or the start of a different map).

### 4. Quiz the user

Present the proposed breakdown as a numbered list. For each ticket, show:

- **Title**: the question
- **Type**
- **Blocked by**: which other tickets (if any) must complete first
- **What it decides**: what we do differently depending on the answer

For an `experiment`, show its pre-registration too: its criteria are fixed before anything runs, and this is the one gate it passes.

Ask the user:

- Does the granularity feel right? (too coarse / too fine)
- Are the blocking edges correct: does each ticket only depend on tickets that genuinely gate it?
- Should any tickets be merged or split further?
- Do the success and stop criteria hold?

Iterate until the user approves the breakdown. When a session drives the map (`research-drive`), it approves a ticket that fits the map's Notes itself, with a dated line; anything on the always-ask list in the style rules still goes to the user.

### 5. Publish the tickets to the configured tracker

Publish the approved tickets in dependency order (blockers first), as the tracker doc says, so each ticket's blocking edges can reference real identifiers. Remove each graduated patch from the map's Not yet specified.

Work the **frontier**: any ticket whose blockers are all done. For a purely linear chain that means top to bottom. The map's driver picks tickets up (`/research-drive <map>`), or a window does (`/research-work <ticket>`); a `grilling` or `prototype` ticket is worked with the user.

Do NOT resolve or modify any other ticket.

<ticket-template>

## Question

The question, in one sentence: what would change what we do next.

## Pre-registration

(`experiment` only.) Written and dated before any run; never edited afterwards (amendments are appended, dated, with the reason).

- Reference recipe and deviations: what this follows (from the map's Notes) and each deviation, with why
- Arms / comparison: the reference run and every difference from it, on the map's benchmark (`rigor`); controls only if the benchmark or pipeline is new
- Primary metric and test:
- Success:
- Stop: the result that retires the idea
- Deviations allowed without asking (e.g. execution fixes before any result):

## Assets

(`experiment` only.) One row per run, arm, smoke test, probe or script made while answering the question.

| name | what it is | where | result |
|---|---|---|---|

</ticket-template>

The answer is not part of the ticket when it is published; it is recorded on resolution, under `## Answer`, with the `rigor` check's PASS/FAIL lines. Name data versions, eval sets and baselines as the map's Notes do; avoid code snippets: they go stale fast.
