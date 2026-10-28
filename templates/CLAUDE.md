@AGENTS.md

## Claude Code
Harness: maps/tickets
<!-- Work is organised in maps (one destination each) and tickets (one question each), kept in the issue tracker named in
     docs/agents/issue-tracker.md. Open a map with /wayfinder, work a ticket with /research-work, a map's frontier with
     /research-drive; run a team with /team. -->
Started: {{DATE}}

{{SCOPE_IMPORT}}
@~/research-harness/rules/style.md

- The harness is still being refined. When a shared rule or research skill is wrong, missing, or gets in the way, add one
  line to `~/research-harness/FEEDBACK.md` (date, project, file, what happened → suggested fix) and carry on. Edit harness
  files only when the user asks.
- A mistake that recurs gets a check that fails (in a tool, a script or the project's code), not another sentence;
  instructions are for judgment calls.
- Folder structure: `~/research-harness/rules/layout.md`.
