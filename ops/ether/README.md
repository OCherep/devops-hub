# Module: ether (Ефір)

Part of [DevOps Hub](https://github.com/OCherep/devops-hub).

Control plane overlay для DevOps KS.TV. **Не SoT.** Не на шляху абонента.

| | |
|---|---|
| Join | `service=ether` |
| Owner | devops |
| Tier | 2 (overlay) |
| App repo | [OCherep/ether@grok-0.0.1](https://github.com/OCherep/ether/tree/grok-0.0.1) |
| Live (Hub) | `https://s.ks.tv/ether/` |
| Compose | цей каталог → `/opt/ops/ether` |

Повна оболонка (очі, конектори, смуги CD) живе в репозиторії ether. Тут — реєстрація в Hub і landing на opsnet.

## Contract

| Вимога | Значення |
|--------|----------|
| Host packages | немає (тільки Docker) |
| Network | `opsnet` (external) |
| Публікація | edge path `/ether/` — без host port |
| Реєстр | рядок у `modules.env` |
| Hub | картка в `tools.json` |

```bash
/opt/ops/up.sh ether
/opt/ops/up.sh edge
```
