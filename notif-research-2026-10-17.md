# WhatsApp і Telegram як канали on-call сповіщень для DevOps Hub / oncall-system

Дата дослідження: 2026-10-16 (Europe/Kiev). Лише аналіз: жодну систему не змінювали, жодних повідомлень не надсилали.
Легенда: **Факт** — підтверджено першоджерелом (посилання + «перевірено 2026-10-16»); **Гіпотеза** — висновок/припущення з рівнем впевненості; **Рекомендація** — пропозиція для команди.
Методика: сторінки developers.facebook.com віддають 403 для WebFetch, тому ті самі публічні сторінки завантажено через curl (публічний fallback). core.telegram.org/bots/faq — через WebFetch, решта Telegram — через curl. Документація Meta переїхала на `developers.facebook.com/documentation/business-messaging/whatsapp/...` (старі `/docs/whatsapp/...` ведуть туди ж).

## Короткі відповіді на ключові питання

| Питання | WhatsApp (Cloud API) | Telegram Bot API |
|---|---|---|
| Чи потрібні затверджені шаблони? | **Так**, для будь-якого повідомлення поза 24-год вікном (а on-call пінг — майже завжди поза вікном). Шаблон має бути в статусі `APPROVED`. | **Ні**, шаблонів/модерації немає. |
| Чи може бізнес/бот написати першим? | **Так, але лише шаблоном** і лише користувачу, який дав opt-in. Вільний текст — тільки в межах 24-год вікна після повідомлення від користувача. | **Ні** в приватний чат: користувач має першим написати боту (/start) або додати його в групу. У групу/канал, де бот є учасником/адміном — так. |

---

## 1. WhatsApp Business Platform

### 1.1 Cloud API vs On-Premises, BSP
- **Факт.** On-Premises API: остання підтримувана версія клієнта спливла 23.10.2025 — тобто On-Prem фактично знято з підтримки; для нових інтеграцій лишається Cloud API. https://developers.facebook.com/docs/whatsapp/on-premises/sunset/ — перевірено 2026-10-16.
- **Факт.** Для прямого розробника (власна компанія) рекомендований тип токена — System User access token; для Tech Provider — Business Integration System User token; також існують Solution Partners (BSP). https://developers.facebook.com/documentation/business-messaging/whatsapp/access-tokens — перевірено 2026-10-16.
- **Гіпотеза (впевненість: середня).** BSP (Twilio, 360dialog тощо) спрощують онбординг, але додають власну націнку поверх тарифу Meta; для внутрішнього інструменту прямий Cloud API, ймовірно, достатній.

### 1.2 Верифікація бізнесу і номер телефону
- **Факт.** Нові business portfolio мають messaging limit 250; підняти до 2 000 можна через scaling path — зокрема Business Verification (або верифікацію партнером). https://developers.facebook.com/documentation/business-messaging/whatsapp/messaging-limits — перевірено 2026-10-16.
- **Факт.** Номер має бути зареєстрований для Cloud API; номер, що вже використовується у звичайному WhatsApp, не можна зареєструвати, доки його там не видалено; після реєстрації номер не працює у WhatsApp Messenger; short codes не підтримуються (потрібен код країни й регіону); стаціонарний номер «Not Recommended»; потрібен display name; статус номера має бути «connected». https://developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/phone-numbers — перевірено 2026-10-16.

### 1.3 Шаблони, категорія utility, затвердження, 24-год вікно
- **Факт.** Шаблони — єдиний тип повідомлень, які можна надсилати поза customer service window; категорії: Marketing, Utility, Authentication. https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing — перевірено 2026-10-16.
- **Факт.** Шаблони автоматично проходять review після створення/редагування; надсилати можна лише зі статусом `APPROVED`; статус може змінитися через якість/скарги (вебхук `message_template_status_update`). https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/overview — перевірено 2026-10-16.
- **Факт.** Бізнес відповідає за перевірку категорії, присвоєної шаблону, і платить за категорію на момент використання. https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing — перевірено 2026-10-16. (Правила категоризації: https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/template-categorization — перевірено 2026-10-16.)
- **Факт.** Customer service window — 24 години від повідомлення/дзвінка користувача, оновлюється при кожному новому повідомленні; non-template (вільний текст) можна слати лише всередині вікна. https://developers.facebook.com/documentation/business-messaging/whatsapp/messages/send-messages — перевірено 2026-10-16.
- **Гіпотеза (впевненість: висока).** Сповіщення «ваша зміна починається о …/вас викликано на інцидент» за змістом підпадає під utility (транзакційне, без маркетингу), але фінальну категорію визначає Meta.

### 1.4 Opt-in
- **Факт.** Бізнес зобов'язаний отримати opt-in до надсилання; opt-in може бути загальним (не обов'язково саме для WhatsApp), за умови дотримання місцевого законодавства; треба чітко вказати, що людина погоджується, і назву бізнесу. https://developers.facebook.com/documentation/business-messaging/whatsapp/getting-opt-in — перевірено 2026-10-16.
- **Рекомендація.** Збирати явну згоду чергових у самому DevOps Hub (чекбокс + номер), зберігати дату згоди й мати відписку.

### 1.5 Ціноутворення і тариф для України
- **Факт.** З 01.07.2025 Meta тарифікує per-message: платно лише доставлені шаблонні повідомлення; ставка залежить від категорії та коду країни отримувача; усі non-template повідомлення безкоштовні (лише у вікні); utility-шаблони, доставлені у відкритому вікні, безкоштовні; є знижки за обсягом (volume tiers) для utility/authentication. https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing — перевірено 2026-10-16.
- **Факт.** Україна (+380) раніше належала до регіону «Rest of Central and Eastern Europe»; сторінка оголошує, що з 01.10.2026 Україна виноситься в окремий ринок з вищими ставками utility/authentication. Там само — та сама сторінка (розділ «Rate card updates effective October 1, 2026»).
- **Факт.** Офіційна rate card USD «effective October 1, 2026» (XLSX за посиланням «USD rates» на сторінці pricing): **Україна — Utility $0.0298 за повідомлення**, Marketing $0.086, Authentication $0.0298, Authentication-International $0.0746. Для порівняння «Rest of Central & Eastern Europe» — Utility $0.0212. Volume tiers для України (utility): $0.0298 до 100 000/міс, далі $0.0283 (−5%) і нижче. Посилання на rate card: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing#rate-cards-and-volume-tiers (інтерактивно також https://business.whatsapp.com/products/platform-pricing#rates) — перевірено 2026-10-16.
- **Гіпотеза (впевненість: висока).** Орієнтовно: 10 чергових × ~3 сповіщення/день × 30 днів ≈ 900 шаблонів/міс ≈ $27/міс (без податків/націнки BSP). Якщо черговий відповів у чаті (відкрив вікно), подальші utility-повідомлення протягом 24 год безкоштовні.

### 1.6 Ліміти і пропускна здатність
- **Факт.** Messaging limit (на рівні business portfolio, спільний для всіх номерів): 250 → 2 000 (scaling path) → 10 000 → 100 000 → Unlimited (автомасштабування). Ліміт стосується шаблонних повідомлень унікальним користувачам. https://developers.facebook.com/documentation/business-messaging/whatsapp/messaging-limits — перевірено 2026-10-16.
- **Факт.** Throughput: до 80 msg/s на номер за замовчуванням, до 1 000 msg/s автоматичним апгрейдом (умови — unlimited ліміт і 100K+ унікальних отримувачів за 24 год); перевищення → помилка `130429`; надто часті повідомлення одному користувачу → pair rate limit. https://developers.facebook.com/documentation/business-messaging/whatsapp/throughput — перевірено 2026-10-16.
- **Гіпотеза (впевненість: висока).** Для on-call (десятки отримувачів) ліміт 250 і 80 msg/s не є обмеженням; ризик — лише pair rate limit при «спамі» одного чергового ескалаціями.

### 1.7 Групи
- **Факт.** Groups API доступний лише бізнесам з Official Business Account (OBA, «синя галочка»); групи — invite-only (учасник приєднується за посиланням-запрошенням); максимум **8 учасників**. https://developers.facebook.com/documentation/business-messaging/whatsapp/groups — перевірено 2026-10-16.
- **Факт.** OBA вимагає верифікованого business portfolio і двоетапної перевірки номера (плюс інші критерії). https://developers.facebook.com/documentation/business-messaging/whatsapp/official-business-accounts — перевірено 2026-10-16.
- **Гіпотеза (впевненість: середня).** Надсилати в довільні існуючі групи команди WhatsApp не можна; практично для on-call групи WhatsApp малопридатні (OBA + ліміт 8).

### 1.8 Приватність / GDPR
- **Гіпотеза (впевненість: середня).** Номери телефонів працівників — персональні дані; передача в Meta (Cloud API хоститься Meta) вимагає правової підстави (згода/легітимний інтерес), оновлення внутрішньої політики приватності та DPA з Meta/BSP. Змісту інцидентів (імена клієнтів, хости, секрети) у шаблонах уникати.
- **Рекомендація.** У повідомлення класти лише мінімум (сервіс, severity, посилання в DevOps Hub з авторизацією), не персональні дані чи секрети.

### 1.9 Що потрібно для інтеграції
- **Факт.** Meta developer account → Meta app (Business) → WhatsApp Business account (WABA) у business portfolio → номер (тестовий або власний, реєстрація через register endpoint) → System User access token → webhook endpoint (HTTPS) для статусів доставки/прочитання і вхідних. https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started — перевірено 2026-10-16; токени — https://developers.facebook.com/documentation/business-messaging/whatsapp/access-tokens — перевірено 2026-10-16.
- **Рекомендація.** Go-бекенд: окремий `Notifier` (інтерфейс поруч із Slack/Telegram), токен — у secret manager, ідемпотентність і ретраї на `130429`, обробка вебхуків статусу для «доставлено/прочитано» в логіці ескалації.

## 2. Telegram Bot API

- **Факт.** Бот не може почати розмову: користувач має додати бота в групу або написати йому першим; можна знайти бота за username або через t.me/bot_username. https://core.telegram.org/bots — перевірено 2026-10-16.
- **Факт.** Deep linking `https://t.me/your_bot?start=<param>` передає параметр у `/start` — зручно для прив'язки акаунта чергового до користувача DevOps Hub. https://core.telegram.org/bots/features — перевірено 2026-10-16.
- **Факт.** Боти отримують усі повідомлення з каналів, де вони учасники; privacy mode увімкнено за замовчуванням (крім ботів-адмінів), бот бачить лише команди/відповіді до себе. https://core.telegram.org/bots/features та https://core.telegram.org/bots/faq — перевірено 2026-10-16.
- **Гіпотеза (впевненість: висока).** Для постингу в канал бот має бути адміністратором каналу з правом публікації; у групу — учасником. (Для сповіщень privacy mode не заважає — він впливає лише на те, що бот читає.)
- **Факт.** Ліміти (FAQ): в одному чаті — не більше ~1 msg/s (короткі сплески допустимі, далі 429); у групі — не більше 20 повідомлень/хв; масові розсилки — ~30 msg/s. https://core.telegram.org/bots/faq — перевірено 2026-10-16.
- **Факт.** Повідомлення ботам безкоштовні; paid broadcasts (через @BotFather) — до 1 000 msg/s, 0.1 Star за кожне повідомлення понад безкоштовні 30/s, вимагає ≥100 000 Stars на балансі і ≥100 000 MAU. https://core.telegram.org/bots/faq — перевірено 2026-10-16.
- **Факт.** Форматування: `parse_mode` MarkdownV2 або HTML; у MarkdownV2 символи `_ * [ ] ( ) ~ \` > # + - = | { } . !` поза сутностями треба екранувати `\`, всередині `pre/code` — `` ` `` і `\`. https://core.telegram.org/bots/api#formatting-options — перевірено 2026-10-16.
- **Факт.** Кожен бот має унікальний токен (вигляду `123456:ABC-...`), який передається в URL запиту; усі запити — через HTTPS. https://core.telegram.org/bots/api — перевірено 2026-10-16. Для вебхуків Telegram радить секретний шлях у URL. https://core.telegram.org/bots/faq — перевірено 2026-10-16.
- **Рекомендація.** Для Go: HTML parse_mode з `html.EscapeString` надійніший за MarkdownV2; токен — у secret manager, ніколи в логах (він у URL!), маскувати URL у логах HTTP-клієнта; при `setWebhook` використовувати `secret_token`; токен перевипускати через @BotFather при підозрі на витік. Черга з per-chat throttling (1/s, 20/min для груп), обробка 429 з `retry_after`, і обробка 403 (користувач заблокував бота) → fallback на Slack.

## 3. Альтернативи (коротко)
- **Viber — Факт.** З 05.02.2024 боти Viber створюються лише на комерційних умовах (через Rakuten Viber або партнерів). https://developers.viber.com/docs/api/rest-bot-api/ — перевірено 2026-10-16.
- **Signal** — офіційного бізнес/бот API на першоджерелах не знайдено; не включаю як підтверджену альтернативу (впевненість у відсутності: середня).

## 4. Порівняльна таблиця

| Критерій | WhatsApp Cloud API | Telegram Bot API |
|---|---|---|
| Вартість | Платно за доставлений шаблон поза вікном: UA utility **$0.0298** (з 01.10.2026); у 24-год вікні — безкоштовно | Безкоштовно (paid broadcasts лише для >30 msg/s, нам не потрібно) |
| Зусилля на налаштування | Високі: Meta app, WABA, business verification, окремий номер, затвердження шаблонів, system user token, webhook, opt-in | Низькі: @BotFather → токен; користувач натискає /start (deep link) |
| Відправка в групу | Лише з OBA, invite-only, ≤8 учасників | Так, якщо бот учасник (група) / адмін (канал) |
| Потрібен opt-in користувача | Так (політика Meta) | Фактично так: користувач мусить почати чат/додати бота |
| Чи може написати першим | Так, лише затвердженим шаблоном | Ні в приват; так у групу/канал з ботом |
| Шаблони | Обов'язкові поза 24-год вікном | Немає |
| Ліміти | 250 унікальних/24 год стартово → до unlimited; 80 msg/s на номер | ~1 msg/s на чат, 20/хв у групі, ~30 msg/s загалом |

## 5. Рекомендації для команди
1. **Рекомендація.** Основний мобільний канал — **Telegram** (вже є дзеркалювання): безкоштовно, швидко, підтримує групу чергових. Додати онбординг через deep link `?start=<одноразовий код>` для прив'язки особистого чату.
2. **Рекомендація.** Slack лишити джерелом правди; Telegram — паралельний push; при 403/429-вичерпанні ретраїв — fallback/ескалація (PagerDuty дзвінок/SMS, якщо використовується).
3. **Рекомендація.** WhatsApp — лише якщо є вимога бізнесу (напр. частина чергових не має Telegram). Тоді: прямий Cloud API, 1–2 utility-шаблони («Нова зміна», «Інцидент SEV-x»), бюджет ~$0.03/повідомлення, без груп.
4. **Рекомендація.** У жодному каналі не передавати секрети/персональні дані — лише короткий опис і посилання в DevOps Hub.
5. **Рекомендація.** Переглянути тарифи Meta перед запуском — Україна щойно (01.10.2026) стала окремим ринком, ставки змінюються щокварталу за pricing calendar.
