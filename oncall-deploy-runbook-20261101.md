# Ранбук деплою OnCall: `fix/oncall-schedule-logic` → прод (один захід)

Дата: 2026-11-01 · PR: https://github.com/OCherep/oncall-system/pull/2 · база `grok-1.0.0` @ e1e8d06
Позначки: ✅ перевірено в коді · ⚠️ НЕ перевірено (немає доступу до прод).

## ▶ ОСНОВНИЙ ШЛЯХ: один скрипт `deploy.sh` (коміт d1f3a07 у PR)
Скрипт робить усе нижче (п.3–9) автоматично з автовідкатом. Ручні кроки — лише як fallback.

**Підготовка (один раз, до запуску):** у `.env` поруч із compose:
```
DUTY_ANNOUNCE_CHANNELS=C0XXXXXXX,C0YYYYYYY   # ID каналів; бот запрошений (/invite)
DUTY_ANNOUNCE_TIME=09:00
DUTY_ANNOUNCE_ENABLED=1
```
**Запуск на прод-хості** (поки PR не змерджено, скрипта ще немає в робочій копії, тому беремо його з гілки):
```bash
cd /opt/oncall-app-5
git fetch origin
git show origin/fix/oncall-schedule-logic:deploy.sh > /tmp/deploy.sh
ONCALL_REPO_DIR=$PWD bash /tmp/deploy.sh fix/oncall-schedule-logic --dry-run            # репетиція, прод не чіпає
ONCALL_REPO_DIR=$PWD bash /tmp/deploy.sh fix/oncall-schedule-logic --no-announce-today  # бойовий запуск
```
Після мерджу: `./deploy.sh` (ref за замовчуванням `grok-1.0.0`). **Увага:** до мерджу `grok-1.0.0` = стара версія — передавайте ref явно.

**Що робить скрипт:**
1. Префлайт: docker/compose/git, контейнер `oncall_app_5` працює, БД існує, немає незакомічених змін tracked-файлів, ≥2 ГБ вільного місця, `SLACK_BOT_TOKEN` задано; попередження, якщо `DUTY_ANNOUNCE_CHANNELS` порожня або з `#назвами`, якщо `DB_ADMIN_PASSWORD`/`WEBHOOK_SECRET` дефолтні, і якщо зараз ≥ 09:00 без `--no-announce-today`.
2. Бекап: `sqlite3 .backup` → `../oncall-backups/oncall-<TS>.db` (якщо sqlite3 нема на хості — через тимчасовий контейнер `alpine` + apk sqlite), `integrity_check`, звірка кількості shifts, sha256.
3. Тег відкату `oncall-app:rollback-<TS>` для поточного образу; все записується в `../oncall-backups/rollback-<TS>.env`.
4. `git fetch`, обчислення цільового коміту; код береться через `git archive` у тимчасовий каталог (робоча копія прод ще не змінюється).
5. `go vet` + `go test` у `golang:1.22-alpine` (CGO). Якщо падає — вихід, **прод не змінено**.
6. `docker build -t oncall-app:<sha12>`. Якщо падає — **прод не змінено**.
7. Запам'ятовує сьогоднішню пару (sqlite, Київська дата).
8. `git checkout --detach <коміт>`, генерує `.deploy-override.yml` (`image: oncall-app:<sha12>`), опційно позначає сьогоднішнє оголошення як «вже відправлене» (`--no-announce-today`), `docker compose up -d --no-build --no-deps app`.
9. Healthcheck (до 90 с, HTTP від :8085 усередині контейнера), образ = новий, немає panic/fatal у логах, колонка `is_manual` є, сьогоднішня пара не змінилась. **Будь-яка помилка після п.8 → автовідкат**: stop app, відновлення БД з бекапу (видаляються -wal/-shm), `git checkout` попереднього коміту, запуск `rollback-<TS>`, вихід з кодом 1.
Лог: `deploy-<TS>.log` у каталозі репозиторію.

**Параметри:** `REF` (позиційний), `--dry-run` (п.1–7 без змін: без бекапу, тегування, fetch, тестів і збірки — лише перевірки та друк команд), `--no-announce-today`, `--skip-tests` (не рекомендовано). Env: `ONCALL_CONTAINER`, `ONCALL_BACKUP_DIR`, `ONCALL_MIN_FREE_MB`, `ONCALL_HEALTH_TIMEOUT`.

**Нюанси скрипта:**
- Надалі app запускається через `-f docker-compose.yml -f .deploy-override.yml`. Звичайний `docker compose up -d --build` збере образ за старою схемою (без override) — це безпечно, але тег-історія буде лише через скрипт.
- Ручні правки на майбутні дні мають `is_manual=0` (див. ризики) — скрипт цього не виправляє.
- shellcheck: чисто. Скрипт **не запускався проти реального docker/прод** (у мене немає docker); перевірено лише синтаксис, shellcheck і ранній вихід префлайту.
- Помилка під час відкату (контейнер не піднявся) — скрипт пише 🔥 і лишає дані для ручного відкату (розділ 9).

---
# FALLBACK: ручні кроки

## 0. Що відомо про прод
- ⚠️ Каталог прод: `/opt/oncall-app-5` (з `DEPLOY_PORT85.md`), деплой: `docker compose up -d --build`. Перевірте на хості.
- ✅ Контейнери: `oncall_app_5` (Go, :8085) та `oncall_nginx_5` (85→443). Мережа `opsnet` (external).
- ✅ SQLite: `DB_PATH=/app/data/oncall.db`, bind-mount `./data:/app/data` → на хості `/opt/oncall-app-5/data/oncall.db` (+ `-wal`, `-shm`, режим WAL).
- ✅ У compose немає `image:` — образ збирається з тегом за замовчуванням (`<project>-app`), тож **старий образ перезаписується**. Нижче — ручне тегування для відкату.
- ✅ Логи: `docker logs oncall_app_5` + `/var/log/oncall-app-5/app.log`.

## 1. Міграції БД (✅ код `main.go`, `schedule_balance.go`, `handlers_duty_announce.go`)
Застосовуються **автоматично при старті**, усі адитивні:
| Зміна | Як | Ідемпотентність |
|---|---|---|
| `shifts.is_manual INTEGER NOT NULL DEFAULT 0` | `ALTER TABLE ADD COLUMN`, помилка ігнорується | повторний запуск → «duplicate column», ігнор ✅ |
| `duty_balance` | `CREATE TABLE IF NOT EXISTS` (в `initDB`) | ✅ |
| `duty_announce_sent (day, channel, sent_at)` | `CREATE TABLE IF NOT EXISTS` (фонова горутина, ~9 с після старту) | ✅ |
Інших змін схеми немає (нових ALTER/CREATE в diff більше немає). Даних не видаляє.
- Ризик: SQLite `ADD COLUMN ... NOT NULL DEFAULT 0` безпечний (константний дефолт). Відкат кодом не видаляє колонку/таблиці — старий код їх ігнорує ⚠️ (старий `INSERT INTO shifts` без `is_manual` працює завдяки DEFAULT; не перевірено на прод-даних). Для чистоти відкату — відновлення бекапу.
- ⚠️ **Усі наявні рядки отримають `is_manual=0`**, тобто попередні ручні правки адміна на майбутні дні **не захищені** від перепланування (при затвердженні відсутності, зміні складу, «перерахувати вперед»). Сам старт їх не змінює (див. п.2).

## 2. Поведінка при першому старті (✅ код)
1. `initDB` → міграції.
2. `shiftHorizonLoop` → `planShifts(today, fillOnly=true)`: **лише заповнює відсутні дні** від київського сьогодні до кінця наступного місяця. Наявні дні (включно з сьогодні та майбутніми) **не переписуються**, минуле не чіпається. Повтор щогодини.
3. Ранковий дайджест (DM) — як і раніше, за налаштуванням `morning_duty_time` (деф. 08:00) з вікном повторів; маркер `morning_duty_last` у `app_settings` вже є (⚠️ якщо старий код сьогодні вже відправив і записав маркер — повтору не буде; не перевірено, чи старий код писав той самий ключ — перевірте SQL у п.3).
4. **Оголошення в канали**: `DUTY_ANNOUNCE_ENABLED` за замовчуванням **=1**, канали деф. `#devops-pm-direct,#devops_team`. Якщо старт **після 09:00 Києва** — пост піде **одразу** (~10–40 с після старту) в обидва канали і далі ретраї до кінця дня. Таблиця нова → «сьогодні ще не відправлено».
   **Рекомендація:** перший старт з `DUTY_ANNOUNCE_ENABLED=0`, або деплой до 09:00 (тоді перший пост — штатно о 09:00). Нижче варіант: деплой вдень з `=0` і ввімкнути наступним рестартом увечері/зранку до 09:00 — але це другий рестарт. **Для одного заходу:** деплоїти ~08:30–08:50 Києва з `ENABLED=1` (після вікна дайджесту не залежить), або будь-коли з `ENABLED=1`, якщо ви згодні на одразу пост сьогодні (це навіть корисна перевірка).

## 3. Пре-чеки (на прод-хості)
```bash
cd /opt/oncall-app-5
git status --short; git rev-parse --abbrev-ref HEAD; git log -1 --oneline   # очікуємо grok-1.0.0 @ e1e8d06
docker compose ps
docker inspect oncall_app_5 --format '{{.Image}} {{.Config.Image}}'
df -h .                                     # місце під бекап і образ
ls -la data/                                # oncall.db, -wal, -shm
cat .env 2>/dev/null | grep -E 'SLACK_BOT_TOKEN|DUTY_' | sed 's/=.*/=<set>/'
command -v sqlite3 || echo "sqlite3 відсутній на хості"
# стан для порівняння після деплою:
sqlite3 -readonly data/oncall.db "SELECT date,primary_user,backup_user FROM shifts WHERE date>=date('now','-7 day') ORDER BY date LIMIT 50;" > /tmp/shifts_before.txt
sqlite3 -readonly data/oncall.db "SELECT key,value FROM app_settings WHERE key LIKE 'morning_duty%';"
```
Slack: отримайте **ID каналів** (`C…`) для `#devops-pm-direct` і `#devops_team` (Slack → канал → About → Channel ID) і запросіть бота: `/invite @<bot>` в обох. Бот потребує `chat:write`. ⚠️ Не перевірено, чи бот уже там.

## 4. Бекап БД
```bash
TS=$(date +%Y%m%d-%H%M); mkdir -p /opt/oncall-backups
# онлайн-копія з урахуванням WAL (бажано):
sqlite3 data/oncall.db ".backup '/opt/oncall-backups/oncall-$TS.db'"
# якщо sqlite3 нема на хості — через контейнер не вийде (в образі лише sqlite-libs); тоді копія після зупинки (п.6):
#   docker compose stop app && cp -a data/oncall.db* /opt/oncall-backups/ ...
sqlite3 /opt/oncall-backups/oncall-$TS.db "PRAGMA integrity_check; SELECT count(*) FROM shifts; SELECT count(*) FROM users;"
# очікуємо: ok + ненульові лічильники, порівняти з живою БД
sha256sum /opt/oncall-backups/oncall-$TS.db
```

## 5. Збірка образу з можливістю відкату
```bash
# зберегти поточний образ під тегом відкату
OLD=$(docker inspect oncall_app_5 --format '{{.Image}}')
docker tag "$OLD" oncall-app:rollback-e1e8d06
git fetch origin
git checkout fix/oncall-schedule-logic && git pull --ff-only origin fix/oncall-schedule-logic   # або grok-1.0.0 після мерджу
git log -1 --oneline        # fd910d5
docker compose build app    # контейнер ще працює старий — простою нема
docker tag $(docker compose images -q app 2>/dev/null || echo "<project>-app") oncall-app:fd910d5 2>/dev/null || true
```
⚠️ Назва образу compose (`oncall-app-5-app` тощо) залежить від імені проєкту — перевірте `docker images`.

## 6. Env
Додати в `.env` (поруч із compose):
```
DUTY_ANNOUNCE_ENABLED=1          # або 0 — див. п.2
DUTY_ANNOUNCE_CHANNELS=C0XXXXXXX,C0YYYYYYY
DUTY_ANNOUNCE_TIME=09:00
```

## 7. Рестарт (одна команда)
```bash
docker compose up -d --no-deps app
```
(nginx не чіпаємо; простій ~кілька секунд.) Якщо sqlite3 на хості відсутній і бекап робиться холодним: `docker compose stop app && cp -a data/oncall.db* /opt/oncall-backups/ && docker compose up -d --no-deps app`.

## 8. Smoke-чеки (перші 5 хв)
```bash
docker logs --since 5m oncall_app_5 | grep -Ei 'sqlite:|schema|shifts plan|horizon|duty announce|digest|panic|error'
# очікуємо: "sqlite: /app/data/oncall.db", "shifts plan (horizon): ... fill_only=true written=N", без panic
sqlite3 -readonly data/oncall.db "PRAGMA table_info(shifts);" | grep is_manual
sqlite3 -readonly data/oncall.db ".tables" | tr ' ' '\n' | grep -E 'duty_balance|duty_announce_sent'
sqlite3 -readonly data/oncall.db "SELECT date,primary_user,backup_user FROM shifts WHERE date>=date('now','-7 day') ORDER BY date LIMIT 50;" > /tmp/shifts_after.txt
diff /tmp/shifts_before.txt /tmp/shifts_after.txt && echo "минуле/сьогодні/наявне — без змін"
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1:85/
```
UI: сторінка графіка — сьогоднішня пара як до деплою, минулі дні без змін, підсвітка «сьогодні» за Києвом. Якщо `ENABLED=1` і після 09:00 — перевірити пости в обох каналах і `SELECT * FROM duty_announce_sent;`. Помилка `channel_not_found`/`not_in_channel` у лозі → бот не запрошений/невірний ID (ретраї тривають, нічого не ламається).

## 9. Відкат
```bash
docker compose stop app
cp -a /opt/oncall-backups/oncall-$TS.db data/oncall.db && rm -f data/oncall.db-wal data/oncall.db-shm
git checkout grok-1.0.0     # e1e8d06
docker tag oncall-app:rollback-e1e8d06 <compose-image-name>:latest   # ⚠️ ім'я з `docker images`
docker compose up -d --no-deps app     # БЕЗ --build
```
Увага: відновлення бекапу втрачає зміни, внесені після бекапу (нові звернення/задачі). Якщо проблема лише в коді — можна відкотити тільки образ, залишивши БД (нові колонка/таблиці старим кодом ігноруються ⚠️ не перевірено на проді).

## 10. Ризики (підсумок)
- 🟠 До мерджу `deploy.sh` без аргументу деплоїть `grok-1.0.0` (стару версію) — передавайте `fix/oncall-schedule-logic`.
- 🟡 `deploy.sh` не прогнаний на справжньому docker-хості — почніть з `--dry-run`.
- 🟡 `--no-announce-today` вимагає, щоб ваші `DUTY_ANNOUNCE_CHANNELS` у `.env` точно збігались із тими, що бачить застосунок (інакше пост піде).
- 🔴 Оголошення за замовчуванням увімкнене; старт після 09:00 → миттєвий пост у 2 канали.
- 🟠 Старі ручні правки не мають `is_manual=1` — наступне перепланування (відсутність/склад/перерахунок) може їх переписати. За потреби після деплою: `UPDATE shifts SET is_manual=1 WHERE date>=date('now') AND <відомі ручні дати>;`.
- 🟠 Канали за назвою (`#name`) можуть не спрацювати — використовуйте ID.
- 🟡 compose перезаписує тег образу — без ручного `docker tag` відкат образу неможливий без перезбірки.
- 🟡 `go test -race` падає (наявна гонка в `init()` дайджесту) — на прод не впливає, але відомо.
- ⚠️ Не перевірено: реальний шлях/ім'я проєкту, наявність sqlite3 на хості, членство бота в каналах, значення `.env`, ключі `app_settings` на проді.
