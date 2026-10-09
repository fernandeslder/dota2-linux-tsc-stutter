#!/bin/sh
# Flip a sysctl through timed phases in a running session (same-session A/B), marking each phase; ALWAYS restores the original.
# usage: tools/sysctl_phases.sh <run-dir> <secs-per-phase> <sysctl.key> name=value [name=value ...]
set -eu
RD=$1; SECS=$2; KEY=$3; shift 3
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ORIG=$(sysctl -n "$KEY")
trap 'sudo sysctl -w "$KEY=$ORIG" >/dev/null; echo "restored $KEY=$ORIG"' EXIT INT TERM
for ph in "$@"; do
  name=${ph%%=*}; val=${ph#*=}
  sudo sysctl -w "$KEY=$val" >/dev/null
  "$ROOT/bin/stutter" collect mark "phase:$name" --run-dir "$RD" --detail "$KEY=$val" >/dev/null 2>&1 || true
  echo "$(date +%T) phase $name $KEY=$val"
  sleep "$SECS"
done
"$ROOT/bin/stutter" collect mark "phase:end" --run-dir "$RD" >/dev/null 2>&1 || true
