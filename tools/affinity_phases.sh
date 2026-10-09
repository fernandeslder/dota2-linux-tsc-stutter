#!/bin/sh
# Change the CPU affinity of a running process through timed phases (same session A/B), marking each phase.
# usage: tools/affinity_phases.sh <pid> <run-dir> <secs-per-phase> name=cpulist [name=cpulist ...]
set -eu
PID=$1; RD=$2; SECS=$3; shift 3
ROOT=$(cd "$(dirname "$0")/.." && pwd)
for ph in "$@"; do
  name=${ph%%=*}; mask=${ph#*=}
  taskset -a -cp "$mask" "$PID" >/dev/null
  "$ROOT/bin/stutter" collect mark "phase:$name" --run-dir "$RD" --detail "cpus=$mask" >/dev/null 2>&1 || true
  echo "$(date +%T) phase $name cpus=$mask"
  sleep "$SECS"
done
"$ROOT/bin/stutter" collect mark "phase:end" --run-dir "$RD" >/dev/null 2>&1 || true
