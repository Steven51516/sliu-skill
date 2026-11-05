#!/usr/bin/env bash
# team-up [--codex] [--driver] <map, e.g. T8>
# Run inside herdr from the project folder. Adds tabs A desk, B driver and watch to the current workspace; each agent tab
# starts its team role (TEAM-PROTOCOL.md). Worker tabs open and close as the driver starts and finishes tickets, on the
# driver's own agent. Claude Code (default): sessions start logged in (Keychain item claude-code-oauth) and on an explicit
# model and effort (TEAM_MODEL, default claude-opus-5-5; TEAM_EFFORT, default xhigh), so a /model or /effort saved
# elsewhere cannot change them. Extra claude flags: CLAUDE_ARGS.
# --codex: every session is Codex, with the flags in codex-team.args at medium effort (workers: xhigh); the watch tab
# is the driver's schedule, since Codex has no /loop.
set -euo pipefail
[[ "${HERDR_ENV:-}" == 1 ]] || { echo "run team-up inside herdr"; exit 1; }
AGENT=claude; ONLY_DRIVER=0   # --driver: only a driver tab for one more map, for a team already running
while [[ "${1:-}" == --* ]]; do case "$1" in --codex) AGENT=codex;; --driver) ONLY_DRIVER=1;; *) echo "unknown option $1"; exit 1;; esac; shift; done
T="${1:?usage: team-up [--codex] [--driver] <map, e.g. T8>}"
if [[ ! -d "$T" ]]; then for d in maps/"$T"-* tracks/"$T"-*; do [[ -d "$d" ]] && { T="$d"; break; }; done; fi
[[ -f "$T/map.md" || -f "$T/track.md" ]] || { echo "no map '$1' in $PWD/maps"; exit 1; }
P="$(basename "$PWD" | tr 'A-Z' 'a-z' | tr -c 'a-z0-9\n' '-' | cut -c1-20)"   # agent-name prefix
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

TOK=""; CODEX=()
if [[ $AGENT == claude ]]; then
  TOK=$(security find-generic-password -a "$USER" -s claude-code-oauth -w 2>/dev/null || true)   # login for new tabs
else
  while IFS= read -r l; do [[ -z "$l" || "$l" == \#* ]] || CODEX+=("${l/#\~/$HOME}"); done < "$HERE/codex-team.args"
fi
tab() {  # tab <label> -> pane id of a new tab in this workspace
  herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "$PWD" --label "$1" --no-focus ${TOK:+--env "CLAUDE_CODE_OAUTH_TOKEN=$TOK"} |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["root_pane"]["pane_id"])'
}
go() {  # go <agent name> <pane> <team role, e.g. "driver maps/T8-x">
  if [[ $AGENT == codex ]]; then
    herdr agent start "$1" --kind codex --pane "$2" --timeout 120000 -- "${CODEX[@]}" -c 'model_reasoning_effort="medium"' >/dev/null
    herdr agent prompt "$1" "Read ~/.agents/skills/team/SKILL.md and follow it as \`team $3\`." >/dev/null
  else
    herdr agent start "$1" --kind claude --pane "$2" --timeout 120000 -- --model "${TEAM_MODEL:-claude-opus-5-5}" --effort "${TEAM_EFFORT:-xhigh}" ${CLAUDE_ARGS:-} >/dev/null
    herdr agent prompt "$1" "/team $3" >/dev/null
  fi
}

ID="$(basename "$T" | cut -d- -f1)"
if [[ $ONLY_DRIVER == 1 ]]; then   # same pinned model and effort as a full team-up; only a team-watch run with no arguments (it reads the roster) watches it
  B="$(tab "B driver $ID")"; go "$P-driver-$(echo "$ID" | tr A-Z a-z)" "$B" "driver $T"
  echo "driver for $T ($AGENT) in $B"; exit 0
fi
A="$(tab "A desk")"; B="$(tab "B driver $ID")"; W="$(tab watch)"
go "$P-driver" "$B" "driver $T"
sleep 20   # the driver joins the roster first, so the desk finds it
go "$P-desk" "$A" "desk"
KEEP=$(command -v caffeinate >/dev/null && echo "caffeinate -dimsu ")   # macOS: keep the machine awake while the driver runs
herdr pane run "$W" "${KEEP}team-watch $T $B $P-driver" >/dev/null   # driver log; restarts a stuck Claude driver, ticks a Codex one
echo "team up for $T ($AGENT): talk to tab 'A desk'"
