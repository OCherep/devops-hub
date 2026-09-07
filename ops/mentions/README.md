# Slack Mentions (DevOps Hub)

Окремий сервіс хаба. Схема Postgres `mentions.*` у спільній `platform` БД — пізніше можна стикувати з OnCall roster по `slack_id`.

## Slack app
1. api.slack.com/apps → Create (або існуючий OnCall bot, якщо scopes вистачить).
2. Bot token scopes: `channels:history`, `groups:history`, `channels:read`, `users:read`, `chat:write` (для permalink), `usergroups:read`.
3. Event Subscriptions: Request URL `https://s.ks.tv/mentions/api/slack/events`
   Subscribe: `message.channels`, `message.groups`, `app_mention`.
4. Бот має бути в каналах, які слухаємо.
5. `.env` поруч із compose:

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
SLACK_DEVOPS_GROUP=devops-team
DATABASE_URL=postgres://ops:ops@ops_postgres:5432/platform
```

User-group `@devops-team` приходить як `<!subteam^S…|@devops-team>`.
