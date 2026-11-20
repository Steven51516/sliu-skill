---
name: wayfinder
description: Plan a huge chunk of work (more than one agent session can hold) as a shared map of decision tickets on your issue tracker, and resolve them one at a time until the way to the destination is clear. Also re-charts a map that no longer fits.
disable-model-invocation: true
---

A loose idea has arrived, too big for one agent session, and wrapped in fog: the way from here to the **destination** isn't visible yet. Wayfinding is about finding that way, not charging at the destination. This skill charts the way as a **shared map** on the repo's issue tracker, then works its **decision tickets** (questions whose resolution is a decision, not slices of a build to execute) one at a time until the route is clear.

The destination varies per effort, and naming it is the first act of charting: it shapes every ticket. It might be a spec to hand off and iterate on, a decision to lock before planning starts, or a change made in place like a data-structure migration. The map is domain-agnostic: engineering work, course content, whatever fits the shape.

## Plan, don't do

Wayfinder is **planning** by default: each ticket resolves a decision, and the map is done when the way is clear, with nothing left to decide before someone goes and does the thing. The pull to just do the work is usually the signal you've reached the edge of the map and it's time to hand off. An effort can override this in its **Notes**, carrying execution into the map itself, but absent that, produce decisions, not deliverables. A research map always overrides it, through its **Contract**: `experiment` tickets resolve by measurement (see [Ticket Types](MAP-FORMAT.md#ticket-types)).

## Refer by name

Every map and ticket is an issue, so it has a **name**: its title. In everything the human reads (narration, the map's Decisions-so-far), refer to it by that name, never by a bare id, number, or slug. A wall of `#42, #43, #44` is illegible; names read at a glance. The id and URL don't vanish; a name wraps its link, but they ride _inside_ the name, never stand in for it.

## The map

A map is one issue that indexes its decision tickets. What it and its tickets hold (the map body, the ticket body, ticket types, fog, out of scope) is in [MAP-FORMAT.md](MAP-FORMAT.md): read it before writing either.

## Invocation

Three modes. In each, **never resolve more than one ticket per session**, with the exception of research tickets.

### Chart the map

User invokes with a loose idea.

1. **Name the destination.** Call the Skill tool with "grilling" (terms into `GLOSSARY.md` as they settle) to pin down what this map is finding its way to: the spec, decision, or change. The destination fixes the scope, so it's settled first.
2. **Map the frontier.** Grill again, **breadth-first** this time: fan out across the whole space rather than deep on any one thread, surfacing the open decisions and the first steps takeable now. **If this surfaces no fog** (the way to the destination is already clear, the whole journey small enough for one session), you don't need a map. Stop and ask the user how they'd like to proceed.
3. **Create the map** (label `wayfinder:map`): Destination, Notes and Contract filled in, Decisions-so-far empty, the fog sketched into **Not yet specified**.
4. **Create the tickets you can specify now** as child issues of the map, then wire blocking edges in a **second pass** (issues need ids before they can reference each other). Write cross-references in that pass too, with real ids: a placeholder `#<n>` auto-links to an unrelated issue. Wiring sorts them into the frontier and the blocked; everything you can't yet specify stays in the fog: the **Not yet specified** section.
5. **Fire the research subagents.** For each `research` ticket you just created, spin up a subagent with a fresh context window to resolve it in parallel from primary sources, capturing its findings where the project keeps such notes (else in the ticket's folder), with a context pointer from the ticket.
6. Stop: charting is one session's work; it hand-resolves nothing.

### Work through the map

User invokes with a map (URL or number). A ticket is **optional**: without one, you pick the next decision, not the user.

1. Load the **map**: the low-res view, not every ticket body.
2. Choose the ticket. If the user named one, use it. Otherwise take the first frontier ticket in order. **Claim it**: assign it to yourself before any work.
3. Resolve it as the type its `wayfinder:<type>` label names (see [Ticket Types](MAP-FORMAT.md#ticket-types)). Read the label, not just the body: the body never states the type. **Zoom as needed**: fetch the full body of any related or closed ticket on demand; call the Skill tool for whichever skills the `## Notes` block names. If in doubt, call the Skill tool with "grilling".
4. Record the resolution: post the answer as a **resolution comment**, **close** the issue, and **append a context pointer** to the map's Decisions-so-far.
5. Add newly-surfaced tickets (create-then-wire); graduate any fog the answer has made specifiable, clearing each graduated patch from **Not yet specified** so it lives only as its new ticket. If the answer reveals that a ticket (this one or another) sits beyond the destination, **rule it out of scope** rather than resolving it on the route. If the decision invalidates other parts of the map, update or supersede those tickets.

The user may run unblocked tickets in parallel, so expect other sessions to be editing the tracker concurrently.

### Re-chart the map

User invokes with a map and `--rechart`: evidence suggests the destination or the Contract should change, the map has two destinations, a ticket has swallowed many runs or questions, or the tracker reports resolved tickets missing from the map. Draft the new map, show it, and write it once the user agrees.

1. Read the map and every ticket's question and answer; open a ticket body only to settle what it answered.
2. **A change of destination or Contract:** go through the evidence with the user; they decide. Rewrite what they change and append a dated line to Decisions so far: old → new, with the evidence link. Tickets the change invalidates are superseded, or re-registered on the new terms; if the benchmark changed, re-score the reference runs on it before comparing. Redraw the fog.
3. **One destination per map:** tickets heading to a second destination move to a new map (charted as above).
4. **Rebuild Decisions so far:** one line per answered question, by name. A ticket that answered several questions gets one line per question, each linking it.
5. **Unbundle:** runs, arms and variants become assets of their ticket; questions still open become new tickets if sharp, fog if not; anything past the destination goes to Out of scope.
6. **Consolidate** past ~10 closed tickets: closed tickets that answered the same question merge into one digest ticket (variant → result → why it ended → link), and nothing that backs a claim is dropped. Consolidating alone changes no decision, so it needs no OK.
