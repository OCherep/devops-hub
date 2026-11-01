# DevOps Hub: маршрут публічної форми «Нове звернення» (16.10.2026, лише читання)
Коміти: devops-hub@main 4c88535 (09.10), oncall-system локальна гілка grok-1.0.0 e1e8d06 (09.10; origin/main aa6ae12 від 26.08 відстає, у ньому теж немає PD).

## Маршрут (факти)
1. UI: devops-hub index.html:115-128 (поля hi-name/slack/email/mins/prio/desc; пріоритети Звичайний…Терміновий, index.html:124) → roster.js:118-130 `submitHubIncident` → `POST /api/incidents`, source="hub-guest", без токена/ролі. Дубль у шапці: chrome.js:154.
   Перевірка на клієнті лише: name+email+desc не порожні (roster.js:127). Немає captcha, rate limit, dedup.
2. Транспорт: ocFetch пробує `/oncall-api` → `https://s.ks.tv:85` (roster.js:1, chrome.js:3). Caddy ops/edge/Caddyfile:22-25 знімає префікс → oncall_nginx_5:80 → Go oncall-system.
3. Backend: main.go:586 `/api/incidents` → `withIPAllow(handleIncidents)` (main.go:258-280): CORS для s.ks.tv + IP allowlist; ipAllowed() main.go:199-212 — якщо таблиця allowed_ips порожня, доступ ВІДКРИТИЙ. Сесійної автентифікації на POST немає.
4. handleIncidents (handlers_client.go:1001): decode JSON (≈1058), `role := inc.Role` береться з тіла (1081) — порожня роль = гість. Гостю обов'язковий reporter_slack, перевіряється через Slack API (slackResolveUser), підтягуються ім'я/email; дата не в минулому. Ліміту довжини/частоти немає.
   (SOFT_AUTH=1 за замовчуванням: docker-compose.yml:21; handlers_session.go:192,227 — зона AppSec; роль із body також на 1081.)
5. Маршрутизація: applyIncidentRouting handlers_settings.go:264-310; on-call = власна БД `shifts` (primary/backup на дату, handlers_settings.go:255), режим on-grid за таблицею/таймзоною (isOnGridNow :151). Ранги priorityRank :226: Критичний=3, Терміновий=4, Високий=2.
   - on-grid: будь-який пріоритет → notify; ≥Критичний → призначити primary.
   - off-grid: ≥Високий → призначити primary + notify; нижче — без сповіщень.
6. INSERT INTO incidents (handlers_client.go:1169) → `go notifyNewIncident` (1209) / skip (1211).
7. Сповіщення (handlers_notify.go): Slack канал+Telegram-дзеркало (notifyTeam :55-76), DM виконавцю/диспетчерам/primary/backup (:167-215). Env: SLACK_BOT_TOKEN / Slack webhook, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (docker-compose.yml:23-24, handlers_notify.go:23-45). Дедуп лише in-memory по ID інциденту, 2 хв (:105-123,170) — від флуду не захищає (кожне звернення має новий ID). Ретраїв немає.
   Ескалації (повторів/ack-таймаутів) у коді немає.

## PagerDuty
- ФАКТ: у жодній гілці обох репо немає PagerDuty (git grep / git log -G по всіх гілках = 0): нема Events API v2, routing key, dedup_key, severity, REST-токена.
- PD (vidmind.pagerduty.com) — 10 сервісів, жодного devops-hub/oncall/s.ks.tv: AWS, DataDog, DataDogDisaster, Default Mobilization, Grafana, Jenkins, NewRelicMonitoring, StarAds-Grafana, Zabbix production, Zabbix production warn. Другий namespace за запитом «hub» — 0.
- EP: «Vidmind production» PX576S0 (6 людей, 5 хв, 2 loops) — AWS/DataDogDisaster/NewRelic/Zabbix prod; «PDAlert» PG6G36F (5 людей, 30 хв) — DataDog/Grafana/Jenkins/StarAds/Zabbix warn; «Default Mobilization EP»; «Send to Artem» (без сервісів).
- Гіпотеза (низька впевненість): «надсилає в PagerDuty» — або плани (INTEGRATIONS.md), або непрямо (напр. Slack→PD). Підтверджень не знайдено. Urgency/integration-налаштування сервісів не перевіряв.

## Ризик флуду
Анонім (якщо allowed_ips порожня — перевірити на проді) може скриптом слати POST з будь-яким валідним Slack ID (довідник відкритий: /api/slack/lookup) і priority=«Терміновий» → кожен запит = Slack DM primary+backup+диспетчерам і пост у канал/Telegram, цілодобово (off-grid теж). Пейджингу через PD нема, але є DM-втома і засмічення БД/каналу; плюс витрата Slack API rate limit. Зупиняє лише: IP allowlist (якщо заповнена) і вимога реального Slack-користувача.

## Моніторинг
Datadog: моніторів за «ks.tv / devops-hub / oncall» — 0. Synthetics/логи не перевіряв.

## Прогалини
Прод-стан allowed_ips, реальні env (чи задані Slack/Telegram), чи гілка grok-1.0.0 = прод; urgency PD-сервісів; nginx oncall_nginx_5 rate limit (конфіг не в репо).

## Рекомендації CUT-04
1. Rate limit на POST /api/incidents (по IP + reporter_slack, напр. 5/10 хв) у Caddy/nginx і в Go; ліміт розміру body/description.
2. Публічний intake не може ставити ≥Критичний: гостьовий пріоритет обрізати до «Високий», підвищує лише диспетчер; off-grid гості → без DM, лише черга.
3. Дедуп за хешем (reporter_slack+нормалізований опис, 15-30 хв) у БД, а не in-memory по ID; якщо додавати PD — Events API v2 з dedup_key=цей хеш, окремий сервіс «DevOps Hub intake» з low-urgency (urgency за severity, high лише після підтвердження людиною), routing key лише в env/secret.
4. Captcha/Turnstile або вимога SSO/сесії для форми; прибрати роль з body (AppSec, SOFT_AUTH=0).
5. Synthetic/uptime-монітор s.ks.tv і /oncall-api/health у Datadog + алерт на сплеск INSERT incidents source=hub-guest.
