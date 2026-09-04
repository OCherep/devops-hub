#!/usr/bin/env bash
# Usage: up.sh [module_id ...]
# Without args: start network + all modules listed in modules.env (except comments).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

"$ROOT/network.sh"

port_in_use() {
  local p="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -lnt | grep -qE ":${p}\\s"
  else
    return 1
  fi
}

who_on_port() {
  local p="$1"
  docker ps --format '{{.Names}}\t{{.Ports}}' 2>/dev/null | grep -E ":${p}->|:${p}\\b" || true
  ss -lntp 2>/dev/null | grep -E ":${p}\\s" || true
}

start_one() {
  local id="$1"
  local dir="$ROOT/$id"
  if [[ ! -d "$dir" ]]; then
    echo "SKIP $id — no directory $dir"
    return 0
  fi
  local compose="docker-compose.yml"
  if [[ ! -f "$dir/$compose" ]]; then
    echo "SKIP $id — no $compose"
    return 0
  fi

  # Edge needs host :80 and :443 free of other containers
  if [[ "$id" == "edge" ]]; then
    if port_in_use 80; then
      echo "ERROR: host port 80 is already in use — edge (Caddy) cannot bind."
      echo "       OnCall must NOT publish 80:80 (only 85:443). Free :80 first:"
      who_on_port 80
      echo "       Hint: docker ps | grep 80  &&  docker stop <old_nginx>"
      return 1
    fi
  fi

  echo "==> up $id"
  (cd "$dir" && docker compose -f "$compose" up -d --remove-orphans)
}

if [[ $# -gt 0 ]]; then
  for id in "$@"; do
    start_one "$id"
  done
  exit 0
fi

# Ordered defaults: edge last so backends exist
ORDER=(hub radar oncall edge)
declared=()
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  IFS='|' read -r id _ <<<"$line"
  id="$(echo "$id" | xargs)"
  declared+=("$id")
done < "$ROOT/modules.env"

started=()
for id in "${ORDER[@]}"; do
  start_one "$id"
  started+=("$id")
done

for id in "${declared[@]}"; do
  skip=0
  for s in "${started[@]}"; do [[ "$s" == "$id" ]] && skip=1 && break; done
  [[ $skip -eq 1 ]] && continue
  start_one "$id"
done

echo "==> done"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | head -40
