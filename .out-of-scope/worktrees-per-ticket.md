# A git worktree per ticket

Tickets do not get their own git worktree or branch, the way coding-agent apps isolate parallel agents.

## Why this is out of scope

Worktrees prevent two agents from editing the same files at once. In this harness that is already ruled out by ownership:
the driver alone writes a map, each implementer writes only its own ticket folder, and ticket code lives in that folder.
A search of real project history (feedback log, memory notes, ticket logs) found no case of two agents editing the same
file. Adding worktrees would add merge steps without fixing an observed failure.

Revisit if two agents ever clash over the same code.

## Prior discussion

- 2026-11-01: weighed against Codex's and Claude Desktop's worktree support; kept out until a clash happens.
