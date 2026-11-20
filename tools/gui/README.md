# Research Desk

A desktop app over the research harness. herdr and Claude Code stay the runtime; the app is the control layer.

- `server.py` — the backend (`research-gui`): pure standard library, listens on 127.0.0.1. It reads maps and tickets
  through `../status.py`, herdr through its CLI, servers over one shared SSH connection (read-only), and Claude Code
  transcripts (`~/.claude/projects/*/<session>.jsonl`, `rg_chat.py`). Terminals are ptys over a WebSocket (`rg_term.py`).
- `web/` — the page (plain ES modules, no build; libraries vendored in `web/vendor/`).
- `app/` — the Electron shell: starts the backend in a herdr workspace called `research-desk` (so it inherits the
  terminal's file access and outlives the app), shows the page, adds the menu, dock badge and notifications.
  Build and install: `cd app && npm install && npm run pack` → `~/Applications/Research Desk.app`. Only `main.js` and
  `preload.js` are bundled; changes to `server.py` or `web/` need only a reload (⌘R) or a backend restart.

Notifications (`rg_notify.py`, Settings → Notifications or the bell in the sidebar): a monitor in the backend turns
state changes into events (a prompt, a reply, a loop gone quiet, a safeguard flag, a decision ticket, a result); each
kind goes to a Mac banner, a Mac sound and/or a Moshi push, set in `~/.config/research-gui/notify.json`. Pushes use the
Keychain item `moshi-push` (`security add-generic-password -a "$USER" -s moshi-push -w`), are bundled per 20 s and
capped per hour. A `--dry-run` backend records events but plays and pushes nothing.

Figures: an image in the file viewer has **Mark & ask**: circle or box what's wrong on a copy (numbered marks), add a
note, pick a session (the ticket's worker by default, else the desk); the copy goes where that session runs and the
session gets the original's path, the copy's and the note (`/api/figure-fix`). A ticket's **Trace** tab lists what
the sessions that worked it did (commands, edits, reads, web, messages, failures), each step opening the conversation
at that moment. Its sessions are those whose first prompt names the ticket's folder (`/research-work …`, as
team-worker starts them), found here and on each herdr machine by `rg_trace.py`, which runs there over ssh so only the
steps cross.

Projects: `~/.config/research-gui/projects.toml` (template `projects.example.toml`, also editable in Settings).
`research-gui` opens the app if installed; `--browser` uses a browser tab; `--serve` runs only the backend;
`--dry-run` makes Start buttons print their herdr commands instead.

Testing without touching live agents: `research-gui --serve --port 8799 --dry-run`, then drive the page offscreen with
`app/node_modules/.bin/electron app/shoot.js spec.json` (navigate, run JS, save screenshots). For a live test, point a
second backend at a scratch project with `--config` and start sessions there.

A session that can't open a browser (one in a container) sees the app through Settings → Pictures for review: Chrome,
headless with its own empty profile, saves a picture of each main screen in `tools/gui/.shots` (ignored by git), on
the person's click, or when the session touches `.shots/request` once the person ticked the box that allows it. The
screens are fixed in `server.py` (`shot_plan`); `status.json` there says what was saved and what failed.

Remote projects (`host = "<ssh alias>"` in a project block) are reached only through `host_call` in `server.py`: one call
at a time per host, only over the shared connection a person opened (`ssh -O check` first; the app never opens one, since
Engaging needs Duo), a hard deadline that kills the call's whole process group (a ProxyCommand hop included), and back-off
after a failure (30 s, then 1, 2, 4, 8, 15 min). Records sync every 5 minutes and when a project is opened; live sessions
are checked every 20 s only while a page or chat of that host is open. `tests/remote_calls_test.py` (run by
`scripts/check.py`) points the app at a host that never answers and fails if it ever floods it; it was written after
the app took down Engaging's login008 that way.

herdr machines (`herdr machine add`: a Docker container on this Mac, another computer) need no config: the app lists
every enabled saved machine and shows its sessions beside this Mac's, each in the project whose folder holds its cwd
(the same path there: a shared folder or a clone at the same place). Status, messages, keys, screens and btw go through
`herdr --machine`; conversations come over ssh to the machine's target, mirrored read-only (the last 2 MB at first,
then what was added). Same `host_call` rules, minus the shared-connection check; a look every 10 s (3 s while one of its
chats is open). A host in `~/.config/research-gui/remote-paused` gets no call by any name: an alias or a machine's
target that resolves to it (`ssh -G`) counts, and so do the GPU page and server file views.
