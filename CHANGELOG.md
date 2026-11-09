# Changelog

Notable changes, newest first. Versions follow semver; a release moves the Unreleased lines under its number and tags
`vX.Y.Z`.

## Unreleased

- **team-watch** also watches worker tabs: a worker stopped by Claude's safeguards is resumed once on Sonnet 5.5
  (`team-worker --rescue`) instead of waiting for the driver's next pass; stopped again, its driver gets one line.
- **team-watch** holds an OS file lock, so a second watch on the same project cannot start and a dead one leaves no
  stale lock (two protbench watches once ran at the same time).
- **rigor** rule 1: the reference is ground truth or named a proxy when a model made it; a score is never normalised
  by the evaluated model's own outputs (from ARIS's experiment audit).
- **Research Desk:** pasting an image (⌘V of a screenshot or a copied image) saves it and types its path, which the
  agent reads; a file copied in Finder pastes its path. For a session on a remote host the file is uploaded there first.
- **Research Desk:** each session's tag shows its reasoning effort beside the model ("Opus 5.5 · xhigh"), read from
  its requests or the last `/effort`.
- **Research Desk:** when Claude Code compacts a session, its summary shows folded under a "context compacted" note
  (with the tokens before and after), not as a message from the human.

## 0.1.0 (2026-11-03)

First public release.

- **Research loop:** maps under a Contract; question tickets with blocking edges and pre-registration; `research-drive`
  passes with a fresh implementer per ticket; `rigor`; `review` by one fresh reviewer on three axes; `research-status`
  (`STATUS.md`, `--now`, `--frontier`, `--check`).
- **Team mode in herdr:** a desk, a driver per map and a worker tab per ticket (`team-up`, `team-worker`, `team-watch`,
  `team-roster-hook`); a team is all Claude Code or all Codex.
- **Codex:** skills linked into `~/.agents/skills`; `codex-run` for delegating from Claude Code; `codex-team.args`.
- **Helpers:** `away`, `ketchup`, `retro`, `wait-what`, `writing-for-agents`; `ask-human` (phone buttons through Moshi);
  `ask-feishu` with the `ask-via-feishu` skill; run cards.
- **Research Desk**, a macOS app over the same files and herdr.
- **Repository:** MIT license, `CONTRIBUTING.md`, `AGENTS.md`, `GLOSSARY.md`, `scripts/check.py` run in CI.
