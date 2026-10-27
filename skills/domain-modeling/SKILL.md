---
name: domain-modeling
description: Build and sharpen a project's shared vocabulary in GLOSSARY.md (metrics, quantities, data versions, model arms, gates) and decide when a choice belongs in docs/decisions.md. Use when a term is coined, overloaded or unclear, when writing or editing GLOSSARY.md, or when recording a cross-map decision.
---

# Domain modeling

Glossary format: [GLOSSARY-FORMAT.md](GLOSSARY-FORMAT.md).

The vocabulary is how the human reads every report. A term the agent coins and never defines ("z_relk", "gate 3", "the
store") forces the human to ask; a term used two ways breaks comparisons. This skill is the *active* discipline: challenge
terms, probe them with scenarios, and write them down the moment they settle. Merely reading `GLOSSARY.md` is a habit
every skill has, not this skill.

## During the session
- **Define on first use.** In anything the human reads, a project term gets a short definition the first time it appears.
  A term you coin that will be used again goes into `GLOSSARY.md` the moment you coin it.
- **Challenge against the glossary.** When a term is used in a way that conflicts with `GLOSSARY.md`, say so at once:
  "The glossary defines z_rel on teacher-forced draws; you seem to mean the rollout. Which is it?"
- **Sharpen fuzzy language.** For an overloaded term, propose one canonical name and list the others under _Avoid_
  ("TM" against which reference? "the null" — which of the two?).
- **Probe with concrete scenarios** that force the boundary of a concept: "Does a decode variant of the same checkpoint
  count as a new arm?"
- **Cross-check with the code and the records.** When a stated definition disagrees with what the code computes or a ticket
  reports, surface the contradiction.
- **Update `GLOSSARY.md` inline**, one term at a time, as each one settles. Create the file lazily, at the project root.

`GLOSSARY.md` holds definitions only: what a thing IS (a metric's formula is its definition). No file paths, flags, results
or plans; those live in tickets.

## Decisions
Every cross-map decision gets one line in `docs/decisions.md` (date, decision, why; newest first); a map decision is a dated
line in the map's Decisions so far. Link a longer rationale note from that line only when all three hold:
1. **Hard to reverse:** changing your mind later is costly (a data version, a tokenizer, an evaluation protocol).
2. **Surprising without context:** a future reader would wonder why it was done this way.
3. **A real trade-off:** there were genuine alternatives and one was chosen for specific reasons.

Worth recording: deliberate deviations from the reference recipe, constraints not visible in the code (which nodes,
licences, budgets), scope decisions, and rejected alternatives whose rejection is not obvious.
