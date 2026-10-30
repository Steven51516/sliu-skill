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

Projects: `~/.config/research-gui/projects.toml` (template `projects.example.toml`, also editable in Settings).
`research-gui` opens the app if installed; `--browser` uses a browser tab; `--serve` runs only the backend;
`--dry-run` makes Start buttons print their herdr commands instead.

Testing without touching live agents: `research-gui --serve --port 8799 --dry-run`, then drive the page offscreen with
`app/node_modules/.bin/electron app/shoot.js spec.json` (navigate, run JS, save screenshots). For a live test, point a
second backend at a scratch project with `--config` and start sessions there.
