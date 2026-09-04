# Ops layout — тепла модульна схема

На EC2 (і будь-якій машині з **лише Docker + Compose**):

```text
/opt/ops/
├── edge/           # Caddy :80/:443 → hub + /radar/
├── hub/            # цей репозиторій (devops-hub)
├── radar/          # kstv-tech_radar
├── oncall/         # oncall-system (порт хоста 85 без змін)
├── _template/      # шаблон нового сервісу (копіюй)
├── network.sh      # створює docker network opsnet
├── bootstrap.sh    # перший підйом з git
├── up.sh           # підняти всі зареєстровані модулі
├── down.sh
└── modules.env     # список модулів і git URL
```

## Правила

1. **Один сервіс = одна директорія** під `/opt/ops/<id>/`.
2. У кожній директорії — свій `docker-compose.yml` (і лише свої volumes/env).
3. Спільна мережа: **`opsnet`** (`external: true` у compose модулів).
4. На хост **не** ставимо nginx/java/node — тільки Docker.
5. **OnCall** лишається на **`:85`** (як зараз). Hub і Radar — через edge **`:443`**.
6. Новий сервіс: `cp -a _template <id>` → заповнити → додати в `modules.env` + за потреби route в `edge/Caddyfile` + запис у `tools.json`.

## Швидкий старт на EC2

```bash
# 1) Docker вже має бути
sudo mkdir -p /opt/ops && sudo chown "$USER:$USER" /opt/ops
cd /opt/ops

# 2) Клонувати hub (джерело layout + скриптів)
git clone https://github.com/OCherep/devops-hub.git hub
cd hub

# 3) Розкласти ops-файли в /opt/ops (або працювати з ops/ як root layout)
./ops/bootstrap.sh /opt/ops

# 4) Мережа + модулі
/opt/ops/network.sh
/opt/ops/up.sh
```

Після цього:

| URL | Сервіс |
|-----|--------|
| `https://<host>/` | DevOps Hub |
| `https://<host>/radar/` | Tech Radar |
| `https://<host>:85/` | OnCall (без змін) |

Деталі: [DEPLOY.md](./DEPLOY.md), шаблон: [_template/](./_template/).
