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

# --- preflight секретів (FAIL, значення не друкуються) ---
envget() { # envget <file> <KEY>
  [ -f "$1" ] || return 0
  grep -E "^$2=" "$1" | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'
}
bad_secret() { # порожнє, плейсхолдер або < 16 символів
  local v="$1"; local l; l="$(printf '%s' "$v" | tr '[:upper:]' '[:lower:]')"
  [ -z "$v" ] || [ "${#v}" -lt 16 ] || case "$l" in *change-me*|*changeme*|your-long-random-secret|ops) true ;; *) false ;; esac
}
PREFLIGHT_FAIL=0
need() { # need <file> <KEY>
  local v; v="$(envget "$1" "$2")"
  if bad_secret "$v"; then echo "FAIL preflight: $2 у $1 не задано/дефолтний/коротший за 16"; PREFLIGHT_FAIL=1
  else echo "ok   preflight: $2 у $1 (${#v} симв., приховано)"; fi
}
need "$OPS/oncall/.env"   DB_ADMIN_PASSWORD
need "$OPS/oncall/.env"   WEBHOOK_SECRET
need "$OPS/postgres/.env" POSTGRES_PASSWORD
for f in "$OPS/mentions/.env" "$OPS/netmap/.env"; do
  u="$(envget "$f" DATABASE_URL)"
  case "$u" in ""|*ops-change-me*|*://ops:ops@*) echo "FAIL preflight: DATABASE_URL у $f не задано або з дефолтним паролем"; PREFLIGHT_FAIL=1 ;;
    *) echo "ok   preflight: DATABASE_URL у $f (приховано)" ;; esac
done
for k in SLACK_SIGNING_SECRET ONCALL_READ_TOKEN; do
  [ -n "$(envget "$OPS/oncall/.env" "$k")" ] || echo "WARN preflight: $k не задано в oncall/.env — функцію вимкнено (fail closed)"
done
[ -n "$(envget "$OPS/mentions/.env" SLACK_SIGNING_SECRET)" ] || echo "WARN preflight: SLACK_SIGNING_SECRET не задано в mentions/.env — Slack events вимкнено"
if [ "$(envget "$OPS/oncall/.env" ONCALL_READ_TOKEN)" != "$(envget "$OPS/mentions/.env" ONCALL_READ_TOKEN)" ]; then
  echo "WARN preflight: ONCALL_READ_TOKEN в oncall/.env і mentions/.env різний — roster mentions буде урізаним"
fi
sa="$(envget "$OPS/oncall/.env" SOFT_AUTH)"; [ -z "$sa" ] || [ "$sa" = "0" ] || echo "WARN preflight: SOFT_AUTH=$sa більше не діє — приберіть"
if [ "$PREFLIGHT_FAIL" -ne 0 ] && [ "${SKIP_SECRET_PREFLIGHT:-0}" != "1" ]; then
  echo "Деплой зупинено: задайте секрети (див. hub/ops/SECURITY-AUTH.md)"; exit 1
fi
[ "${PREFLIGHT_ONLY:-0}" = "1" ] && { echo "PREFLIGHT_ONLY=1 — вихід без змін"; exit 0; }

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
cp -a "$OPS/hub/ops/netmap/app.py" "$OPS/netmap/" 2>/dev/null || true
cp -a "$OPS/hub/ops/netmap/Dockerfile" "$OPS/netmap/" 2>/dev/null || true
cp -a "$OPS/hub/ops/netmap/docker-compose.yml" "$OPS/netmap/" 2>/dev/null || true
cp -a "$OPS/hub/ops/netmap/ui/." "$OPS/netmap/ui/" 2>/dev/null || true
keep_env "$OPS/netmap/.env" /tmp/netmap.env.bak 2>/dev/null || true
restore_env "$OPS/netmap/.env" /tmp/netmap.env.bak 2>/dev/null || true
up "$OPS/netmap" --build --force-recreate
if [ -d "$OPS/awsinv/.git" ]; then
  pull "$OPS/awsinv" origin main
else
  echo "== clone aws-inventory =="
  git clone --branch main --single-branch https://github.com/OCherep/aws-inventory.git "$OPS/awsinv"
fi
up "$OPS/awsinv" --build
up "$OPS/oncall"
up "$OPS/edge" --force-recreate

echo "== health (opsnet, без hairpin) =="
docker exec ops_edge wget -qO- -T 3 http://oncall_nginx_5/api/on-grid >/dev/null 2>&1 && echo "oncall: OK" || echo "oncall: FAIL"
docker exec ops_edge wget -qO- -T 3 http://ops_hub/tools.json >/dev/null 2>&1 && echo "hub: OK" || echo "hub: FAIL"
docker exec ops_edge wget -qO- -T 3 http://ops_mentions:8091/health >/dev/null 2>&1 && echo "mentions: OK" || echo "mentions: FAIL"
docker exec ops_edge wget -qO- -T 3 http://ops_netmap:8092/health >/dev/null 2>&1 && echo "netmap: OK" || echo "netmap: FAIL"
docker exec ops_edge wget -qO- -T 3 http://ops_awsinv:8093/health >/dev/null 2>&1 && echo "awsinv: OK" || echo "awsinv: FAIL"
docker exec ops_edge wget -qO- -T 3 http://ops_ether/ether/ >/dev/null 2>&1 && echo "ether: OK" || echo "ether: FAIL"
docker exec ops_edge wget -qO- -T 3 http://ops_certs_ui/ >/dev/null 2>&1 && echo "certs: OK" || echo "certs: FAIL"

echo "== disk after =="
df -h / | tail -1
echo "done. UI: https://s.ks.tv/  https://s.ks.tv/aws/  https://s.ks.tv/ether/  https://s.ks.tv/mentions/  https://s.ks.tv:85/"
