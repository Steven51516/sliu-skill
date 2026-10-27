#!/usr/bin/env bash
# Scaffold a new research project. Usage: init.sh <name> ["one-line direction"]
# Settings (env vars; research-init chooses them with the user):
#   SCOPE_FILE       path of the scope file (scopes/README.md); imported by CLAUDE.md, named in AGENTS.md
#   SCOPE_INHERITED  path of a parent CLAUDE.md that already imports the scope: CLAUDE.md then does not import it again
#   PROJECTS_ROOT    where the project folder goes (default ~/projects)
#   POOL_ROOT, SCRATCH_ROOT  storage roots; without them artifacts/ and scratch/ are plain folders (gitignored)
#   CODE_LOCATION    where the code lives, e.g. "node-16:~/code/<name>" (default: this folder)
#   GIT              1 (default) runs git init; 0 skips it
#   TRACKER          issue tracker: local (default), github or gitlab; written to docs/agents/issue-tracker.md
set -euo pipefail

NAME="${1:?usage: init.sh <name> [direction]}"
DIRECTION="${2:-Direction: TBD}"
HARNESS="${HARNESS:-$HOME/research-harness}"
PROJECTS_ROOT="${PROJECTS_ROOT:-$HOME/projects}"
POOL_ROOT="${POOL_ROOT:-}"
SCRATCH_ROOT="${SCRATCH_ROOT:-}"
SCOPE_FILE="${SCOPE_FILE:-}"
SCOPE_INHERITED="${SCOPE_INHERITED:-}"
CODE_LOCATION="${CODE_LOCATION:-this folder}"
GIT="${GIT:-1}"
TRACKER="${TRACKER:-local}"
DATE="$(date +%F)"
DIR="$PROJECTS_ROOT/$NAME"

[[ "$NAME" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "name must be [A-Za-z0-9._-]"; exit 1; }
[[ -e "$DIR" ]] && { echo "exists: $DIR (adopt it with research-init instead of init.sh)"; exit 1; }
[[ -f "$HARNESS/skills/research-init/issue-tracker-$TRACKER.md" ]] || { echo "unknown TRACKER: $TRACKER (local, github or gitlab)"; exit 1; }

mkdir -p "$DIR"/{common,logs,docs/agents,resources/{papers,prior-work,other,repos}}
[[ "$TRACKER" == local ]] && mkdir -p "$DIR/maps"
link_or_dir() {  # link_or_dir <root> <name in project>
  if [[ -n "$1" ]]; then mkdir -p "$1/$NAME" && ln -s "$1/$NAME" "$DIR/$2"; else mkdir -p "$DIR/$2"; fi
}
link_or_dir "$POOL_ROOT" artifacts
link_or_dir "$SCRATCH_ROOT" scratch

if [[ -n "$SCOPE_INHERITED" ]]; then SCOPE_IMPORT="<!-- Scope: loaded by the parent $SCOPE_INHERITED; not imported again here. -->"
elif [[ -n "$SCOPE_FILE" ]]; then SCOPE_IMPORT="<!-- Scope: where this project runs. See ~/research-harness/scopes/README.md. -->
@$SCOPE_FILE"
else SCOPE_IMPORT="<!-- TODO: import this project's scope file here, e.g. @~/research-harness/scopes/engaging.md -->"; fi
SCOPE_PATH="${SCOPE_FILE:-TODO: name the scope file}"

esc() { printf '%s' "$1" | sed -e 's/[\\&|]/\\&/g' | awk 'BEGIN{ORS="\\n"} {print}' | sed -e 's/\\n$//'; }
render() {  # render <template> <dest>
  sed -e "s|{{NAME}}|$NAME|g" -e "s|{{DATE}}|$DATE|g" \
      -e "s|{{DIRECTION}}|$(esc "$DIRECTION")|g" -e "s|{{SCOPE_IMPORT}}|$(esc "$SCOPE_IMPORT")|g" \
      -e "s|{{SCOPE_PATH}}|$(esc "$SCOPE_PATH")|g" -e "s|{{CODE_LOCATION}}|$(esc "$CODE_LOCATION")|g" \
      "$HARNESS/templates/$1" > "$2"
}
render AGENTS.md    "$DIR/AGENTS.md"
render CLAUDE.md    "$DIR/CLAUDE.md"
render ../skills/research-init/delegation.md "$DIR/docs/agents/delegation.md"
render "../skills/research-init/issue-tracker-$TRACKER.md" "$DIR/docs/agents/issue-tracker.md"
render ../skills/research-init/domain.md "$DIR/docs/agents/domain.md"
render STATUS.md    "$DIR/STATUS.md"
render decisions.md "$DIR/docs/decisions.md"
render OVERVIEW.md  "$DIR/OVERVIEW.md"
for f in BRIEF.md LINKS.md README.md INTAKE.md; do render "resources/$f" "$DIR/resources/$f"; done
touch "$DIR"/resources/{papers,prior-work,other}/.gitkeep
cp "$HARNESS/templates/gitignore" "$DIR/.gitignore"

[[ "$GIT" == "1" ]] && git -C "$DIR" init -q
echo "created $DIR (issue tracker: $TRACKER)"
