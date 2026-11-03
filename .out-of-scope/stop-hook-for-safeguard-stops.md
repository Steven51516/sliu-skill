# A Stop hook that continues a session after a safeguard stop

No hook tries to continue a Claude Code session whose reply was stopped by Claude's safeguards.

## Why this is out of scope

Stop hooks do not fire on a turn that a refusal ended, and an earlier version acted on a transcript that had not caught
up yet, causing an extra refused turn. The working remedies sit outside the session: `team-watch` resumes a stuck driver
in its own session on another model, `team-worker --rescue` does the same for a worker, Claude Code's
`switchModelsOnFlag` setting switches model on a flag, and projects keep biology prose out of messages between sessions.

## Prior discussion

- 2026-10: the hook was built, then removed.
