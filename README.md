# DevOps Hub

**Єдина перша сторінка** для інструментів DevOps / SRE навколо KSTV (VidMind) і міжкомандної роботи.

| | |
|---|---|
| **Live (після Pages)** | `https://ocherep.github.io/devops-hub/` |
| **Каталог** | [`tools.json`](./tools.json) |
| **Owner** | platform / SRE |

## Навіщо

Замість розкиданих репо й закладок — один портал:

1. **[OnCall System](https://github.com/OCherep/oncall-system)** — чергування, звернення, дейлі
2. **[KSTV Tech Radar](https://github.com/OCherep/kstv-tech_radar)** — tech portfolio, ArchUnit, DORA
3. **Planned** — runbooks, service catalog, DORA dashboard, …

Нові ідеї додаються записом у `tools.json` без переписування HTML.

## Швидкий старт

```bash
git clone https://github.com/OCherep/devops-hub.git
cd devops-hub
# локально: будь-який static server
python3 -m http.server 8080
# → http://localhost:8080
```

### GitHub Pages

Settings → Pages → Source: **Deploy from a branch** → `main` / `/ (root)`.

## Як додати інструмент

1. Створи/підготуй репозиторій.
2. Додай об’єкт у `tools.json` (`status`: `active` | `beta` | `planned`).
3. У README того репо — рядок: *Part of [DevOps Hub](https://github.com/OCherep/devops-hub)*.
4. (Опційно) PR у цей репо.

## Узгодження з існуючими проєктами

| Проєкт | Гілка / стан | Роль у Hub |
|--------|--------------|------------|
| [oncall-system](https://github.com/OCherep/oncall-system/tree/grok-1.0.0) | `grok-1.0.0` | Операційна робота з командою |
| [kstv-tech_radar](https://github.com/OCherep/kstv-tech_radar/tree/grok-0.0.1) | `grok-0.0.1` | Технологічні рішення платформи |

Разом: **хто на зміні / що ламається** (OnCall) + **який стек дозволений** (Radar).

## Ліцензія

Внутрішній tooling; за потреби додай LICENSE.
