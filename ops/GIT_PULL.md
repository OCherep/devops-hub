# Безпечний git pull на EC2

## OnCall (`/opt/ops/oncall`, гілка grok-1.0.0)

```bash
cd /opt/ops/oncall
git status -sb
git stash push -u -m "local-$(date +%F)" -- scripts/nginx-entrypoint.sh scripts/issue-letsencrypt.sh || true
git fetch origin
git pull --ff-only origin grok-1.0.0
# якщо nginx віддає статику з образу — перезібрати:
docker compose up -d --build
```

Адмінка: `https://s.ks.tv:85/admin.html` (не http). Hard refresh.

## Hub (`/opt/ops/hub`, гілка main)

```bash
cd /opt/ops/hub
git status -sb
git stash push -m "local-upsh" -- ops/up.sh
git pull --ff-only origin main
# розкласти модуль сертифікатів
mkdir -p /opt/ops/certs/hooks
cp -a /opt/ops/hub/ops/certs/. /opt/ops/certs/
# подивитись stash
git stash list
# відкинути локальний up.sh, якщо репо новіший:
# git stash drop
# або повернути свої правки поверх:
# git stash pop
```

## Типові конфлікти

| Файл | Чому |
|------|------|
| `ops/up.sh` | ручні правки на хості |
| `scripts/nginx-entrypoint.sh` | chmod / локальний TLS |
| `scripts/issue-letsencrypt.sh` | те саме |

## Ether (`/opt/ops/ether`, гілка grok-0.0.1)

Повна оболонка, не landing. Якщо каталог ще nginx-заглушка (не git):

```bash
cd /opt/ops
docker compose -f ether/docker-compose.yml down || true
rm -rf ether
git clone --branch grok-0.0.1 --single-branch https://github.com/OCherep/ether.git ether
/opt/ops/up.sh ether
/opt/ops/up.sh edge
```

Оновлення:

```bash
cd /opt/ops/ether
git status -sb
git pull --ff-only origin grok-0.0.1
docker compose up -d --build
```

Caddy: **`handle /ether/*` без strip**. Після pull Hub скопіюй `ops/edge/Caddyfile` в `/opt/ops/edge/` і `up.sh edge`.

