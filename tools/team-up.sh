#!/usr/bin/env bash
# team-up <map, e.g. T8>
# Run inside herdr from the project folder. Adds tabs A desk, B driver and watch to the current workspace; each agent tab
# is a Claude Code session started with its /team command (TEAM-PROTOCOL.md). The driver's implementers are its own
# subagents, so they get no tabs. Extra claude flags: CLAUDE_ARGS.
set -euo pipefail
[[ "${HERDR_ENV:-}" == 1 ]] || { echo "run team-up inside herdr"; exit 1; }
T="${1:?usage: team-up <map, e.g. T8>}"
if [[ ! -d "$T" ]]; then for d in maps/"$T"-* tracks/"$T"-*; do [[ -d "$d" ]] && { T="$d"; break; }; done; fi
[[ -f "$T/map.md" || -f "$T/track.md" ]] || { echo "no map '$1' in $PWD/maps"; exit 1; }
P="$(basename "$PWD" | tr 'A-Z' 'a-z' | tr -c 'a-z0-9\n' '-' | cut -c1-20)"   # agent-name prefix

tab() {  # tab <label> -> pane id of a new tab in this workspace
  herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "$PWD" --label "$1" --no-focus |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["root_pane"]["pane_id"])'
}
go() {  # go <agent name> <pane> <prompt>
  herdr agent start "$1" --kind claude --pane "$2" --timeout 120000 ${CLAUDE_ARGS:+-- $CLAUDE_ARGS} >/dev/null
  herdr agent prompt "$1" "$3" >/dev/null
}

A="$(tab "A desk")"; B="$(tab "B driver $(basename "$T" | cut -d- -f1)")"; W="$(tab watch)"
go "$P-driver" "$B" "/team driver $T"
sleep 20   # the driver joins the roster first, so the desk finds it
go "$P-desk" "$A" "/team desk"
KEEP=$(command -v caffeinate >/dev/null && echo "caffeinate -dimsu ")   # macOS: keep the machine awake while the driver runs
herdr pane run "$W" "${KEEP}tail -n 40 -F scratch/agents/driver.log" >/dev/null
echo "team up for $T: talk to tab 'A desk'"
