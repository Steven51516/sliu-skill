---
name: to-map
description: "Turn the current conversation into a map and publish it to the project issue tracker: no interview, just synthesis of what you've already discussed."
disable-model-invocation: true
---

This skill takes the current conversation context and the project's state and produces a map. Do NOT interview the user; just synthesize what you already know.

The issue tracker should have been provided to you. If not, tell the user to run `/research-init`.

## Process

1. Explore the project to understand where it stands (its other maps, and the code and results the new one builds on), if you haven't already. Use the project's domain glossary vocabulary throughout the map, and respect any decisions in `docs/decisions.md` in the area you're touching. If an existing map already heads to this destination, add tickets to it instead (call the Skill tool with "to-tickets") and stop.

2. If this map will measure anything, sketch out the benchmark every ticket on it will be scored on: eval set and N, metric, scorer, decoding, and the baselines on it. If it measures nothing (a data build, a survey, a tool) or what to measure is still open, the benchmark is `none`, with why, and choosing one may be its first question. An existing benchmark should be preferred to a new one. If a new one is needed, say what it measures that the existing ones can't. Every comparison on this map uses the same one.

Check with the user that this benchmark matches their expectations.

3. Write the map using the template below, then publish it to the project issue tracker.

4. Call the Skill tool with "to-tickets" for the questions in the conversation that are already sharp; the rest stays in Not yet specified.

<map-template>

## Destination

What reaching the end of this map looks like, from the user's perspective, with the number or answer that decides it. One or two lines; every session orients to it before choosing a ticket.

## Notes

Domain; skills every session should consult; standing preferences for this effort.

## Contract

- **Benchmark**: the one from step 2 (eval set and N, metric, scorer, decoding), and the baselines to beat with their numbers on it; or `none`, with why. Name data versions and eval sets exactly: every comparison on this map depends on them.
- **Reference recipe**: the paper, repo or run the tickets follow unless a ticket records a deviation.
- **Without asking**: the methods and compute cap the agent may use on its own, and what to ask first.

Only the user changes this section.

## Decisions so far

The decisions the conversation already made, one dated line each. Resolved tickets add theirs below.

## Not yet specified

A LONG list of the questions you can see coming but can't yet state sharply enough to ticket, written as loosely or as fully as the view allows. This list should cover the whole way to the destination.

## Out of scope

A description of the things that are out of scope for this map.

</map-template>
