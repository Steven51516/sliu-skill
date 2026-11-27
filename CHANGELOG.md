# Changelog

Notable changes, newest first. Versions follow semver; a release moves the Unreleased lines under its number and tags
`vX.Y.Z`.

## Unreleased

- **`team-worker --close`** asks a worker that still holds a background command to stop it, once, and says "try
  again later" (exit 3); the next call closes it. Before, it only backed out, and every pass of the driver and of
  `team-watch` typed an exit into the worker again: eight finished workers got 4 to 16 exits each and stayed open for
  days, each holding a poll loop that never ended. A worker that keeps a command after being asked is left, and no
  exit is typed into it again until its state changes. `team-watch` tries again 10 minutes after "later". The
  question says how to find the tasks and that every shell child of the session's process is one of its own (asked
  only "what runs?", a worker checked `jobs` and kept its loop; two long sessions took their own loops for the
  harness's shells), and it is sent once herdr no longer reports the exit dialog (herdr refuses a prompt until then).
  `tools/tests/team_close_test.py` (run by `scripts/check.py`) covers it with a stand-in for herdr.
- **Research Desk**: a big map opens readable. An 83-ticket map opened at 60% (ticket text about 7 px), most of it
  one column of the resolved tickets that link to nothing. The first view now opens at 85% or more, on what is live
  (the open ticket, else one that needs you, is running or is ready), and settled tickets with no link to another are
  laid out as a grid under the graph instead of sharing one rank. Fit still shows everything.
- **Research Desk**: a project's page says where it lives in words ("On this Mac · code on <server>", "On <host>")
  instead of printing its folder paths under the title; the paths are in the tooltip, and More has Copy its path
  beside Reveal in Finder. The file tree's header for a whole project drops the path the same way.
- **Research Desk**: the sidebar lists a project's maps with the ones being worked first, and folds the paused ones
  into one line ("4 paused"), opened by a click or by being on one. With four paused maps among three driven ones, in
  map order, the active ones were hard to find. The overview's map cards put paused ones last.
- **Research Desk**: the library page and the reader, redesigned to the level of the rest of the app. The viewer's
  header showed a file path in mono and up to ten ungrouped buttons; the library list had three rows of system
  dropdowns; highlight colours were unexplained. Now: the item's title, grouped tools (zoom, page, Highlights, Box &
  ask), a Paper | Note switch, Teach me, and More (reload, VS Code, delete); a collection switcher with search, filter
  and sort menus, calmer rows, arrow keys; a Highlights legend that shows or hides each kind; a small dark bar over a
  selection. App-wide: the app's own tooltips in place of the system's (`tips.js`), its chevron on dropdowns.
- **Research Desk**: a library's **Add** takes several lines, one thing to add on each, and starts a session for each
  in turn (it took one; six or more ask first).
- **Research Desk**: a library holds any documents, not only papers. Its page listed the folders under `Papers/` and
  nothing else of the library (courses, notes kept as single files). Its top-level folders are now collections to
  switch between; an item is a folder with its documents, or a single file; Teach me and the trash work on any item;
  `add` and `teach` commands are set per collection. `/api/papers` is `/api/library`.
- **Research Desk**: **End** in the chat header closes a plain session's tab (`/api/session-end`). A paper's session
  is often for one question, and there was no way to close it from the app; what it wrote stays (replies pinned to the
  paper, lessons, the conversation). It asks first when the session is working or its project is not a paper library.
- **Research Desk**: each paper has its own session. Ask and Teach me went to whichever session the chat showed, so a
  second paper's questions landed in the first paper's conversation. They now go to the session named after the
  paper's folder, or start one; Add starts a session of its own for each paper.
- **Research Desk**: **Teach me** opens a box with the request ("Teach me this paper step by step."), to edit before
  it goes: your level, what to focus on. It went off at once, and the session then asked why the paper was being
  studied.
- **Research Desk**: a paper library's **Add** and **Teach me** send the commands its `add` and `teach` settings name.
  They asked in plain words, which reaches a skill only if the agent may start it by itself; a skill started only by
  its command (no description loaded in every session) was never reached.
- **Research Desk**: reading mode. In a 1050-pixel window the sidebar and the paper list left the paper 538 pixels
  (60% zoom). The file viewer's first button hides both while a file is open (the paper gets 1049 pixels, 123%) and
  becomes "‹ Papers" (or "‹ Files") to bring them back; the choice is kept. In a library the header drops VS Code and
  Delete paper is the trash icon, so it fits one row.
- **Research Desk**: a paper in a library has **Teach me** in the reader's header: it asks a session, in plain words,
  to teach the paper one step at a time (a study skill, if one is installed, picks that up), starting a session when
  there is none. There was no way to start that from the app.
- **Research Desk**: a question sent from the reader is drawn in the chat as its passage, folded to three lines, then
  the question (the bubble showed the file path, the whole passage and Claude Code's `<pasted_content>` tags); the
  paper list's two menus fit their words (they were cut at the box's edge); Delete or Backspace removes the highlight
  whose note is open.
- **Research Desk**: a reply is pinned to its passage again. Claude Code wraps a pasted (multi-line) message in
  `<pasted_content>` tags in its transcript, so a question sent from the reader no longer ended with the question and
  two real replies stayed unpinned; the tags are ignored when matching and taken out of chat bubbles. A question
  asked from an existing highlight is pinned too (it kept the highlight's kind and was skipped). A reply that came
  before its paper was opened is pinned when the paper opens (the chat loads at start, so its "turn ended" had already
  passed), and changes to a paper's marks are made one at a time (two at once lost one).
- **Research Desk keeps what you read.** A question about a passage left no trace on the paper. The reader now keeps
  marks beside the PDF (`<name>.marks.json`): a passage you highlight or ask about stays highlighted, the session's reply
  is pinned to it when its turn ends, and an agent can mark claims, the method, results and limitations. A project
  with `library = true` is a paper library with its own sidebar entry and page (papers on the left, searched and
  filtered by concept; the paper or its note on the right). Asking with no session starts a Claude session with the
  question instead of opening the New session dialog; pinch or ⌘-wheel zooms the paper; clicking Ask did nothing after
  a real click (its mouse-up closed the question box).
- **Research Desk reads papers.** A PDF opened in the built-in viewer could not be asked about: its text sat in an
  iframe the page cannot see into. The file viewer now draws PDFs with PDF.js: select a passage and press **Ask**, or
  **Box & ask** an equation or a figure, and the passage (or a crop), its page and your question go to a session.
  **Delete paper** moves a paper's folder (`paper.pdf` beside `note.md`) to the trash. Markdown in the viewer and in
  chat draws math (KaTeX) and the pictures a note links beside it.
- **Research Desk**: the file view keeps its pane's width (a long line pushed it under the chat panel); the backend
  queues 128 connections instead of 5 (the page opens one per file, and at start some were refused: in a test of six
  loads, most failed once and reloaded; none of eight after); every project in the sidebar has the same icon (a remote
  one is marked by its host tag).
- **`research-work`**: before reporting done, a worker stops the background commands it started. A leftover waiter
  blocked every close of a finished worker's tab (three exits typed into one pane, all backed out).
- **`codex-run`**: a start-up failure counts only when no tool call succeeded (the words quoted from a file gave a
  false failure); a relative run dir works, and running from inside the run dir no longer renames its own files.
- **`team-watch`** switches a fallen-back session to Sonnet 5.5 where it is (`/model`, `/effort` typed into it) and
  puts the saved defaults those commands change back; it no longer exits such a session, which failed whenever the
  session had background work.
- **`team-watch`** acts on a fallback only when the transcript herdr names is the one the session is writing now
  (written since the watch last saw the agent work): herdr can keep an old session id after a resume, and a driver on
  Sonnet was exited for a stale Opus 4.8 line.
- **`team-watch`** closes a worker's tab once its ticket is closed and it has sat idle for 30 minutes (8 of 19 worker
  tabs were on closed tickets). Its driver resume uses a valid agent name for pane ids with capitals (a resume exited
  a driver and then failed on `invalid_agent_name`), retries the start, and alerts with the resume command if it fails.
- Checked against Matt Pocock's skills at `abeeaf9` (2026-11-19): none of the skills this harness builds on changed.
  Taken from his new CI: `check.py` fails a skill header a strict YAML parser would reject (`team`'s description was one).
- **`team-watch`** also resumes on Sonnet 5.5 a driver or worker that Claude Code moved to its fallback model after a
  flag (its last reply came from Opus 4.x): such a session keeps working, so the safeguard-stop rule never saw it.
- **What waits on the human is one list, from tickets.** `waiting()` leaves out paused and closed maps (two asks of a
  map paused that day still showed); `research-status --check` flags a live map whose tickets are all closed with no
  question open (a driver waited on a route decision it had asked only in its pane); `team-watch` tells a driver whose
  `needs-you` line names no open question ticket to file one; the desk starts each turn from the list, not from relays.
- **A failed alert is visible.** The alert command's exit code is recorded per alert in `scratch/agents/alerts.log`;
  `research-status --now` says how many did not reach you, `driver.log` gets "ALERT NOT DELIVERED", and
  `research-preset` shows a preset as `broken` when a program it needs is missing. 15 of 15 alerts had failed silently
  for 9 days: the watch ran in a container without the Mac's programs.
- **`team-watch`** alerts when its clock jumped (the machine or its VM slept; 4 h on 11-20 with every wait stalled).
- **`team-worker --close <ticket id>`** ends a worker and closes its tab; opening a worker names the tabs still open
  on resolved tickets (8 of 13 were; 25 sessions held 8.5 of 12 GB).
- **`review`** has a third verdict, **EDIT**: wording only, applied by the doer, no re-check. FAIL now means a number,
  the rule or the code is wrong. Reviewers were already writing "FAIL (wording only)": 55% of Spec verdicts were FAIL.
- **`delete-guard`** treats a message to another agent (`herdr agent prompt`) as text and honours quotes: a driver sat
  15 min, twice, for telling a worker which delete it had declined.
- **`team-up`** starts the desk and the driver with a 400k compaction window (`TEAM_COMPACT`), and no longer needs
  `USER` set (a container). New projects' `.gitignore` covers `.trash/`.
- **Confirmation is derived, not tagged.** A resolved experiment records `repeats: <n>`; `research-status --now` lists
  each answer resting on one run that open tickets build on. The hand-written `[tentative]` / `[established]` tags are
  gone from the skills: in one project 82 tickets resolved in 12 days without a single `[established]` line.
- **`wayfinder`**'s map and ticket format moved, word for word, to `MAP-FORMAT.md` beside it; the skill keeps the
  procedures (15 KB to 7 KB for the sessions that only need those).
- **Three repeated mistakes became checks or tool behaviour:** `research-status --check` flags a ticket line stamped
  later than now (workers wrote Log times 10-30 min ahead); `team-worker` tells each worker to claim as
  `worker <pane>` (two workers claiming as one name blocked a dispatch twice); STYLE: a wait ends on its condition, in
  a loop, not on one timed check (a worker sat idle 1 h 50 min).
- **`trash --empty`** only empties under one folder (default: the current one) and lists each entry; unscoped, it
  deleted 46 entries of other sessions. **`codex-run`** fails when Codex could not start its tools (it printed "done").
- Removed the unused `wait-what` skill.
- **Research Desk:** Settings → Pictures for review saves a picture of each main screen (headless Chrome) where a
  session without a browser can read them; a session may ask for a round itself once you allow it.
- **Research Desk:** a simpler look: black-and-white controls so colour only marks a state, hairline cards, plain
  replies, a larger message box that names the machine and model it goes to, a New session button, blurred dialogs,
  thin scrollbars; one main action per page header.
- **Research Desk:** the GPU page offers to update `[gpu_pools]` when `~/.ssh/config` renamed hosts (an old name kept
  as an alias leads to the new one), dropped them, or has numbered hosts no pool lists.
- **Research Desk:** Mark & ask on a figure (circle what's wrong, the marked copy and a note go to the ticket's worker
  or the desk); a ticket's Trace tab (what its sessions did, step by step, here and on herdr machines).
- **Map ids** are `M1`, `M2`, … and ticket ids `M1-01`, … throughout the docs, examples and `team-up`.
- **Research Desk:** sessions on herdr's saved machines (a Docker container on this Mac, another computer) show beside
  this Mac's, in their projects, with chat, prompts, keys, btw and paste; the sidebar footer lists the machines. Fixed:
  remote calls used a later ssh option list (a connection of their own, not the shared one), and the GPU page and
  server file views reached paused or Duo hosts outside the guard.
- **`research-preset`** lists presets in sections (this machine, each pick-one choice, bundles, per project), each with
  on / partly / off and one short line; the long descriptions moved to the README.
- **Delete presets**, one of three: `deletes-ask` (was `safe-deletes`: a recursive delete asks, declined after 15 min
  with a pointer to `trash`), `deletes-trash` (refused at once; `delete-guard --policy trash`) or `deletes-allow` (no
  guard; in auto mode an `autoMode.allow` rule lets the classifier pass deletes). `research-preset` gained `settings`
  (dotted keys in `~/.claude/settings.json`; a `$` marker such as `$defaults` is never taken out), `group` (presets that
  exclude each other: applying one takes out the others' rules, hooks and rule blocks) and `was` (an old name still
  works and its rule block is replaced). `delete-guard` refuses at once, with the `trash` pointer, in a session without
  prompts (`bypassPermissions`, `dontAsk`). Settings backups get unique names. `research-init` offers the choice once
  per machine.
- **`run-card`** rewritten from how its 39 cards were used: 36 were over 4,000 characters (median 7.3 KB), with table
  cells written as paragraphs. A card is about one screen; long configs sit beside it as files; a run that differs from
  a reference lists only the differences; the line under the title says what a comparison must match; entries count as
  read on the card's `checked` date unless marked (reported) or (inferred); `status` is one word, now including `paused`
  and `stopped`. `research-status --check` reports a card with another status word, a missing field, or no link from its
  ticket (5 cards across both projects).
- **Presets:** optional setup comes as named presets (`presets/`), applied, shown (`--dry-run`) and taken out
  (`--remove`) by `research-preset` or `install.sh --preset <name>`: `alerts` (`extras/notify.py` routes each alert by
  kind: a Moshi push and a Mac sound by default), `safe-deletes` (now `deletes-ask`: `trash`, the `delete-guard` hook and
  a rule for Claude and Codex), `team-hooks` (the roster hook), `claude-codex` (a project's delegation rows: work in your field that
  Claude's safeguards often stop, and large reviews, go to Codex at xhigh; an option, not in `recommended`) and
  `recommended` (alerts, deletes-ask, team-hooks). `research-init` asks: for delegation, one agent (the default: all Claude in
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
