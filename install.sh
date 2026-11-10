#!/usr/bin/env bash
# Symlink every skill in ./skills/<group>/ into ~/.claude/skills (and ~/research-harness to this folder if missing). Safe to rerun; never overwrites a real directory.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.claude/skills"
AGENTS_DEST="$HOME/.agents/skills"   # Codex and other Agent Skills-compatible harnesses
# Every rule and skill refers to ~/research-harness; point it here when the harness lives elsewhere.
if [[ ! -e "$HOME/research-harness" ]]; then ln -s "$HERE" "$HOME/research-harness"; echo "linked  ~/research-harness -> $HERE"; fi
mkdir -p "$DEST" "$AGENTS_DEST"
# research-status, codex-run and the team commands (team-up, team-worker, team-watch) on PATH
mkdir -p "$HOME/.local/bin"; chmod +x "$HERE/tools/team-up.sh"; ln -sfn "$HERE/tools/team-up.sh" "$HOME/.local/bin/team-up"
chmod +x "$HERE/tools/status.py"; ln -sfn "$HERE/tools/status.py" "$HOME/.local/bin/research-status"
chmod +x "$HERE/tools/codex-run.sh"; ln -sfn "$HERE/tools/codex-run.sh" "$HOME/.local/bin/codex-run"
chmod +x "$HERE/tools/team-watch.py"; ln -sfn "$HERE/tools/team-watch.py" "$HOME/.local/bin/team-watch"
chmod +x "$HERE/tools/team-worker.py"; ln -sfn "$HERE/tools/team-worker.py" "$HOME/.local/bin/team-worker"
# Optional extras (extras/, README "Optional extras"): `trash`, a delete that can be undone, and the delete-guard hook.
# Off unless asked for (`install.sh --extras`); a trash link an earlier install made is kept pointing at the right file.
case "$(readlink "$HOME/.local/bin/trash" 2>/dev/null)" in "$HERE"/*|"$HOME/research-harness"/*) EXTRAS=1;; *) EXTRAS=0;; esac
if [[ "${1:-}" == "--extras" || $EXTRAS == 1 ]]; then
  chmod +x "$HERE/extras/trash.py" "$HERE/extras/delete-guard.py"; ln -sfn "$HERE/extras/trash.py" "$HOME/.local/bin/trash"
  echo "extras: trash on PATH (the delete-guard hook goes into ~/.claude/settings.json by hand: extras/delete-guard.py)"
fi
for t in "$HERE"/tools/local/*; do   # your own tools (tools/local/, gitignored), on PATH without their extension
  [[ -f "$t" ]] || continue; chmod +x "$t"; ln -sfn "$t" "$HOME/.local/bin/$(basename "${t%.*}")"
done
chmod +x "$HERE/tools/gui/server.py"; ln -sfn "$HERE/tools/gui/server.py" "$HOME/.local/bin/research-gui"
# drop links left by skills that were removed or renamed here
for d in "$DEST" "$AGENTS_DEST"; do for l in "$d"/*; do
  [[ -L "$l" && ! -e "$l" ]] || continue
  case "$(readlink "$l")" in "$HERE"/*|"$HOME/research-harness"/*) rm "$l"; echo "removed stale $(basename "$l")";; esac
done; done
chmod +x "$HERE"/skills/*/*/*.sh 2>/dev/null || true
for s in "$HERE"/skills/*/*/; do
  name="$(basename "$s")"
  target="$DEST/$name"
  if [[ -L "$target" ]]; then ln -sfn "${s%/}" "$target"; echo "updated $name"
  elif [[ -e "$target" ]]; then echo "SKIP $name: $target exists and is not a symlink"
  else ln -s "${s%/}" "$target"; echo "linked  $name"
  fi
done
for s in "$HERE"/skills/*/*/; do
  name="$(basename "$s")"
  target="$AGENTS_DEST/$name"
  if [[ -L "$target" ]]; then ln -sfn "${s%/}" "$target"; echo "updated $name (codex)"
  elif [[ -e "$target" ]]; then echo "SKIP $name: $target exists and is not a symlink"
  else ln -s "${s%/}" "$target"; echo "linked  $name (codex)"
  fi
done
