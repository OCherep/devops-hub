#!/usr/bin/env bash
# Usage: down.sh [module_id ...]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

stop_one() {
  local id="$1"
  local dir="$ROOT/$id"
  [[ -f "$dir/docker-compose.yml" ]] || return 0
  echo "==> down $id"
  (cd "$dir" && docker compose down) || true
}

if [[ $# -gt 0 ]]; then
  for id in "$@"; do stop_one "$id"; done
  exit 0
fi

# edge first, then others
stop_one edge
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  IFS='|' read -r id _ <<<"$line"
  id="$(echo "$id" | xargs)"
  [[ "$id" == "edge" ]] && continue
  stop_one "$id"
done < "$ROOT/modules.env"
