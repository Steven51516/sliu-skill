@AGENTS.md

## Claude Code
Harness: maps/tickets
<!-- Work is organised in maps (one destination each) and tickets (one question each), kept in the issue tracker named in
     docs/agents/issue-tracker.md. Open a map with /wayfinder, work a ticket with /research-work, a map's frontier with
     /research-drive; run a team with /team. -->
Started: {{DATE}}

{{SCOPE_IMPORT}}
@~/research-harness/rules/style.md

- On opening a session, call the Skill tool with `resume`: it reports the state, proposes one next step, and asks. No
  grilling unless the human asks.
- The harness is still being refined. When a shared rule or research skill is wrong, missing, or gets in the way, add one
  line to `~/research-harness/FEEDBACK.md` (date, project, file, what happened → suggested fix) and carry on. Edit harness
  files only when the user asks.
- Folder structure: `~/research-harness/rules/layout.md`.
