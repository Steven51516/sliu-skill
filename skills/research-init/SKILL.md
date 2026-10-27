---
name: research-init
description: Set up a research project for the harness, new or existing: its name, scope (where it runs), optional content, and team (default: Claude plans, Codex works and reviews).
argument-hint: "<project-name> [optional one-line direction]"
disable-model-invocation: true
---

Setup only: the direction is discussed later, in a session inside the project, so it gets recorded there. Prompt-driven:
explore, ask one section at a time, show drafts, then write.

## 1. Explore
Read what exists; don't assume.
- The target folder: does it exist? Does it already have `CLAUDE.md`, `AGENTS.md`, `docs/agents/` (this skill's prior
  output), `maps/`, or the old `tracks/` layout?
- `git remote -v`: is this a GitHub or GitLab repo? Which one?
- Parent folders' `CLAUDE.md` (walk up from the target): does one already import a scope file (an org's server rules)?
- Available scopes: the harness's [scopes/](../../scopes/), plus any scope file a parent imports.
- Team tooling: `codex --version`, `claude --version`.

## 2. Ask, one section at a time
Lead each section with the recommended answer so the user can accept it in a word; skip a section the arguments or
exploration already settled.
- **A. Name and place.** A short kebab-case name; the folder goes under the scope's projects root (or the folder the user
  is in, for an org folder like `scinetics/`).
- **B. Scope.** Recommend the scope a parent `CLAUDE.md` already loads (then it is inherited, not imported again), else
  the one this machine's other projects use. A place with no scope file yet: draft one from [scopes/README.md](../../scopes/README.md)
  with the user, kept with the org's own folder when it names internal hosts.
- **C. Content (optional, skippable).** A one-line direction; where the code lives (this folder, or a server path such as
  `node-16:~/code/<name>`); whether the folder is under git (recommend no for a knowledge-only folder whose code lives
  elsewhere). Papers, links and briefs can wait: they go in `resources/` later.
- **D. Issue tracker.**
  > Explainer: The "issue tracker" is where maps and tickets live for this project. Skills like `wayfinder`,
  > `research-ticket`, `research-work` and `research-drive` read from and write to it. They need to know whether to call
  > `gh issue create`, write a markdown file under `maps/`, or follow some other workflow you describe. Pick the place you
  > actually track work for this project.

  If a `git remote` points at GitHub, propose GitHub; at GitLab, propose GitLab. Otherwise (or if the user prefers), offer
  **Local markdown**: maps and tickets live as files under `maps/` (good for solo projects, folders without git, and
  tickets that keep their code beside them), or **Other**: ask the user to describe the workflow in one paragraph and
  record it as freeform prose. Record the choice in `docs/agents/issue-tracker.md` from
  [templates/](../../templates/) (`issue-tracker-local.md`, `-github.md`, `-gitlab.md`).
- **E. Team.** The role table in [templates/team.md](../../templates/team.md): every session is the planner (Claude Code),
  which calls the worker and the reviewer (Codex by default). Change any role's agent, model or effort on the user's word.

## 3. Show drafts
Show the drafts of `AGENTS.md` (shared by every agent: read-first pointers, roles, code location, records, project notes),
`CLAUDE.md` (`@AGENTS.md` plus the Claude-only imports and session rules), `docs/agents/team.md` and
`docs/agents/issue-tracker.md`. Let the user edit
before writing.

## 4. Write
- **New folder:** run [init.sh](init.sh) `<name> ["<direction>"]` with the chosen settings as
  environment variables: `SCOPE_FILE`, `SCOPE_INHERITED`, `PROJECTS_ROOT`, `POOL_ROOT`, `SCRATCH_ROOT`,
  `CODE_LOCATION`, `GIT`, `TRACKER` (the header of `init.sh` lists them). Then apply any edits the user made to the drafts.
- **Existing folder (adopt):** never run `init.sh` and never overwrite. Create the missing pieces (`AGENTS.md`,
  `docs/agents/team.md`, `docs/agents/issue-tracker.md`, `GLOSSARY.md` lazily later) from the templates. A project on the
  old `tracks/` layout moves to the local tracker with `research-migrate <project>` (run `--dry-run` first and show it). In an existing `CLAUDE.md`, add
  `@AGENTS.md` at the top and a `## Claude Code` block with the harness header, or refresh that block in place if it is
  already there; leave the user's other text where it is. Move nothing the user wrote without asking.
- Codex reads only `AGENTS.md` and cannot follow `@` imports, which is why shared rules live there as plain path pointers.

## 5. Done
Name the files written. Tell the user they can drop material into `<project>/resources/` (see its README): a direction and
constraints in `BRIEF.md`, links in `LINKS.md`, PDFs in `papers/`, existing code or results in `prior-work/`. Next step:
open a session in the project (`cd <project> && claude`) and run `/wayfinder "<first idea>"` to open the first map. Who plans, works and reviews
lives in `docs/agents/team.md`, and where maps live in `docs/agents/issue-tracker.md`; editing either is how to change
them later.
