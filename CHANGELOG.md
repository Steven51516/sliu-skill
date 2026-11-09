# Changelog

Notable changes, newest first. Versions follow semver; a release moves the Unreleased lines under its number and tags
`vX.Y.Z`.

## Unreleased

- **Research Desk:** never floods a remote host with ssh (it took down Engaging's login008): one call at a time per
  host, only over a connection a person opened, a hard deadline that kills the call's hop too, and back-off after a
  failure; the project page says "not connected" or "unreachable". `tools/gui/tests/remote_calls_test.py`, run by
  `scripts/check.py`, fails if it ever floods again.
- **Research Desk:** a host listed in `~/.config/research-gui/remote-paused` gets no call at all (not even the local
  connection check) until it is removed; its projects show "paused" and their last copy.
- **`scripts/check.py`** fails when a file calls a skill that is not in git (removed, renamed or local only), as
  DARE's CI does for its skill graph. It found Research Desk's "Diagnosis card" start option, which called a local-only
  skill; the option is gone (type `/diagnosis-card` where that skill is installed).
- **Dropped the old `tracks/` layout:** `research-status`, `team-up` and Research Desk read only `maps/*/map.md`; the
  app's default server map folder is `maps`.
- **Removed the `away` skill.** A driver already keeps its map moving inside the Contract whether or not the human
  is there; `/ketchup` catches them up.
- **Skill groups:** `run-card` moved to `core/`; `team` has its own `team/`; `optional/` is gone. Local-only skills
  (`ask-via-feishu`, `diagnosis-card`, `to-diagnosis-map`) live in `skills/local/`, gitignored as a whole.
- **Local only (gitignored):** `ask-via-feishu` and its `ask-feishu` tool (now `tools/local/`, which `install.sh` puts on
  PATH), and `scopes/` (a scope file describes your own machines; `SCOPE-FORMAT.md` says what it answers).
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
  run cards.
- **Research Desk**, a macOS app over the same files and herdr.
- **Repository:** MIT license, `CONTRIBUTING.md`, `AGENTS.md`, `GLOSSARY.md`, `scripts/check.py` run in CI.
