# Delegation

Where delegated work goes in this project; the skills read it every time. Delegating is optional: a session does a task
itself, or delegates it when that helps (parallel work, a long task, a fresh pair of eyes). A rule below is a must for the
work it matches.

| work | goes to | how |
|---|---|---|

<!-- No rules yet. Example: | biology-related coding, analysis, paper reading and review | Codex, gpt-6-astra, xhigh | `codex-run` | -->

## When a skill says…
- **"delegate"**, **"spin up a subagent"**, **"a background agent"**, **"parallel sub-agents"**: a matching rule decides;
  otherwise do it yourself or delegate as you judge.
- **"use implementer subagents"**: a fresh background subagent per ticket (a new context window, never a fork), told "Call the Skill tool with `research-work` on
  <ticket> in <project>. End with one line: `done | running | blocked <ticket>: <one line>`." A subagent cannot open
  subagents of its own: what it would hand to a Claude subagent it does itself (a team's workers are full sessions and can).
- **"review"**: once per ticket that `review` says needs it, plus a re-check of only what a fix changed: a fresh session that did not do the work (a rule may name one). It
  writes only its PASS/FAIL lines under the answer.
- **"ask the user"**, **"tell the user"**: in this session.

## Briefs and commands
A brief is `scratch/agents/<date>-<slug>/brief.md`, short and outcome-first: the result wanted, input paths (not contents),
outputs, what done looks like and how to check it, and only the hard constraints. One task per run; a follow-up carries
only the change. A long report goes to `report.md` in pieces of at most ~80 lines. Check what comes back before it enters
a ticket (`rigor`).
- **Codex:** `codex-run <run dir>`; a follow-up: write `followup.md`, then `codex-run <run dir> --resume`. It fixes model,
  effort and sandbox on every call, strips secrets, adds a scope preamble, and fails loudly on a wrong header, a non-zero
  exit or an empty answer. Effort: `xhigh` (default), always for a review or a re-check; `CODEX_EFFORT=medium` only for a simple
  task that is not a review.
- **Claude:** a background subagent (the Agent tool, with the model and effort a rule names). From another agent:
  `claude -p --model <m> --effort <e> --permission-mode auto --output-format json "$(cat brief.md)"`, with every secret
  in the environment unset except `CLAUDE_CODE_OAUTH_TOKEN`.

## Rules
- If the delegate a rule requires fails, wait and retry, or ask the user; never hand the work to someone the rule doesn't name.
- A delegate writes only the paths its brief names and never edits a map or `STATUS.md`; over ssh, the brief and
  `STYLE.md` are the guard.
- Chain dependent steps in one script; nothing waits on a marker file another session writes.
- Long GPU jobs launch detached as the scope file says; their PID and log path go in the ticket's Assets.
