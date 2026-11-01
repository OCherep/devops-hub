# DevOps Hub — інвентаризація auth/секретів (2026-11-01)

Джерело сесії для всіх модулів — OnCall: `GET $ONCALL_API/api/session/me` з токеном
(`Authorization: Bearer` з localStorage хаба або cookie `oncall_session`; same-origin через edge `/oncall-api`).
Кеш перевірки 30 с. Заголовок `X-Oncall-User` ніде не приймається.

| Модуль / контейнер | Маршрут | Було | Стало |
|---|---|---|---|
| mentions / ops_mentions | `GET /health`, статика UI | відкрито | відкрито |
| mentions | `GET /api/*` (mentions, people, stats…) | відкрито | сесія OnCall |
| mentions | `/api/debug`, `/api/backfill` | відкрито | admin |
| mentions | `POST /api/slack/events` | підпис пропускався без `SLACK_SIGNING_SECRET` | fail closed (403) без секрету, HMAC v0 |
| mentions | `/api/data` OnCall (upstream) | без токена | `X-Oncall-Read-Token: $ONCALL_READ_TOKEN` |
| mentions | CORS | `*` | `HUB_ORIGIN` |
| netmap / ops_netmap | `GET /health`, статика UI | відкрито | відкрито |
| netmap | `GET /api/*` | відкрито | сесія OnCall |
| netmap | усі `POST` (scan, cidrs…) | відкрито | admin |
| netmap | CORS | `*` | `HUB_ORIGIN` |
| postgres / ops_postgres | `POSTGRES_PASSWORD` | дефолт у compose | без дефолту, preflight FAIL |
| mentions, netmap | `DATABASE_URL` | дефолт з паролем у коді/compose | без дефолту, preflight FAIL |
| hub, radar, ether, certs_ui, edge | — | статика / не змінено | не змінено (див. «Не охоплено») |

## Змінні середовища (лише імена)
- `postgres/.env`: `POSTGRES_PASSWORD`
- `mentions/.env`: `DATABASE_URL`, `SLACK_SIGNING_SECRET`, `ONCALL_READ_TOKEN` (те саме значення, що в `oncall/.env`), `HUB_ORIGIN` (опц., дефолт `https://s.ks.tv`), `ONCALL_API` (опц.)
- `netmap/.env`: `DATABASE_URL`, `HUB_ORIGIN` (опц.), `ONCALL_API` (опц.)
- `oncall/.env`: `DB_ADMIN_PASSWORD`, `WEBHOOK_SECRET`, `SLACK_SIGNING_SECRET`, `ONCALL_READ_TOKEN`, опц. `ONCALL_BOOTSTRAP_ADMIN_PASSWORD`; `SOFT_AUTH` прибрати.

`ops/deploy.sh` тепер має preflight: FAIL на порожні/дефолтні/короткі (<16) секрети, значення не друкує.
`PREFLIGHT_ONLY=1` — лише перевірка. `SKIP_SECRET_PREFLIGHT=1` — аварійний обхід (не рекомендовано).

## Тести
`python3 -m unittest discover -s ops/tests`

## Не охоплено
- `aws-inventory` (ops_awsinv) — окремий репозиторій, не перевірявся.
- Зміна `POSTGRES_PASSWORD` у `.env` не змінює пароль уже ініціалізованої БД — потрібен `ALTER USER` (див. план деплою).
