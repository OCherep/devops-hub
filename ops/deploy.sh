#!/bin/bash
# /opt/ops/hub/ops/deploy.sh — єдиний редеплой хаба + модулів
set -euo pipefail
chmod +x "$0" 2>/dev/null || true
OPS="${OPS_ROOT:-/opt/ops}"
find "$OPS/hub/ops" -name "*.sh" -exec chmod +x {} + 2>/dev/null || true
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

keep_env() {
  local f="$1" bak="$2"
  if [ -f "$f" ]; then cp -a "$f" "$bak"; echo "preserved $f"; fi
}
restore_env() {
  local f="$1" bak="$2"
  if [ -f "$bak" ]; then cp -a "$bak" "$f"; echo "restored $f"; fi
}

up() {
  local dir="$1"; shift || true
  [ -f "$dir/docker-compose.yml" ] || { echo "skip compose $dir"; return 0; }
  echo "== compose $dir $* =="
  (cd "$dir" && docker compose up -d --remove-orphans "$@")
}

"$OPS/hub/ops/network.sh" 2>/dev/null || "$OPS/network.sh" 2>/dev/null || docker network create opsnet 2>/dev/null || true

keep_env "$OPS/oncall/.env" /tmp/oncall.env.bak
keep_env "$OPS/mentions/.env" /tmp/mentions.env.bak
keep_env "$OPS/postgres/.env" /tmp/postgres.env.bak

pull "$OPS/hub"    origin main
pull "$OPS/radar"  origin grok-0.0.1
pull "$OPS/oncall" origin grok-1.0.0

restore_env "$OPS/oncall/.env" /tmp/oncall.env.bak
restore_env "$OPS/postgres/.env" /tmp/postgres.env.bak

mkdir -p "$OPS/edge" "$OPS/certs/ui" "$OPS/postgres/init" "$OPS/mentions/ui"
cp -a "$OPS/hub/ops/edge/." "$OPS/edge/" 2>/dev/null || true
cp -a "$OPS/hub/ops/postgres/docker-compose.yml" "$OPS/postgres/" 2>/dev/null || true
cp -a "$OPS/hub/ops/postgres/init/." "$OPS/postgres/init/" 2>/dev/null || true
cp -a "$OPS/hub/ops/certs/docker-compose.yml" "$OPS/certs/" 2>/dev/null || true
cp -a "$OPS/hub/ops/certs/ui/index.html" "$OPS/certs/ui/" 2>/dev/null || true
# mentions code, не чіпати .env
cp -a "$OPS/hub/ops/mentions/app.py" "$OPS/mentions/" 2>/dev/null || true
cp -a "$OPS/hub/ops/mentions/Dockerfile" "$OPS/mentions/" 2>/dev/null || true
cp -a "$OPS/hub/ops/mentions/docker-compose.yml" "$OPS/mentions/" 2>/dev/null || true
cp -a "$OPS/hub/ops/mentions/ui/." "$OPS/mentions/ui/" 2>/dev/null || true
restore_env "$OPS/mentions/.env" /tmp/mentions.env.bak
if [ ! -f "$OPS/mentions/.env" ]; then
  echo "WARN $OPS/mentions/.env missing — Slack tokens / DATABASE_URL"
fi

up "$OPS/postgres"
if docker ps --format '{{.Names}}' | grep -q '^ops_postgres$'; then
  if [ -f "$OPS/postgres/init/02-mentions.sql" ]; then
    docker exec -i ops_postgres psql -U ops -d platform < "$OPS/postgres/init/02-mentions.sql" >/tmp/mentions-sql.log 2>&1 || true
    echo "postgres mentions schema applied"
  fi
fi

up "$OPS/hub"
up "$OPS/radar"
up "$OPS/certs"
# Ether app is OCherep/ether@grok-0.0.1 — never copy hub/ops/ether (README + Caddy snippet only).
if [ -d "$OPS/ether/.git" ]; then
  pull "$OPS/ether" origin grok-0.0.1
elif [ -f "$OPS/ether/nginx.conf" ] || [ -f "$OPS/ether/public/index.html" ]; then
  echo "== replacing ether nginx landing with git clone =="
  (cd "$OPS/ether" && docker compose down) 2>/dev/null || true
  mv "$OPS/ether" "$OPS/ether.landing.bak.$(date +%Y%m%d%H%M)"
  git clone --branch grok-0.0.1 --single-branch https://github.com/OCherep/ether.git "$OPS/ether"
elif [ -e "$OPS/ether" ]; then
  echo "WARN $OPS/ether exists but is not git — skip clone. rm -rf and re-run to install OCherep/ether@grok-0.0.1"
else
  echo "== clone ether grok-0.0.1 =="
  git clone --branch grok-0.0.1 --single-branch https://github.com/OCherep/ether.git "$OPS/ether"
fi
up "$OPS/ether" --build
up "$OPS/mentions" --build --force-recreate
up "$OPS/oncall"
up "$OPS/edge" --force-recreate

echo "== health (opsnet, без hairpin) =="
docker exec ops_edge wget -qO- -T 3 http://oncall_nginx_5/api/on-grid >/dev/null 2>&1 && echo "oncall: OK" || echo "oncall: FAIL"
docker exec ops_edge wget -qO- -T 3 http://ops_hub/tools.json >/dev/null 2>&1 && echo "hub: OK" || echo "hub: FAIL"
docker exec ops_edge wget -qO- -T 3 http://ops_mentions:8091/health >/dev/null 2>&1 && echo "mentions: OK" || echo "mentions: FAIL"
docker exec ops_edge wget -qO- -T 3 http://ops_ether/ether/ >/dev/null 2>&1 && echo "ether: OK" || echo "ether: FAIL"
docker exec ops_edge wget -qO- -T 3 http://ops_certs_ui/ >/dev/null 2>&1 && echo "certs: OK" || echo "certs: FAIL"

echo "== disk after =="
df -h / | tail -1
echo "done. UI: https://s.ks.tv/  https://s.ks.tv/ether/  https://s.ks.tv/mentions/  https://s.ks.tv:85/"
