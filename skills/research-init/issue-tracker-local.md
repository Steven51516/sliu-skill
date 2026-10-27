# Issue tracker: Local Markdown

Maps and tickets for this project live as markdown files in `maps/`.

## Conventions

- One map per destination: `maps/<id>-<slug>/map.md`, with `id` counting up (`T1`, `T2`, …) and never reused
- One folder per ticket: `maps/<map>/tickets/<NN>-<slug>/ticket.md`, numbered from `01`, never a single combined tickets file. The folder also holds the ticket's code and small results
- Tracker state is recorded in YAML front matter at the top of each file (fields below)
- Comments and conversation history append to the bottom of the file under a `## Log` heading
- `research-status` writes `STATUS.md`, a generated view: the milestones, the open maps, what waits on the user, what is running and the frontier. Never edit it by hand; every operation below that writes a map or ticket ends by running it. `research-status --check` reports a resolved ticket missing from its map, unknown blockers and stale claims

## When a skill says "publish to the issue tracker"

Create a new file under `maps/` (creating the directory if needed), then run `research-status`.

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the ticket id (`T8-12`) directly.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** folder per ticket.

- **Map**: `maps/<id>-<slug>/map.md` (the Destination / Notes / Contract / Decisions-so-far / Fog / Out-of-scope body). Front matter: `id`, `title`, `status` (`open`/`closed`), `claimed` (the session driving the whole map, or `null`), `updated`.
- **Child ticket**: `maps/<map>/tickets/NN-<slug>/ticket.md`, with the question in the body. Front matter: `id` (`<map id>-NN`), `title` (the question), `type` (`research`/`prototype`/`grilling`/`task`/`experiment`), `status` (`open`/`claimed`/`running`/`resolved`/`parked`/`superseded`), `claimed`, `blocked_by`, `updated`; an experiment adds `cost_cap`, `jobs` and `verdict`.
- **Blocking**: a `blocked_by: [T8-04, T8-07]` line. A ticket is unblocked when every ticket it lists is `resolved`, `parked` or `superseded`.
- **Frontier**: `research-status --frontier` (open, unblocked, unclaimed); first by number wins.
- **Claim**: set `claimed: "<session> YYYY-MM-DD HH:MM"` and `status: claimed`, and save before any work, then run `research-status`. A claim with no Log activity for ~1.5 days may be taken over; say so in the Log.
- **Resolve**: append the answer under an `## Answer` heading, set `status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`, and run `research-status`.
- **Milestone**: a Decisions-so-far line whose answer changes the project's route gets the tag `[milestone]` (e.g. a phase closed negative, an arm that becomes the reference). `STATUS.md` lists every such line, open and closed maps alike. A dead end that changes nothing is not one.
- **Close a map**: when its destination is reached, or a measured answer says it can't be, append that final answer to Decisions so far and set `status: closed`, then run `research-status`.
- **Rule out of scope**: `status: parked`, the answer "out of scope: why", and one line in the map's Out of scope.
- **Supersede**: `status: superseded`, `superseded_by: <id>`, and a one-line reason under `## Answer`.
- **One writer per map**: the session in the map's `claimed` writes `map.md`; with none, the session resolving a ticket does. A ticket's claimant writes only its ticket folder.
