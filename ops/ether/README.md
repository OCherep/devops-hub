# Module: ether (Ефір)

Part of [DevOps Hub](https://github.com/OCherep/devops-hub).

**Цей каталог у Hub — лише контракт і Caddy snippet.** Бойовий модуль клонується з [OCherep/ether@grok-0.0.1](https://github.com/OCherep/ether/tree/grok-0.0.1) у `/opt/ops/ether` (`docker-compose.yml` + `Dockerfile` живуть там).

Landing nginx тут більше не деплоїться.

| | |
|---|---|
| Join | `service=ether` |
| Owner | devops |
| Tier | 2 (overlay) |
| App repo | [OCherep/ether@grok-0.0.1](https://github.com/OCherep/ether/tree/grok-0.0.1) |
| Live | `https://s.ks.tv/ether/` |
| Compose | `/opt/ops/ether/docker-compose.yml` (клон ether, не цей каталог) |
| Edge | `handle /ether/*` **без strip** (SSR) |

## Cutover зі старого landing

```bash
cd /opt/ops
docker compose -f ether/docker-compose.yml down || true
rm -rf /opt/ops/ether
git clone --branch grok-0.0.1 --single-branch \
  https://github.com/OCherep/ether.git /opt/ops/ether
/opt/ops/up.sh ether
/opt/ops/up.sh edge
```

`bootstrap.sh` не перезаписує існуючий шлях. Якщо лишилась nginx-заглушка — `rm -rf` обов’язковий.
