#!/bin/bash
# /opt/ops/hub/ops/deploy.sh — pull + up усіх модулів + місце на диску
set -euo pipefail
chmod +x "$0" 2>/dev/null || true
find "${OPS_ROOT:-/opt/ops}/hub/ops" -name "*.sh" -exec chmod +x {} + 2>/dev/null || true
OPS="${OPS_ROOT:-/opt/ops}"
echo "== disk =="
df -h / /var /opt 2>/dev/null | awk 'NR==1 || /\/$|\/var|\/opt/'
echo
docker system df 2>/dev/null || true

pull() {
  local dir="$1" rem="$2" br="$3"
  if [ ! -d "$dir/.git" ]; then
    echo "skip $dir (no git)"
    return
  fi
  echo "== pull $dir ($br) =="
  git -C "$dir" stash push -u -m "deploy-auto $(date +%H%M)" --quiet || true
  git -C "$dir" fetch origin "$br" --quiet
  git -C "$dir" pull --ff-only origin "$br" || echo "WARN pull $dir"
}

up() {
  local dir="$1"
  [ -f "$dir/docker-compose.yml" ] || return 0
  echo "== compose $dir =="
  (cd "$dir" && docker compose up -d --remove-orphans)
}

/opt/ops/network.sh 2>/dev/null || docker network create opsnet 2>/dev/null || true

pull "$OPS/hub"    origin main
pull "$OPS/radar"  origin grok-0.0.1
# never lose OnCall secrets
if [ -f "$OPS/oncall/.env" ]; then
  cp -a "$OPS/oncall/.env" /tmp/oncall.env.bak
  echo "preserved $OPS/oncall/.env"
fi
pull "$OPS/oncall" origin grok-1.0.0
if [ -f /tmp/oncall.env.bak ]; then
  cp -a /tmp/oncall.env.bak "$OPS/oncall/.env"
  echo "restored $OPS/oncall/.env"
fi
# preserve oncall .env

# sync edge/certs/postgres from hub tree
mkdir -p "$OPS/edge" "$OPS/certs/ui" "$OPS/postgres"
cp -a "$OPS/hub/ops/edge/." "$OPS/edge/" 2>/dev/null || true
cp -a "$OPS/hub/ops/certs/docker-compose.yml" "$OPS/certs/" 2>/dev/null || true
cp -a "$OPS/hub/ops/certs/nginx.conf" "$OPS/certs/" 2>/dev/null || true
cp -a "$OPS/hub/ops/certs/ui/index.html" "$OPS/certs/ui/" 2>/dev/null || true
if [ -f "$OPS/certs/ui/status.json" ]; then
  cp -f "$OPS/certs/ui/status.json" "$OPS/certs/ui/inventory.json"
  chmod 644 "$OPS/certs/ui/"*.json 2>/dev/null || true
fi

up "$OPS/postgres"
up "$OPS/hub"
up "$OPS/radar"
up "$OPS/certs"
up "$OPS/oncall"
up "$OPS/edge"

echo "== health (internal, no public hairpin) =="
docker exec ops_edge wget -qO- -T 3 http://oncall_nginx_5/api/on-grid >/tmp/og.json 2>/dev/null && echo "oncall via opsnet: OK" && head -c 120 /tmp/og.json && echo || echo "oncall via opsnet: FAIL"
docker exec ops_edge wget -qO- -T 3 http://ops_certs_ui/inventory.json >/dev/null 2>/dev/null && echo "certs inventory: OK" || \
docker exec ops_edge wget -qO- -T 3 http://ops_certs_ui/status.json >/dev/null 2>/dev/null && echo "certs status.json: OK" || echo "certs: FAIL"
docker exec ops_edge wget -qO- -T 3 http://ops_hub/tools.json >/dev/null && echo "hub tools.json: OK" || echo "hub: FAIL"

echo "== disk after =="
df -h / | tail -1
echo "done."
