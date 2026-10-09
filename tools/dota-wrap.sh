#!/bin/sh
# Steam launch-option wrapper:  <env...> /path/tools/dota-wrap.sh %command% <base game args>
# Reads runs/mangohud-live/condition.env (POSIX sh; may `export` vars and set DOTA_ADD / DOTA_REMOVE) so an A/B
# condition can change without restarting Steam or editing localconfig.vdf.
#   DOTA_ADD="-foo bar"      extra args appended to the game command line
#   DOTA_REMOVE="-threads 8" tokens (space separated, exact match) removed from the args; "-threads 8" removes both
#   DOTA_PREFIX="taskset -c 0-7"   command prefix placed before the game command
ROOT=$(cd "$(dirname "$0")/.." && pwd)
COND=${DOTA_CONDITION_FILE:-$ROOT/runs/mangohud-live/condition.env}
LOG=$ROOT/runs/mangohud-live/wrap.log
DOTA_ADD=; DOTA_REMOVE=; DOTA_PREFIX=
# NOTE: $COND is SOURCED AS SHELL code (it runs with this script's privileges), not parsed as data. Keep it (and its
# directory) writable only by you; do not point DOTA_CONDITION_FILE at a file other users can modify.
[ -f "$COND" ] && . "$COND"
# rebuild argv without removed tokens
n=$#; i=0
set -- "$@" "__END__"
while [ "$1" != "__END__" ]; do
  skip=0
  for r in $DOTA_REMOVE; do [ "$1" = "$r" ] && skip=1; done
  [ $skip -eq 0 ] && set -- "$@" "$1"
  shift
done
shift
for a in $DOTA_ADD; do set -- "$@" "$a"; done
{ echo "== $(date +%s.%N) condition=$(cat "$COND" 2>/dev/null | tr '\n' ';')"; echo "prefix=[$DOTA_PREFIX] argv=$*"; } >> "$LOG"
# shellcheck disable=SC2086
exec $DOTA_PREFIX "$@"
