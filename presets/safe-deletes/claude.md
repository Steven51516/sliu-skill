- Deletes: move a path with `trash <path>` instead of deleting it (undo with `trash --restore <path>`; over ssh call it as
  `~/.local/bin/trash` where it is installed). A trash move needs no ask. Never ask the human to delete something or to
  empty the trash.
- A recursive delete meets the `delete-guard` hook: it asks the human and, unanswered for 15 min, is declined; then use `trash`.
