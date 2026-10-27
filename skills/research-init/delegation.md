# Delegation

Where delegated work goes in this project. Any session may delegate: the one the user talks to, an implementer working a ticket, a driver. Edit the rules freely; the skills read them every time.

## Routing

Delegating is optional. A session does a task itself, or delegates it when that helps (parallel work, a long task, a fresh pair of eyes), to whom it judges best. A rule below is a must: work it matches goes where the rule says.

| work | goes to | how |
|---|---|---|

<!-- No rules yet: every session decides for itself. Example of a rule:
| biology-related coding, analysis, paper reading and review | Codex, gpt-6.1-sol, xhigh | `codex exec` (below) |
-->

## When a skill says "delegate" a task

A bounded task: code, data, an analysis, a reading. If a rule matches it, it goes where the rule says; otherwise do it yourself or delegate it as you judge. Brief a delegate in a file: the goal, input paths (not contents), outputs, stop conditions, the commands that verify it, and what good enough means for this task (the delegate judges whether a defect blocks it). Run it in the background, in `scratch/agents/<date>-<slug>/`. Check what comes back before it enters a ticket (the `rigor` skill).

## When a skill says "spin up a subagent" or "a background agent"

As a delegated task: a matching rule decides; otherwise you do.

## When a skill says "spin up an implementer subagent"

A session that works one ticket end to end, and delegates inside it as it judges: a background subagent of this session's own agent, told "Call the Skill tool with `research-work` on <ticket> in <project>. End with one line: `done | running | blocked <ticket>: <one line>`."

## When a skill says "review"

Once per ticket that `rigor`'s table says needs it: a fresh session that did not do the work, where a matching rule says, else one you choose. It calls the Skill tool with "review" on the ticket, and writes only its PASS/FAIL lines under the answer.

## When a skill says "ask the user" or "tell the user"

Ask in this session.

## Commands

Codex:

    env $(env | cut -d= -f1 | grep -E 'TOKEN|KEY|SECRET|PASSWORD|AUTH' | sed 's/^/-u /') \
      codex exec --skip-git-repo-check -C <project dir> -s workspace-write \
      -c sandbox_workspace_write.network_access=true -m <model> -c 'model_reasoning_effort="<effort>"' \
      -o <run dir>/last.md - < <run dir>/brief.md > <run dir>/codex.log 2>&1

The brief names its report `<run dir>/report.md`, written in pieces of at most ~80 lines (long single writes have been lost to the network); `-o` only keeps Codex's final message in `last.md` and would overwrite a report written there. A follow-up resumes by the session id in `codex.log`'s header, from the project folder; `resume` has no `-s` or `-C` and does not keep the sandbox, so pass it as config:

    codex exec resume <id> --skip-git-repo-check -c sandbox_mode='"workspace-write"' \
      -c sandbox_workspace_write.network_access=true -o <run dir>/last.md - < <run dir>/followup.md

Claude Code, headless:

    env $(env | cut -d= -f1 | grep -E 'TOKEN|KEY|SECRET|PASSWORD|AUTH' | sed 's/^/-u /') \
      claude -p --model <model> --effort <effort> --permission-mode auto --strict-mcp-config \
      --output-format json "$(cat <run dir>/brief.md)" > <run dir>/result.json

## Rules

- The `env -u` prefix keeps tokens and keys out of a delegate's environment.
- A delegate writes only the paths its brief names, stops only processes it started (by PID), and never edits a map, `STATUS.md` or another agent's memory. Over ssh the local sandbox does not apply, so these rules are the guard.
- No process waits on a marker file another session is supposed to write: chain dependent steps in one script.
- Long GPU jobs are launched detached the way the scope file says; the PID and log path go into the ticket's Assets.
