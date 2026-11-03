# Changelog

Notable changes, newest first. Versions follow semver; a release moves the Unreleased lines under its number and tags
`vX.Y.Z`.

## Unreleased

## 0.1.0 (2026-11-03)

First public release.

- **Research loop:** maps under a Contract; question tickets with blocking edges and pre-registration; `research-drive`
  passes with a fresh implementer per ticket; `rigor`; `review` by one fresh reviewer on three axes; `research-status`
  (`STATUS.md`, `--now`, `--frontier`, `--check`).
- **Team mode in herdr:** a desk, a driver per map and a worker tab per ticket (`team-up`, `team-worker`, `team-watch`,
  `team-roster-hook`); a team is all Claude Code or all Codex.
- **Codex:** skills linked into `~/.agents/skills`; `codex-run` for delegating from Claude Code; `codex-team.args`.
- **Helpers:** `away`, `ketchup`, `retro`, `wait-what`, `writing-for-agents`; `ask-human` (phone buttons through Moshi);
  `ask-feishu` with the `ask-via-feishu` skill; run cards and diagnosis cards.
- **Research Desk**, a macOS app over the same files and herdr.
- **Repository:** MIT license, `CONTRIBUTING.md`, `AGENTS.md`, `GLOSSARY.md`, `.out-of-scope/`, `scripts/check.py` run in CI.
