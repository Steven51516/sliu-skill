# Domain Docs

How the research skills should consume this project's domain documentation when exploring its maps, code and results.

## Before exploring, read these

- **`GLOSSARY.md`** at the project root
- **`docs/decisions.md`**: read the cross-map decisions that touch the area you're about to work in (one line each, newest first), and the ADRs in `docs/adr/` they link. A map's own decisions are its Decisions so far.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `domain-modeling` skill (reached via `/improve-codebase-architecture` and `grilling`) creates them lazily when terms or decisions actually get resolved.

## File structure

```
/
├── GLOSSARY.md
├── docs/decisions.md
├── docs/adr/
└── maps/
```

## Use the glossary's vocabulary

When your output names a domain concept (in a ticket title, a refactor proposal, a hypothesis, a metric name), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag decision conflicts

If your output contradicts a line in `docs/decisions.md` or a map's Decisions so far, surface it explicitly rather than silently overriding:

> _Contradicts the 2026-10-25 decision (match the codebook recipe's shape), but worth reopening because…_
