#!/bin/sh
# Start one live Dota trial: wrapper in background (waits for go-file), then launch Dota via Steam.
# usage: tools/live_start.sh <label> <minutes> [extra stutter-trial args...]
# The orchestrator then drives the GUI to a live spectated match and runs: touch $GO
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
LABEL=$1; MIN=$2; shift 2
# LABEL is used in paths (incl. rm -rf below): only [A-Za-z0-9._-], no slashes, must not start with a dot
case "$LABEL" in
  ''|.*|*[!A-Za-z0-9._-]*) echo "invalid label '$LABEL': use only letters, digits, '.', '_', '-' and do not start with '.'" >&2; exit 2 ;;
esac
G=${STUTTER_SCRATCH:-/tmp/stutter-live}; mkdir -p "$G"
GO=$G/go-$LABEL; LOG=$G/trial-$LABEL.log
rm -f "$GO"
pkill -9 -x dota2 2>/dev/null || true
rm -rf "runs/live-$LABEL"
PYTHONUNBUFFERED=1 nohup bin/stutter trial run --run-dir "runs/live-$LABEL" --label "$LABEL" --minutes "$MIN" \
  --warmup 20 --quiesce --profile full --mangohud-link "$ROOT/runs/mangohud-live/current" --go-file "$GO" "$@" \
  > "$LOG" 2>&1 &
i=0; until grep -q "MangoHud output link" "$LOG" 2>/dev/null || [ $i -ge 60 ]; do sleep 1; i=$((i+1)); done
cat "$LOG"
setsid nohup steam -applaunch 570 >/dev/null 2>&1 &
echo "GO=$GO LOG=$LOG"
