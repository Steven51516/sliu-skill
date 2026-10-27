---
name: retro
description: "Retrospective on research sessions, a ticket or a map: find where the human had to babysit or correct the agent, and propose fixes to the agents' environment."
disable-model-invocation: true
---

You are improving the agents' **environment** (rules, maps,
checks, pointers, skills) so that future sessions need less steering. You are not re-judging the research.

## Steps
1. Call the Skill tool with `writing-for-agents` for the writing style guide.
2. **Read the primary sources** for the scope the user names (default: this session). The human's own prompts are the best
   evidence: `~/.claude/history.jsonl` (field `project`), transcripts in `~/.claude/projects/<project-dir>/<session>.jsonl`
   (user-typed messages only, not tool results), and the tickets and maps of the period. Prompts can hold pasted secrets:
   never copy them into files, redact them in quotes, and delete any scratch copies you made.
3. **Look for candidates** in these categories. Count occurrences; quote the human briefly, with dates.
   - **Orientation:** turns spent re-orienting a new session (pasting paths, recaps). Fix: a current map, a navigation
     pointer in the project `CLAUDE.md`, a resolved ticket missing from its map (`research-status --check`).
   - **Navigation:** time spent finding files, data or paths. Fix: a pointer in the project `CLAUDE.md` or the map's Notes.
   - **Automated checks:** a mistake a check could have caught (a bad shard, an eval path that silently produced nothing, a
     leak, a wrong row count). Prefer building the check (a preflight item, an invariant probe, a `research-status` warning) over
     writing a rule. Look for a check that exists but is unwired or silently broken first.
   - **Repeated instructions:** the same instruction given in several sessions (which nodes, proxy, logging account).
     Fix: one line in the project or scope rules, or a check in the launcher.
   - **Judgement slips:** premature verdicts, components the agent invented, re-running results the human trusts.
     Fix: pre-registration fields, the reference recipe in the map's Notes, the established line in Decisions so far.
   - **Monitoring:** the human polling for status. Fix: report on job completion, keep the ticket's Assets table current.
   - **Vocabulary:** terms the human had to ask about. Fix: `GLOSSARY.md` (`domain-modeling`).
   - **No-ops and sprawl:** rules or `CLAUDE.md` lines that change nothing, or files too long to stay relevant.
   - **Tool economy and information access:** expensive calls that could be streamlined; logs, job state or dashboards the
     agent could not see.
4. **Present** the candidates by severity: evidence, fix, and where it lands. Harness-level fixes become a line in
   the harness's `FEEDBACK.md` (or a harness edit, only when the user asks); project-level fixes go to the project's
   `CLAUDE.md`, `common/`, a map's Notes or `GLOSSARY.md`.

## Reference
- `CLAUDE.md` is pushed into every session's context: keep it to navigation pointers and the few rules that change behaviour.
- Docs and maps are reached by pointers; skills carry procedures. Look for an existing home before creating a new file.
