# Deploy guide — DevOps Hub warm stack

## Передумови

- EC2 (або VM): Docker Engine + Docker Compose plugin
- DNS (опційно): `s.ks.tv` → EIP інстанса
- SG: `22` (обмежено), `80`, `443`, **`85`** (OnCall)

На хості **немає** обов’язкових apt-пакетів окрім docker/git.

## Архітектура портів

```text
Internet
  ├── :80 / :443  → ops_edge (Caddy) → ops_hub:80, ops_radar:80, oncall_nginx_5:80  [opsnet]
  └── :85         → oncall_nginx_5:443 (прямий HTTPS OnCall)

Правила:
- Edge — єдиний власник host :80 і :443.
- OnCall compose публікує ТІЛЬКИ "85:443". Внутрішній listen :80 — для Caddy на opsnet, без publish.
- Hub/Radar — без host ports, лише opsnet.
- Перед up: /opt/ops/network.sh (мережа opsnet).
```

## Крок за кроком

### 1. Каталог і bootstrap

```bash
sudo mkdir -p /opt/ops && sudo chown "$USER:$USER" /opt/ops
git clone https://github.com/OCherep/devops-hub.git /opt/ops/hub
/opt/ops/hub/ops/bootstrap.sh /opt/ops
```

Скрипт:
- копіює/лінкуює `network.sh`, `up.sh`, `down.sh`, `modules.env`, `_template`, `edge/`
- клонує `radar` і `oncall` якщо їх ще немає (URL з `modules.env`)

### 2. OnCall (існуючий)

Якщо oncall уже крутиться з іншого шляху — або:

```bash
# симлінк
ln -sfn /шлях/до/поточного/oncall-system /opt/ops/oncall
```

або clone гілки `grok-1.0.0` у `/opt/ops/oncall` і `docker compose up -d` **як раніше** (порти 85 і за потреби 80).

> Якщо edge теж хоче host `:80`, **не** публікуй oncall `80:80` одночасно з edge. Залиш oncall лише **`85:443`**, ACME/80 — на edge або окремий cert flow для oncall.

Рекомендований `ports` для мирного співіснування з edge:

```yaml
ports:
  - "85:443"
  # - "80:80"   # вимкни, якщо edge займає 80
```

Сертифікати oncall лишаються в його `./certs`.

### 3. Мережа і static-модулі

```bash
/opt/ops/network.sh
cd /opt/ops/hub && docker compose -f docker-compose.yml up -d
cd /opt/ops/radar && docker compose -f docker-compose.yml up -d
cd /opt/ops/edge && docker compose up -d
```

Або одним махом: `/opt/ops/up.sh`

### 4. TLS на edge

У `edge/Caddyfile` заміни `s.ks.tv` на свій хост. Caddy сам випустить Let’s Encrypt, якщо `:80` вільний і DNS вказує на інстанс.

Локально без DNS:

```caddy
:80 {
  handle_path /radar/* {
    reverse_proxy ops_radar:80
  }
  handle {
    reverse_proxy ops_hub:80
  }
}
```

### 5. tools.json live URL

Після деплою онови в репо hub (або локально):

```json
"live": "https://s.ks.tv/"
"live": "https://s.ks.tv/radar/"
"live": "https://s.ks.tv:85/"
```

## Новий сервіс (скелетон)

```bash
cp -a /opt/ops/_template /opt/ops/my-service
cd /opt/ops/my-service
# відредагувати docker-compose.yml, Caddy snippet, README
# додати my-service у modules.env
# за потреби location у edge/Caddyfile
/opt/ops/up.sh my-service
```

Див. [_template/README.md](./_template/README.md).

## Оновлення

```bash
cd /opt/ops/hub && git pull && docker compose up -d --force-recreate
cd /opt/ops/radar && git pull && docker compose up -d --force-recreate
cd /opt/ops/oncall && git pull && docker compose up -d --build
```

## Troubleshooting

| Симптом | Що перевірити |
|---------|----------------|
| edge не стартує | `docker ps -a`, зайнятий 80/443 oncall’ом |
| /radar/ 404 | `handle_path` vs `handle`, чи `ops_radar` в opsnet |
| oncall OK, hub ні | `docker network inspect opsnet` |
| ACME fail | DNS A-record, SG 80, не два процеси на 80 |
