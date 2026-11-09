# Changelog

Notable changes, newest first. Versions follow semver; a release moves the Unreleased lines under its number and tags
`vX.Y.Z`.

## Unreleased

- **Skill groups:** `run-card` moved to `core/`; `team` has its own `team/`; `optional/` is gone. Local-only skills
  (`ask-via-feishu`, `diagnosis-card`, `to-diagnosis-map`) live in `skills/local/`, gitignored as a whole.
- **away** is shorter: only what differs from a normal driver pass; the away file is one line.
- **ask-via-feishu** is local only (gitignored), like `diagnosis-card`.
- **away** lasts until the user's next message, whatever it says; no "back" and no brief on return (`/ketchup` gives
  one when asked). While away, a decision that has waited 2 hours, sits inside the Contract, is off the always-ask
  list and can be undone is taken on the driver's recommended answer; the next reply names it.
- **Removed the `research` skill.** A research ticket's subagent reads primary sources and cites each claim
  (`wayfinder`); the skill asked a subagent to start a background agent and write a file, which Claude Code refuses.
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
  `ask-feishu`; run cards.
- **Research Desk**, a macOS app over the same files and herdr.
- **Repository:** MIT license, `CONTRIBUTING.md`, `AGENTS.md`, `GLOSSARY.md`, `scripts/check.py` run in CI.
