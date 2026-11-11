# Changelog

Notable changes, newest first. Versions follow semver; a release moves the Unreleased lines under its number and tags
`vX.Y.Z`.

## Unreleased

- **Permission profiles** as presets, one at a time: `perms-ask` (each agent's default), `perms-guarded` (Claude's auto
  mode with every shell command allowed; history rewrites, PRs and recursive deletes ask; Codex sandboxed, never asks)
  and `perms-full-auto` (Claude `bypassPermissions`, Codex without approvals or sandbox; what would ask is refused by
  deny rules and `delete-guard`). `research-preset` gained `settings` (dotted keys in `~/.claude/settings.json`),
  `codex_config` (top-level keys of `~/.codex/config.toml`) and `group` (presets that exclude each other).
  `delete-guard` refuses a recursive delete at once, with the `trash` pointer, in a session without prompts
  (`bypassPermissions`, `dontAsk`). `research-init` offers a profile once per machine.
- **`run-card`** rewritten from how its 39 cards were used: 36 were over 4,000 characters (median 7.3 KB), with table
  cells written as paragraphs. A card is about one screen; long configs sit beside it as files; a run that differs from
  a reference lists only the differences; the line under the title says what a comparison must match; entries count as
  read on the card's `checked` date unless marked (reported) or (inferred); `status` is one word, now including `paused`
  and `stopped`. `research-status --check` reports a card with another status word, a missing field, or no link from its
  ticket (5 cards across both projects).
- **Presets:** optional setup comes as named presets (`presets/`), applied, shown (`--dry-run`) and taken out
  (`--remove`) by `research-preset` or `install.sh --preset <name>`: `alerts` (`extras/notify.py` routes each alert by
  kind: a Moshi push and a Mac sound by default), `safe-deletes` (`trash`, the `delete-guard` hook and a rule for Claude
  and Codex), `team-hooks` (the roster hook), `claude-codex` (a project's delegation rows: work in your field that
  Claude's safeguards often stop, and large reviews, go to Codex at xhigh; an option, not in `recommended`) and
  `recommended` (alerts, safe-deletes, team-hooks). `research-init` asks: for delegation, one agent (the default: all Claude in
  Claude Code, all Codex in Codex), the `claude-codex` preset, or your own rules; once per machine, the machine presets not yet applied. With no rule,
  delegated work and reviews go to a fresh session of the same agent.
- **`team-watch`** gives each alert a kind in `RH_EVENT` (`question`, `silent`, `gave-up`), and expands `~` in every word
  of your alert command.
- **Your own setup is kept out of the workflow:** `trash` and `delete-guard` moved to `extras/`, used by no skill (a
  trash link an earlier install made is kept up to date). `STYLE.md`'s delete rule names no tool; the team docs say
  alerts go to your alert command, not to a phone.
- **`team-watch`** reads silence per driver, from that driver's own session, and no longer restarts a silent driver:
  the human gets one alert. All 15 resumes in its history were for "no pass logged for 90 min" on the shared
  `driver.log`, none for a safeguard stop; each moved a waiting driver to Sonnet 5.5, one driver wrote 24 hourly
  heartbeat passes to keep the watch off, and another, silent for 2.5 days, was never noticed behind them. Resume on
  Sonnet 5.5 is now only for a safeguard stop. A driver on a closed map is skipped; a paused one is not reported.
- **`team-watch`** sends what waits on the human to their phone once: each open `grilling` or `prototype` ticket and
  each new `needs-you` line in `driver.log` (kept in `scratch/agents/team-watch.pushed`). A team blocked for 31 h on an
  unreachable server had told only its desk. `research-drive` now files such a blocker as a `grilling` ticket.
- **`research-status --check`** limits a live map to 12,000 characters instead of 80 lines (one map had reached 26.7 KB
  in 63 lines), and takes `--map <id>`; `research-drive` runs it on its own map at the start of every pass (42
  warnings had piled up unread in one project).
- An **`experiment` answer** ends with four labelled lines (Set, Runs, Deviations, Does not show); `review`'s Spec axis
  fails one without them. 176 of 310 Spec verdicts were FAIL, most for an answer claiming more than its numbers show.
- **Questions for the human are plain text** (one line, your pick first). `ask-human` moved to `tools/local/`: in a
  month it carried one real question, and phone mode had been off since 10-31, so that one fell back to plain text too.
- **`trash`** moves a path into a `.trash/` folder beside it (same disk, an instant rename) and logs it; `--restore`
  puts it back, `--empty --older <days>` is the human's. **`delete-guard`**, a Claude Code hook, asks the human before a
  recursive delete (any `rm -r` form, ssh quotes included, `find -delete`, `rsync --delete`, `shutil.rmtree`); unanswered
  for 15 min, it declines in the herdr pane and tells the agent to use `trash`. Agents had stalled at the delete prompt 5
  times (one worker for ~30 min on 11-09).
- **`codex-run`** moves files Codex wrote into the project folder (new, and named in its log) into the run dir, and tells
  Codex where to write (7 stray reports, 10-30..11-03).
- **`team-watch`** counts only resumes that started (a busy pane used up both drivers' resumes on 10-31), retries a
  failed start next cycle, and when it gives up runs your own alert command, if
  `~/.config/research-harness/notify` holds one (message as its last argument).
- **Research Desk:** project pages load again after the old tracks/ layout was dropped (the app still read its
  `_legacy` flag).
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
- **Helpers:** `away`, `ketchup`, `retro`, `wait-what`, `writing-for-agents`; run cards.
- **Research Desk**, a macOS app over the same files and herdr.
- **Repository:** MIT license, `CONTRIBUTING.md`, `AGENTS.md`, `GLOSSARY.md`, `scripts/check.py` run in CI.
