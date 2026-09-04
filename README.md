# DevOps Hub

**Єдина перша сторінка** інструментів DevOps / SRE (KSTV · VidMind) + **теплий Docker-only деплой** на EC2.

| | |
|---|---|
| **Portal** | `index.html` + [`tools.json`](./tools.json) |
| **Ops layout** | [`ops/`](./ops/) → `/opt/ops` на інстансі |
| **OnCall** | окремо, **host port 85** (без змін) |
| **Edge** | Caddy `:80/:443` → Hub + `/radar/` |

## Портал

```bash
python3 -m http.server 8080
# http://localhost:8080
```

Або GitHub Pages / edge на EC2.

## Теплий деплой (Docker only)

На хості потрібні лише **Docker** і **Compose plugin**.

```text
/opt/ops/
  edge/     # :80/:443
  hub/      # this repo
  radar/    # tech radar
  oncall/   # :85
  _template/
  modules.env
  up.sh down.sh network.sh bootstrap.sh add-module.sh
```

```bash
sudo mkdir -p /opt/ops && sudo chown "$USER:$USER" /opt/ops
git clone https://github.com/OCherep/devops-hub.git /opt/ops/hub
/opt/ops/hub/ops/bootstrap.sh /opt/ops
/opt/ops/network.sh
/opt/ops/up.sh
```

Повний гід: **[ops/DEPLOY.md](./ops/DEPLOY.md)**.

### Новий сервіс

```bash
/opt/ops/add-module.sh my-tool
# edit compose + edge snippet + tools.json
/opt/ops/up.sh my-tool edge
```

## Активні інструменти

| Інструмент | Repo | Live (ціль) |
|------------|------|-------------|
| OnCall System | [oncall-system](https://github.com/OCherep/oncall-system) | `https://s.ks.tv:85/` |
| KSTV Tech Radar | [kstv-tech_radar](https://github.com/OCherep/kstv-tech_radar) | `https://s.ks.tv/radar/` |
| DevOps Hub | this | `https://s.ks.tv/` |

## Узгодження

Кожен модуль у README: *Part of [DevOps Hub](https://github.com/OCherep/devops-hub)*.
