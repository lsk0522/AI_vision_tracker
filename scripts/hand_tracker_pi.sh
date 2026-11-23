#!/usr/bin/env bash
# 이전 명령 호환용 — 이제 aivt 가 모두 담당합니다 (scripts/aivt.py).
#   deploy → aivt sync,  run/calibrate/preview → 같은 이름
cmd="${1:-}"; shift || true
[ "$cmd" = "deploy" ] && cmd="sync"
[ "$cmd" = "where" ] && cmd="status"
exec python3 "$(dirname "$0")/aivt.py" $cmd "$@"
