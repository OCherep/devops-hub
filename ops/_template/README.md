# Module: __MODULE_ID__

Warm module under `/opt/ops/__MODULE_ID__/`.

## Contract

| Вимога | Значення |
|--------|----------|
| Host packages | **немає** (тільки Docker) |
| Network | `opsnet` (external) |
| Compose | `docker-compose.yml` у корені модуля |
| Публікація | через **edge** path/subdomain; host ports — виняток (OnCall `:85`) |
| Дані | `./data` volume всередині модуля |
| Реєстр | рядок у `/opt/ops/modules.env` |
| Hub | картка в `tools.json` |

## Lifecycle

```bash
/opt/ops/add-module.sh __MODULE_ID__
# or with git:
# /opt/ops/add-module.sh __MODULE_ID__ https://github.com/OCherep/__MODULE_ID__.git main

/opt/ops/up.sh __MODULE_ID__
# edit edge Caddyfile + up edge
/opt/ops/up.sh edge
```

## Public dir

Для static — поклади файли в `public/`.
