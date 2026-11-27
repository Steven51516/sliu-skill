#!/usr/bin/env bash
# codex-run <run dir>             start Codex on <run dir>/brief.md
# codex-run <run dir> --resume    send <run dir>/followup.md to the same Codex session
# Run from the project folder. Model and effort: CODEX_MODEL (default gpt-6-astra), CODEX_EFFORT (default xhigh).
# Every call, resumes included, gets the model, effort and sandbox (a bare resume drops them), and runs without the
# tokens and keys in this environment. The header Codex printed is checked, so a wrong model, effort or sandbox fails loudly,
# and so does a run that ends without a final message or with a non-zero exit.
# A new brief starts with a fixed preamble that keeps Codex to the task (prompting rules from openai/codex-plugin-cc).
# Codex works in the project folder, so a file it names without a path lands there (7 times in 5 days, 10-30..11-03):
# after every call, a file new in the project folder that the run's log names is moved into the run dir, and said so.
set -euo pipefail
D="${1:?usage: codex-run <run dir> [--resume]}"; MODE="${2:-}"
[[ -d "$D" ]] || { echo "codex-run: no run dir $D"; exit 1; }
ABS_D="$(cd "$D" && pwd)"; D="$ABS_D"   # every path below is absolute: a relative run dir (even ".") works
M="${CODEX_MODEL:-gpt-6-astra}"; E="${CODEX_EFFORT:-xhigh}"
PREAMBLE="Do only the task below, tightly scoped; no unrelated refactors. No hashes, manifests, receipts or checks beyond
what done lists. Read the files the brief names and what the task needs, not other agents' logs, memory or chat history.
Never open network listeners; stop only processes you started. If a missing detail changes correctness or safety, stop and
ask; otherwise take the reasonable reading and keep going. Your working directory is the project folder: write every file
you create into $ABS_D unless the brief names another place."
STRIP=$(env | cut -d= -f1 | grep -E 'TOKEN|KEY|SECRET|PASSWORD|AUTH' | sed 's/^/-u /' || true)
SET=(--skip-git-repo-check -m "$M" -c "model_reasoning_effort=\"$E\""
     -c 'sandbox_mode="workspace-write"' -c sandbox_workspace_write.network_access=true -o "$D/last.md")
RC=0
BEFORE="$(ls -A "$PWD")"
tidy() {  # move files Codex wrote into the project folder (new since the start, named in its log) into the run dir
  local f to moved=""
  [[ "$PWD" -ef "$ABS_D" ]] && return 0   # run from inside the run dir: its files are already where they belong
  while IFS= read -r f; do
    [[ -f "$PWD/$f" ]] || continue
    printf '%s\n' "$BEFORE" | grep -qxF -- "$f" && continue
    grep -qF -- "$f" "$LOG" || continue
    to="$ABS_D/$f"; [[ -e "$to" ]] && to="$ABS_D/$f.from-project-folder"
    mv -- "$PWD/$f" "$to" && moved="$moved $f"
  done < <(ls -A "$PWD")
  [[ -z "$moved" ]] || echo "codex-run: moved$moved, which Codex wrote in $PWD, into $ABS_D"
}
if [[ "$MODE" == --resume ]]; then
  ID=$(grep -m1 '^session id:' "$D/codex.log" | awk '{print $3}')
  [[ -n "$ID" && -f "$D/followup.md" ]] || { echo "codex-run: need a session id in $D/codex.log and $D/followup.md"; exit 1; }
  LOG="$D/codex.resume.log"
  env $STRIP codex exec resume "$ID" "${SET[@]}" - < "$D/followup.md" > "$LOG" 2>&1 || RC=$?
else
  [[ -f "$D/brief.md" ]] || { echo "codex-run: no $D/brief.md"; exit 1; }
  LOG="$D/codex.log"
  { echo "$PREAMBLE"; echo; cat "$D/brief.md"; } |
    env $STRIP codex exec -C "$PWD" "${SET[@]}" - > "$LOG" 2>&1 || RC=$?
fi
tidy
# Codex answered but could not run anything (seen in a container: no code-mode host, no sandbox namespace): not "done"
# The same words quoted from a file Codex read are not a failure: it counts only when no tool call succeeded.
if grep -qE "failed to spawn code-mode host|codex-code-mode-host missing|bwrap: No permissions to create a new namespace" "$LOG" \
   && ! grep -q "^ succeeded in " "$LOG"; then
  echo "codex-run: Codex could not start its tools on this machine (see $LOG); run it on a host where Codex works"; exit 1
fi
grep -q "^model: $M" "$LOG" || { echo "codex-run: model is not $M in $LOG"; exit 1; }
grep -q "^reasoning effort: $E" "$LOG" || { echo "codex-run: effort is not $E in $LOG"; exit 1; }
[[ -s "$D/last.md" ]] || { echo "codex-run: no final message (see the end of $LOG, e.g. model at capacity)"; exit 1; }
[[ $RC == 0 ]] || { echo "codex-run: codex exited $RC (see $LOG)"; exit "$RC"; }
grep -q "^sandbox: workspace-write" "$LOG" || { echo "codex-run: sandbox is not workspace-write in $LOG"; exit 1; }
echo "codex-run: done ($LOG; final message in $D/last.md, report in $D/report.md if the brief asked for one)"
