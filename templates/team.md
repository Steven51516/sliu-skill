# Team
<!-- Written by research-init on {{DATE}}. Edit freely: change an agent, model or effort in the table; the rest follows. -->

| role | does | agent | model | effort |
|---|---|---|---|---|
| **planner** | every session: talks to the human, charts maps, drafts and approves tickets, briefs the worker and checks what comes back, writes answers and maps; writes small pure-CS run glue itself (launcher, scheduler hook, checkpoint keeper), starting from the last proven version | Claude Code | claude-opus-5-5 | xhigh |
| **worker** | a ticket's domain work, one bounded task per call: model code, data, analysis, papers | Codex CLI, called by the planner | gpt-6.1-sol | xhigh |
| **reviewer** | one review per ticket at close (`rigor`: the answer, its numbers and the code diff behind them); always a fresh call that did not do the work | Codex CLI, called by the planner | gpt-6.1-sol | xhigh |

## How each is called
- Every session is the planner, including each pane of a team (desk, driver, worker; `~/research-harness/skills/team/TEAM-PROTOCOL.md`).
  A session holding a ticket hands its work to the worker; the driver (or, without a team, the session that closes the
  ticket) calls the reviewer.
- One task per call, briefed in a file: the goal, input paths (not contents), outputs, stop conditions, verification
  commands, and what good enough means for this task (the worker judges whether a defect blocks it). Run it in the background; run dir `scratch/agents/<date>-<slug>/`.

Codex CLI:

    env $(env | cut -d= -f1 | grep -E 'TOKEN|KEY|SECRET|PASSWORD|AUTH' | sed 's/^/-u /') \
      codex exec --skip-git-repo-check -C <project dir> -s workspace-write \
      -c sandbox_workspace_write.network_access=true -m <model> -c 'model_reasoning_effort="<effort>"' \
      -o <run dir>/last.md - < <run dir>/brief.md > <run dir>/codex.log 2>&1

The brief names its report `<run dir>/report.md`, written in pieces of at most ~80 lines (long single writes have been
lost to the network); `-o` only keeps Codex's final message in `last.md` and would overwrite a report written there.
A follow-up resumes by the session id in `codex.log`'s header, from the project folder. `resume` has no `-s` or `-C` and
does not keep the sandbox, so pass it as config:

    codex exec resume <id> --skip-git-repo-check -c sandbox_mode='"workspace-write"' \
      -c sandbox_workspace_write.network_access=true -o <run dir>/last.md - < <run dir>/followup.md

If a role is set to Claude Code instead, call it headless:

    env $(env | cut -d= -f1 | grep -E 'TOKEN|KEY|SECRET|PASSWORD|AUTH' | sed 's/^/-u /') \
      claude -p --model <model> --effort <effort> --permission-mode auto --strict-mcp-config \
      --output-format json "$(cat <run dir>/brief.md)" > <run dir>/result.json

## Rules
- The `env -u` prefix keeps tokens and keys out of the called agent's environment.
- The planner checks the worker's result with `rigor` before it enters the ticket.
- The worker writes only the paths its brief names, stops only processes it started (by PID), and never edits `map.md`,
  `STATUS.md` or the planner's memory. Over ssh the local sandbox does not apply, so these rules are the guard.
- The reviewer writes only its PASS/FAIL lines under the answer.
- No process waits on a marker file another session is supposed to write: chain dependent steps in one script.
- Long GPU jobs: the worker launches them detached the way the scope file says and reports the PID and log path; the
  planner records them in the ticket's Assets and monitors them.
