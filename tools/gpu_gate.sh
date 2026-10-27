#!/bin/bash
# Keep a project's GPU jobs to at most MAXGPU running at once (e.g. to leave a GPU free for another session).
# Slurm scopes only (see scopes/engaging.md). Jobs are matched by name prefix (PREFIX, e.g. "T3" or "N018"); submit them with `sbatch --hold` and this releases
# them as slots free, PRIORITY_RE-matching names first, then oldest job id. Pending jobs that slip through unheld are
# held when over budget. Login-node safe: one squeue per cycle, no compute. Stops at GATE_UNTIL (epoch s).
# Usage: PREFIX=T3 MAXGPU=3 [PRIORITY_RE='^T3-(05|07)'] [GATE_UNTIL=...] bash gpu_gate.sh >> gate.log 2>&1
# Stop it by PID (`kill <pid>`), never with `pkill -f` on a pattern that also matches your own shell.
PREFIX=${PREFIX:?set PREFIX (job-name prefix)}
MAXGPU=${MAXGPU:-3}
GATE_UNTIL=${GATE_UNTIL:-$(date -d 'tomorrow 10:00' +%s)}
PARTS=${PARTS:-mit_preemptable|mit_normal_gpu}
while [ "$(date +%s)" -lt "$GATE_UNTIL" ]; do
  mapfile -t rows < <(squeue --me -h -r -o "%i|%j|%T|%P|%r" | grep "|$PREFIX" | grep -E "\|($PARTS)\|")
  running=0; pend=(); held=()
  for r in "${rows[@]}"; do
    IFS='|' read -r id name st part reason <<< "$r"
    if [ "$st" = RUNNING ] || [ "$st" = CONFIGURING ] || [ "$st" = COMPLETING ]; then running=$((running+1))
    elif [ "$st" = PENDING ]; then
      if [[ "$reason" == *eld* ]]; then held+=("$id"); elif [ "$reason" != Dependency ]; then pend+=("$id"); fi
    fi
  done
  free=$((MAXGPU - running)); n=0
  for id in "${pend[@]}"; do
    n=$((n+1)); if [ $n -gt $free ]; then scontrol hold "$id" 2>/dev/null && echo "$(date +%H:%M) hold $id (running=$running)"; fi
  done
  slots=$((free - ${#pend[@]})); [ $slots -lt 0 ] && slots=0
  order=$(for id in "${held[@]}"; do nm=$(squeue -h -j "$id" -o %j 2>/dev/null | head -1); p=1
          [[ -n "${PRIORITY_RE:-}" && "$nm" =~ $PRIORITY_RE ]] && p=0; echo "$p $id"; done | sort -k1,1n -k2,2 | awk '{print $2}')
  for id in $(printf '%s\n' $order | head -n "$slots"); do
    scontrol release "$id" 2>/dev/null && echo "$(date +%H:%M) release $id (running=$running)"
  done
  sleep 120
done
echo "gate stopped $(date)"
