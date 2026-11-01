# Сповіщення про чергування: дубль у канал, налаштування, інші месенджери (п.2–4)
Автор: Lingxi's Engineer Bot · 16.10.2026 23:10 Київ (20:10 UTC) · лише читання коду `oncall-system` гілка `grok-1.0.0` (e1e8d06). Змін, PR і тестових повідомлень немає.

## 0. Як працює зараз (факти з коду, висока впевненість)
- Ранкове повідомлення: `handlers_duty_digest.go:23-54`. Тікер раз на 30 с; шле, коли `kyivNow()` == `morning_duty_time` (за замовч. `08:00`) і ввімкнено `morning_duty_notify` (за замовч. `1`). Ключі в таблиці `app_settings`.
- Хто черговий: `todayShiftPair()` (`handlers_slack_team.go:45-49`) — `primary_user`/`backup_user` з `shifts` на сьогодні.
- Доставка: лише Slack DM (`conversations.open` + `chat.postMessage`, `handlers_duty_digest.go:70-120`) з `SLACK_BOT_TOKEN`. У канал і Telegram це повідомлення НЕ йде. Текст захардкоджено (`:64`), посилання `https://s.ks.tv:85/` теж.
- Ризики надійності (факт за кодом): (a) `morning_duty_last` ставиться ДО відправки (`:47`) → збій Slack = повідомлення втрачено без повтору; (b) якщо сервіс перезапускався саме в цю хвилину — день пропущено; (c) `todayShiftPair` бере дату з `time.Now()` (TZ контейнера), а час — з `kyivNow()`; при `morning_duty_time` між 00:00 і 02:59/03:00 дата може не збігтися (гіпотеза, залежить від TZ контейнера); (d) помилки лише в `log.Printf`, ні метрик, ні аудиту доставки.
- Для звернень уже є «командний канал + Telegram-дзеркало»: `notifyTeam()` (`handlers_notify.go:55-80`), канал `SLACK_TEAM_CHANNEL`, `TELEGRAM_CHAT_ID`.

## 1. П.2 — дубль у загальний канал з PM: так, можна (висока впевненість)
Інфраструктура є (`notifyTeam`). Мінімальна зміна: після DM ще один зведений пост «Сьогодні чергують: primary X, backup Y» в окремий канал (не обов'язково `SLACK_TEAM_CHANNEL`). Умови:
- окремий ключ каналу (`duty_channel_id`), бо командний канал зараз отримує й звернення;
- бот має бути учасником каналу (інакше `not_in_channel`), скоупи `chat:write` (є);
- у загальний канал — лише імена/ролі й кількість звернень, без описів звернень, телефонів, email (питання до @AppSec про PII);
- один пост на день, ідемпотентно (ключ дня), з повтором при збої.

## 2. П.3 — пропозиція налаштувань в адмінці
Новий розділ «Сповіщення про чергування» (`/api/admin/settings` вже є, `main.go:582`; ⚠ ендпоінт зараз без `requireAuth` — див. CUT-04 AC2, тому вмикати редагування шаблонів лише після AC1–3):
| Ключ | Тип | Приклад |
|---|---|---|
| `duty_notify_enabled` | bool | 1 |
| `duty_notify_time` | HH:MM Київ | 08:00 |
| `duty_targets` | список | `slack_dm:primary`, `slack_dm:backup`, `slack_channel:C0XXXX`, `telegram:<chat>` |
| `duty_template_dm` | текст | див. нижче |
| `duty_template_channel` | текст | див. нижче |
| `duty_weekends` | bool | 1 |

Шаблон: Go `text/template` з білим списком змінних і екрануванням під кожен канал (Slack mrkdwn / Telegram HTML), без довільних функцій.
Змінні: `{{.Date}}`, `{{.Weekday}}`, `{{.Role}}`, `{{.Primary}}`, `{{.Backup}}`, `{{.PrimaryMention}}` (`<@U…>`), `{{.OpenCount}}`, `{{.InWorkCount}}`, `{{.HubURL}}`, `{{.RunbookURL}}`.
Приклад DM: `Чергування {{.Date}} ({{.Weekday}}): ви {{.Role}}. Відкритих: {{.OpenCount}}, у роботі: {{.InWorkCount}}. {{.HubURL}}`
Приклад каналу: `:rotating_light: Сьогодні {{.Date}} чергують: {{.PrimaryMention}} (основний), {{.BackupMention}} (дублюючий). Runbook: {{.RunbookURL}}`
Кнопка «Попередній перегляд» рендерить без відправки; «Тест» — лише після рішення Олега (зараз заборонено).
Аудит: хто/коли змінив шаблон чи цілі (таблиця `settings_audit`).

## 3. П.4 — інші месенджери
Що вже є: Slack (bot API + incoming webhook), Telegram (`postTelegram`, `handlers_notify.go:304-335`, один груповий чат, конвертер mrkdwn→HTML), email (`notifyEmail`, `:375`). WhatsApp — нема.
Абстракція (пропозиція):
```go
type Notifier interface {
    Name() string                       // "slack", "telegram", "whatsapp", "email"
    Send(ctx, target Target, msg Message) (DeliveryResult, error)
}
type Message struct{ Kind, Text, Markdown string; Vars map[string]string; DedupKey string }
```
- реєстр нотифікаторів, конфіг цілей у БД; один `dispatch()` замість прямих викликів у `notifyTeam`/`slackDM`;
- таблиця `notify_outbox` (pending/sent/failed, attempts, last_error) + воркер з повторами і backoff → вирішує втрату з §0(a), дає аудит і метрики для AC7;
- рендер шаблону окремо на кожен канал; ідентичність користувача: `users.slack_id`, `telegram_chat_id`, `whatsapp_e164` (opt-in).
Telegram: особисті DM можливі лише після того, як користувач сам натисне /start боту (обмеження платформи) — для DM потрібна прив'язка через deep-link.
WhatsApp: лише WhatsApp Business Platform (Cloud API Meta або BSP): верифікований бізнес і номер, бізнес-ініційовані повідомлення поза 24-год вікном — лише через попередньо схвалені шаблони (категорія utility), платно за повідомлення; потрібен opt-in користувача. Точні ціни й ліміти для UA — від @Researchy з джерелами.
Рекомендація: спершу Slack-канал + outbox (мінімальна вартість), Telegram DM — другим кроком, WhatsApp — лише якщо є бізнес-потреба і власник акаунта Meta Business.

## Рішення для Олега
1. Окремий канал для дубля чи `SLACK_TEAM_CHANNEL`?
2. Чи потрібні Telegram DM / WhatsApp взагалі.
3. Хто може редагувати шаблони (лише admin після AC1–3).
4. Робити це як окремий зріз після CUT-04 (рекомендую: outbox + шаблони — один PR, канал — другий).
