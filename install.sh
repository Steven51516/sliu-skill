#!/usr/bin/env bash
# Symlink every skill in ./skills/<group>/ into ~/.claude/skills (and ~/research-harness to this folder if missing). Safe to rerun; never overwrites a real directory.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.claude/skills"
AGENTS_DEST="$HOME/.agents/skills"   # Codex and other Agent Skills-compatible harnesses
# Every rule and skill refers to ~/research-harness; point it here when the harness lives elsewhere.
if [[ ! -e "$HOME/research-harness" ]]; then ln -s "$HERE" "$HOME/research-harness"; echo "linked  ~/research-harness -> $HERE"; fi
mkdir -p "$DEST" "$AGENTS_DEST"
# team-up (start a team in herdr), research-status and research-migrate as commands on PATH
mkdir -p "$HOME/.local/bin"; chmod +x "$HERE/tools/team-up.sh"; ln -sfn "$HERE/tools/team-up.sh" "$HOME/.local/bin/team-up"
chmod +x "$HERE/tools/status.py"; ln -sfn "$HERE/tools/status.py" "$HOME/.local/bin/research-status"
chmod +x "$HERE/tools/migrate_to_maps.py"; ln -sfn "$HERE/tools/migrate_to_maps.py" "$HOME/.local/bin/research-migrate"
chmod +x "$HERE/tools/codex-run.sh"; ln -sfn "$HERE/tools/codex-run.sh" "$HOME/.local/bin/codex-run"
chmod +x "$HERE/tools/team-watch.py"; ln -sfn "$HERE/tools/team-watch.py" "$HOME/.local/bin/team-watch"
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
