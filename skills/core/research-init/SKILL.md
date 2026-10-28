---
name: research-init
description: "Configure a project for the research skills: set up its scope, issue tracker, delegation and domain doc layout. Run once before first use of the other research skills."
argument-hint: "<project-name> [optional one-line direction]"
disable-model-invocation: true
---

# Research Init

Scaffold the per-project configuration that the research skills assume:

- **Scope**: where the project runs (machines, storage, GPUs, network): one scope file the project imports
- **Issue tracker**: where maps and tickets live (local markdown for a folder without a remote; GitHub and GitLab are also supported out of the box)
- **Delegation**: where delegated work goes (code, analysis, reading, review), and how each agent is called
- **Domain docs**: where `GLOSSARY.md` and decisions live, and the consumer rules for reading them

This is a prompt-driven skill, not a deterministic script. Explore, present what you found, confirm with the user, then write. The direction itself is discussed later, in a session inside the project, so it gets recorded there.

## Process

### 1. Explore

Look at the target folder to understand its starting state. Read whatever exists; don't assume:

- Does the folder exist? `AGENTS.md` and `CLAUDE.md` at its root: does either exist? Is there already a `## Claude Code` block in `CLAUDE.md`?
- `docs/agents/`: does this skill's prior output already exist?
- `maps/`: a sign that the local-markdown tracker is already in use; `tracks/`: the old layout, to migrate
- `git remote -v` and `.git/config`: is this a GitHub or GitLab repo? Which one?
- `GLOSSARY.md` and `docs/decisions.md` at the root
- Parent folders' `CLAUDE.md` (walk up from the target): does one already import a scope file (an org's server rules)? The available scopes are in [scopes/](../../../scopes/), plus any a parent imports
- `codex --version`, `claude --version`: which agents can take a role

### 2. Present findings and ask

Summarise what's present and what's missing. Then take the sections in order. One section, one answer, then the next.

Lead each section with the recommended answer so the user can accept it in a word. Give a one-line explainer only when the choice genuinely branches; skip the section entirely when exploration already settled it.

**Section A: Name and place.** A short kebab-case name; the folder goes under the scope's projects root (or the folder the user is in, for an org folder). Optional: a one-line direction, and where the code lives (this folder, or a server path such as `<host>:~/code/<name>`).

**Section B: Scope.** Recommend the scope a parent `CLAUDE.md` already loads (then it is inherited, not imported again), else the one this machine's other projects use. A place with no scope file yet: draft one from [scopes/README.md](../../../scopes/README.md) with the user, kept with the org's own folder when it names internal hosts.

**Section C: Issue tracker.**

> Explainer: The "issue tracker" is where maps and tickets live for this project. Skills like `wayfinder`, `to-tickets`, `research-work` and `research-drive` read from and write to it. They need to know whether to call `gh issue create`, write a markdown file under `maps/`, or follow some other workflow you describe. Pick the place you actually track work for this project.

If a `git remote` points at GitHub, propose that. If a `git remote` points at GitLab (`gitlab.com` or a self-hosted host), propose GitLab. Otherwise (or if the user prefers), offer:

- **GitHub**: maps and tickets live in the repo's GitHub Issues (uses the `gh` CLI)
- **GitLab**: maps and tickets live in the repo's GitLab Issues (uses the [`glab`](https://gitlab.com/gitlab-org/cli) CLI)
- **Local markdown**: maps and tickets live as files under `maps/` in this project, each ticket in a folder beside its code (good for solo projects, folders without git, or a knowledge folder whose code lives on a server)
- **Other** (Jira, Linear, etc.): ask the user to describe the workflow in one paragraph; the skill will record it as freeform prose

Record the choice in `docs/agents/issue-tracker.md`.

**Section D: Delegation.** Where delegated work goes: who writes code, runs analyses, reads papers and reviews results. Default to [delegation.md](delegation.md) with no rules: each session decides whether to delegate and to whom. If the user has rules (by topic, by kind of work, or by role, e.g. "biology-related coding, analysis, paper reading and review go to Codex"), write each as a row, with the agent's model and effort.

**Section E: Domain docs.** Default to one `GLOSSARY.md` + `docs/decisions.md` at the project root. Write it without asking.

### 3. Confirm and edit

Show the user a draft of:

- `AGENTS.md` (read by every agent: read-first pointers, code location, project notes) and `CLAUDE.md` (`@AGENTS.md` plus the Claude-only imports and session rules), or the block to add to an existing `CLAUDE.md`
- The contents of `docs/agents/issue-tracker.md`, `docs/agents/delegation.md` and `docs/agents/domain.md`

Let them edit before writing.

### 4. Write

**New folder:** run [init.sh](init.sh) `<name> ["<direction>"]` with the chosen settings as environment variables (its header lists them: `SCOPE_FILE`, `SCOPE_INHERITED`, `PROJECTS_ROOT`, `POOL_ROOT`, `SCRATCH_ROOT`, `CODE_LOCATION`, `GIT`, `TRACKER`). Then apply any edits the user made to the drafts.

**Existing folder:** never run `init.sh` and never overwrite. Create the missing pieces from the templates. Keep both `AGENTS.md` and `CLAUDE.md`: Codex reads only `AGENTS.md` and cannot follow `@` imports, so shared rules live there as plain path pointers, and `CLAUDE.md` starts with `@AGENTS.md`. If a `## Claude Code` block already exists in `CLAUDE.md`, update its contents in place rather than appending a duplicate. Don't overwrite user edits to the surrounding sections. A project on the old `tracks/` layout moves to the local tracker with `research-migrate <project>`: run `--dry-run` first and show it.

Write the docs files using the seed templates in this skill folder as a starting point:

- [issue-tracker-github.md](./issue-tracker-github.md): GitHub issue tracker
- [issue-tracker-gitlab.md](./issue-tracker-gitlab.md): GitLab issue tracker
- [issue-tracker-local.md](./issue-tracker-local.md): local-markdown issue tracker
- [delegation.md](./delegation.md): where delegated work and reviews go
- [domain.md](./domain.md): domain doc consumer rules + layout

For "other" issue trackers, write `docs/agents/issue-tracker.md` from scratch using the user's description.

### 5. Done

Tell the user the setup is complete and which research skills will now read from these files. Mention they can edit `docs/agents/*.md` directly later; re-running this skill is only necessary if they want to switch issue trackers or restart from scratch. They can drop material into `resources/` (a direction in `BRIEF.md`, links in `LINKS.md`, PDFs in `papers/`), and the next step is to open a session in the project and run `/wayfinder "<first idea>"` to open the first map.
