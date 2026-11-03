# Glossary

The words the skills use, in the order you meet them. Matt Pocock's terms keep his meaning; the rest are added here.

| Term | Meaning |
|---|---|
| **project** | One research effort in one folder, with its own `AGENTS.md`, maps and records. |
| **scope file** | The facts about where a project runs: scheduler, storage, GPUs, network. The skills say "the way the scope file says" and never name a machine. |
| **map** | The plan for reaching one destination: decisions so far, the fog, what is out of scope, and the Contract. Rewritten to stay current, never appended to. |
| **destination** | What the map is for, stated so it can be measured ("TM-score 0.7 on benchmark B"). |
| **fog** | Questions you can see coming but cannot yet ask sharply enough to ticket (*Not yet specified*). |
| **Contract** | A map's fixed terms: the benchmark every ticket is scored on, the reference recipe, and what may be done without asking. Only the human changes it. |
| **ticket** | One question on a map, sized to one agent session. Types: `experiment`, `task`, `research`, `grilling`, `prototype`. |
| **blocking edge** | "This ticket needs that one answered first." The edges make the map a task graph. |
| **frontier** | The tickets whose blockers are all resolved: ready to start now. |
| **pre-registration** | An experiment's success and stop criteria, written and approved before anything runs; never edited after results are seen. |
| **asset** | A run, arm, smoke test or variant of a ticket: a row in its Assets table, never a ticket of its own. |
| **pass** | One call of `research-drive`: read state, check jobs, merge, dispatch, file next tickets, log. `/loop` repeats it. |
| **implementer** | A fresh session that works one ticket (`research-work`): a subagent in a single session, a worker tab in a team. |
| **review** | A fresh reviewer's check of an answer on three axes: **Fair** (the `rigor` rules), **Spec** (the pre-registered rule, no overclaim), **Code** (the code does what the ticket says). |
| **rigor** | The rules for a trustworthy answer: verify the measurement, same benchmark, numbers from files with their denominator, no leakage, every difference recorded. |
| **screen / confirm** | A cheap first result tagged `[tentative]`, and the repeat that makes it `[established]`. |
| **milestone** | A closed map's one-line outcome, listed in `STATUS.md`. |
| **held / paused** | A ticket or map taken off the frontier by the human; only the human lifts it. |
| **desk / driver / worker** | Team roles: the session you talk to, the one driving a map, and one per ticket. |
| **roster** | `scratch/agents/roster.md`: who is on the team and at which herdr pane. |
| **always-ask** | The actions in `STYLE.md` that need the human's OK every time (large GPU budgets, deleting data, posting externally). |
