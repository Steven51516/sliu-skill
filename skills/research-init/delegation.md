# Delegation

Where delegated work goes in this project. Any session may delegate: the one the user talks to, an implementer working a ticket, a driver. Edit the rules freely; the skills read them every time.

## Routing

Delegating is optional. A session does a task itself, or delegates it when that helps (parallel work, a long task, a fresh pair of eyes), to whom it judges best. A rule below is a must: work it matches goes where the rule says.

| work | goes to | how |
|---|---|---|

<!-- No rules yet: every session decides for itself. Example of a rule:
| biology-related coding, analysis, paper reading and review | Codex, gpt-6.1-sol, xhigh (medium for simple tasks) | `codex-run` (below) |
-->

## When a skill says "delegate" a task

A bounded task: code, data, an analysis, a reading. If a rule matches it, it goes where the rule says; otherwise do it yourself or delegate it as you judge. Brief a delegate in a file: the goal, input paths (not contents), outputs, stop conditions, the commands that verify it, and what good enough means for this task (the delegate judges whether a defect blocks it). Run it in the background, in `scratch/agents/<date>-<slug>/`. Check what comes back before it enters a ticket (the `rigor` skill).

## When a skill says "spin up a subagent", "a background agent" or "parallel sub-agents"

As a delegated task: a matching rule decides; otherwise you do.

## When a skill says "use implementer subagents" or "kick off more implementer subagents"

A session that works one ticket end to end, and delegates inside it as it judges: a background subagent of this session's own agent, told "Call the Skill tool with `research-work` on <ticket> in <project>. End with one line: `done | running | blocked <ticket>: <one line>`."

## When a skill says "review"

Once per ticket that `rigor`'s table says needs it: a fresh session that did not do the work, where a matching rule says, else one you choose. It calls the Skill tool with "review" on the ticket, and writes only its PASS/FAIL lines under the answer.

## When a skill says "ask the user" or "tell the user"

Ask in this session.

## Commands

Codex: write the brief to `<run dir>/brief.md` (it names its report `<run dir>/report.md`, written in pieces of at most ~80 lines), then, from the project folder:

    codex-run <run dir>              # a follow-up: write <run dir>/followup.md, then codex-run <run dir> --resume

Effort: `xhigh`, the default, for reviews and complex tasks; `medium` for a simple one (a lookup, a format
conversion, a small scripted edit): `CODEX_EFFORT=medium codex-run <run dir>`.

`codex-run` sets the model and effort (`CODEX_MODEL`, `CODEX_EFFORT`) and the sandbox on every call, resumes included, strips tokens and keys from Codex's environment, and fails loudly if Codex's header shows anything else.

Claude Code: from a Claude session, a background subagent (the Agent tool). From another agent, headless, keeping only the
secret Claude signs in with:

    env $(env | cut -d= -f1 | grep -E 'TOKEN|KEY|SECRET|PASSWORD|AUTH' | grep -vx CLAUDE_CODE_OAUTH_TOKEN | sed 's/^/-u /') \
      claude -p --model <model> --effort <effort> --permission-mode auto --strict-mcp-config \
      --output-format json "$(cat <run dir>/brief.md)" > <run dir>/result.json

## Rules

- If the delegate a rule requires fails (it can't start, can't log in, or errors out), wait and retry, or ask the user; never hand the work to someone the rule doesn't name.
- A delegate writes only the paths its brief names, and never edits a map, `STATUS.md` or another agent's memory. Over ssh the local sandbox does not apply, so the brief and the always-ask list in `rules/style.md` are the guard.
- No process waits on a marker file another session is supposed to write: chain dependent steps in one script.
- Long GPU jobs are launched detached the way the scope file says; the PID and log path go into the ticket's Assets.
