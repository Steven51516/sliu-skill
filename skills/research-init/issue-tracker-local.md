# Issue tracker: Local Markdown

Maps and tickets for this project live as markdown files in `maps/`.

## Conventions

- One map per destination: `maps/<id>-<slug>/map.md`, with `id` counting up (`T1`, `T2`, …) and never reused
- One folder per ticket: `maps/<map>/tickets/<NN>-<slug>/ticket.md`, numbered from `01`, never a single combined tickets file. The folder also holds the ticket's code and small results
- Tracker state is recorded in YAML front matter at the top of each file (fields below); its `status:` line also says who holds it
- Dates and times are UTC, from `date -u`
- Comments and conversation history append to the bottom of the file under a `## Log` heading
- `research-status` writes `STATUS.md`, the project page: the milestones (closed maps and their outcomes) and the open maps. Never edit it by hand; run it after opening, re-charting, pausing or closing a map. What is live (waiting on the user, running, the frontier) is printed, never stored: `research-status --now`. `research-status --check` reports what breaks these rules.

## When a skill says "publish to the issue tracker"

Create a new file under `maps/` (creating the directory if needed); for a new map, then run `research-status`.

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the ticket id (`T8-12`) directly.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** folder per ticket.

- **Map**: `maps/<id>-<slug>/map.md` (the Destination / Notes / Contract / Decisions-so-far / Fog / Out-of-scope body). Front matter: `id`, `title`, `status`, `outcome` (one line, once closed), `updated`. Status: `open`; `claimed (<session>, <time>)` while a session drives it; `paused (human, <date>: why)`; `closed`.
- **Child ticket**: `maps/<map>/tickets/NN-<slug>/ticket.md`, with the question in the body. Front matter: `id` (`<map id>-NN`), `title` (the question), `type` (`research`/`prototype`/`grilling`/`task`/`experiment`), `status`, `blocked_by`, `updated`; an experiment adds `cost_cap`, `jobs` and `verdict`. Status: `open`; `claimed (<session>, <time>)`; `running (since <time>)`, while its jobs outlive the session that launched them; `held (human, <date>: why)`; `resolved`; `parked`; `superseded`.
- **Blocking**: a `blocked_by: [T8-04, T8-07]` line. A ticket is unblocked when every ticket it lists is `resolved`, or `superseded` by a resolved one. Only a dated line from the human waives an edge.
- **Frontier**: `research-status --frontier`: open, unblocked tickets on maps that are neither paused nor closed; first by number wins.
- **Claim**: set `status: claimed (<session>, <time>)` and save before any work. A session holds one claim at a time. A claim with no Log activity for ~1.5 days may be taken over; say so in the Log.
- **Resolve**: append the answer under an `## Answer` heading, set `status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.
- **Hold a ticket, pause a map**: the human's call, written with their words: `status: held (human, <date>: why)` or `paused (human, <date>: why)`. Held tickets and paused maps leave the frontier; only the human lifts it.
- **Close a map**: when its destination is reached, or a measured answer says it can't be, append that final answer to Decisions so far, set `status: closed` and `outcome:` (the answer in one line, with its number), then run `research-status`. A closed map's outcome is a **milestone**: `STATUS.md` lists them all.
- **Rule out of scope**: `status: parked`, the answer "out of scope: why", and one line in the map's Out of scope.
- **Supersede**: `status: superseded`, `superseded_by: <ticket or map id>`, and a one-line reason under `## Answer`.
- **One writer per map**: the session in the map's `status: claimed (…)` writes `map.md`; with none, the session resolving a ticket does. A ticket's claimant writes only its ticket folder.
