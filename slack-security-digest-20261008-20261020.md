# Дайджест Slack по безпеці: 08.10.2026 00:00 – 20.10.2026 ~18:20 (Київ, UTC+3)
Джерело: Slack MCP (vidmindtalk), лише читання. ID користувачів і каналів замасковано; секретів, паролів і токенів тут немає; ID ключів доступу скорочено.

## Доступ до каналів
- #secret (приватний) — доступний, прочитано весь період (≈25 повідомлень у каналі + 7 ключових тредів)
- #devops-pm-direct (приватний) — доступний, прочитано весь період (≈207 повідомлень + 8 тредів)
- #security_report (приватний) — доступний, прочитано весь період (≈157 повідомлень, переважно звіти бота/Datadog + 4 треди)
- #guardduty-alerts (ID відомий, C0C6…X24) — доступний, 9 сторінок, ≈868 повідомлень від вебхука + повідомлення людей
- Помічено новий канал #security_audit (створено 12.10, Andrii Lytvyn) — не читав, бо він не входив у завдання

## 1. jenkins-legacy / Jenkins
- ФАКТ 08.10 00:46 (Oleg Cherep): GD HIGH Persistence:EC2/BootOrLogonInitializationScripts (IAM user `jenkins`, ключ AKIAJJDS…, IP 54.72.145.185) — найімовірніше легітимний Terraform apply (джоба preprod2-up-down → preprod2-blizzard; впевненість ~75%). Проблема: apply робив `jenkins-legacy`, який вважається скомпрометованим; досі працює, має ключ 2017 року з повними правами EC2/S3; у SG `SystemWide-OA` для нього відкриті всі TCP-порти. Рекомендовано: snapshot + ізоляція; деактивувати ключ AKIAJJDS… після переходу CI на вужчу роль; закрити Redis/Mongo на VPN-сервері від інтернету; змінити пароль haproxy stats (лежить відкритим текстом у user-data).
- ФАКТ 19.10 00:34 (Oleg Cherep): Jenkins 2.414.1 уразливий до CVE-2024-23897 (CVSS 9.8, є в CISA KEV); рекомендовано оновлення до LTS 2.580.1.
- ФАКТ 19.10 (Oleksandr Baiduzh): додав basic auth на nginx для Jenkins; закрито прямий доступ до backend-порту 8080 з інших хостів (VID-42924, частина скоупу).
- ФАКТ 20.10 15:08 (#guardduty-alerts, AWS audit): `jenkins` (той самий ключ AKIAJJDS…, IP 34.252.219.252, Terraform) — CreateRole → AccessDenied. Тобто станом на 20.10 ключ 2017 року ВСЕ ЩЕ АКТИВНИЙ (права вже частково урізані).
- ФАКТ 20.10 17:18: GD MEDIUM Persistence:EC2/ExternalRemoteServices (EC2SecurityGroupPublicSSH) від ролі development_servers з IP 54.72.145.185 (IP jenkins-legacy).
- ВІДКРИТО: немає підтвердження про snapshot/ізоляцію jenkins-legacy чи деактивацію ключа; оновлення Jenkins не підтверджене.

## 2. OpenVPN
- ФАКТ 08.10 00:21–00:46: GD HIGH Trojan:EC2/PhishingDomainRequest!DNS на i-0dbf…efb (це OfficeVPN). Домен malvertising (somepossibility[.]com). Сервер не зламаний; «Sophos» — це назва фіду GuardDuty, а не антивірус (Oleg Cherep). 09.10: ще DriveBySourceTraffic!DNS (HIGH) і UnusualDNSResolver 213.111.126.150 (MEDIUM, Bilink, UA).
- ФАКТ 14.10 03:08 (звіт Oleg Cherep): уже 6 запитів на фішинговий домен; скан диска VPN-сервера CLEAN → проблема на боці клієнта; треба знайти його в журналі OpenVPN. У VPC немає DNS query logs і flow logs.
- ФАКТ 14.10: Tymur Zaidullin погодив пропозицію Oleg Cherep — обмежити VPN лише робочою мережею, без виходу в інтернет.
- ФАКТ 12.10 і 20.10 (#secret, Roman Soproniuk / Artem Lokotosh): тисячі (≈14 тис.) невдалих входів у pmongo під старим `rootwildfire` з NoSQLBooster (macOS) через 10.0.31.46 — це внутрішня IP VPN-сервера (NAT), конкретного користувача не встановлено. 20.10 частину спроб Artem пояснив своїми старими кредами з ansible vault (datagate); інші «точно не я».
- ФАКТ 14.10 (Dmytro Alieksieiev): люди без доступу до VPN ходять на VPN-хост через сусідній інстанс (jenkins worker) зі спільним ключем master-3.pem — ризикова практика.
- ВІДКРИТО: заражений клієнт VPN не знайдено; персональна атрибуція через VPN неможлива (спільний NAT); спільні облікові записи БД.

## 3. Ротації секретів / облікових даних
- ФАКТ 14.10 03:48 (Oleg Cherep): аналіз SSM завершено — 118 SendCommand + 611 GetCommandInvocation (нападник читав вивід: Mongo keyFile, /proc/*/environ, SCRAM-хеші). Parameter Store: 15 розшифрованих читань, 8 параметрів (Mongo admin для prod/preprod/content-manager, Mongo URI, Firebase admin SDK) — усі 8 потрібно ротувати.
- ФАКТ 14.10 04:22 (Oleg Cherep): «інцидент не закрито; вважаємо, що зловмисник досі в оточенні → уся робота з ротації скомпрометована» (це оцінка/гіпотеза автора).
- ФАКТ 18.10 14:01 (#secret): що міняти — роль development_servers, Mongo keyFile (+ аудит дій під `__system`), усі паролі PG titan, витеклі секрети застосунків, ключ Datadog. Нових користувачів, cron, systemd немає; authorized_keys звірити окремо. Чекає на пріоритизацію/дозвіл.
- ФАКТ 19.10 00:34: підтверджено 44 секрети + 8 параметрів = 52/52. Ще 2 вкрадені ключі (…FEPKSUHK, …N3426NJJ) треба додати в IOC. `/api/internal/**` захищений лише Basic auth з паролем, зашитим у код.
- ФАКТ 19.10 01:03: спроба входу в CyberArk Kyivstar SFE з вебшела під 5 обліковими записами (session_introspector, KYIVSTAR\gateway, oleg.gutsalo, KYIVSTAR\trino, analytics); успіх невідомий. Рекомендовано змінити паролі цим 5 і попросити Київстар перевірити журнали Logon за 29.09 15:13–15:37.
- ФАКТ 13–14.10: нові ключі й користувачі flume (vv.berest, y.diduk) — Victor Berest підтвердив, що це планова робота (нові конфіги/ключі, ключі обмежено під кожне оточення).
- ФАКТ 20.10 (Yurii Diduk): бекап playback-session-mongo не виконується з 29.09 (є snapshot від 20.10) — «паролі змінили, але є залежності».
- ФАКТ 16.10 (Oleg Cherep): політика для розробників — лише читання Secrets Manager; створення/зміни робить DevOps. Власника стріму не визначено.
- ВІДКРИТО: немає підтвердження ротації Mongo keyFile, PG titan, ключа Datadog, 8 SSM-параметрів, PSK Zabbix.

## 4. IMDSv2
- ФАКТ 12.10 (Yurii Diduk / Artem Lokotosh / Oleg Cherep): обговорення переходу; Java SDK має підтримувати IMDSv2 (потрібно оновити бібліотеки й AMI); Oleg: «доведеться багато змінювати».
- ФАКТ 18.10 22:09 (за повідомленням 19.10 00:34): IMDSv1 досі дозволений на 27 з 28 інстансів *wildfire — це шлях, яким викрали ключі; він досі відкритий.
- ФАКТ: ролі development_servers та p/s/f/vwildfire мають AdministratorAccess; `AdministratorAccess` на development_servers досі висить (19.10).
- ВІДКРИТО: жодного факту примусового ввімкнення IMDSv2 немає.

## 5. Нові алерти (#guardduty-alerts і #security_report)
GuardDuty (≈868 повідомлень; шум: PortProbe ≈497, ElevationToRoot на i-07d2…5ec ×64 — це netdata на oleg-ec2, очікувано):
- 08.10 00:05 HIGH Persistence:EC2/BootOrLogonInitializationScripts — jenkins (див. п.1).
- 08.10 00:30 / 09.10 20:46 HIGH Trojan Phishing/DriveBy DNS — OfficeVPN (див. п.2).
- 09.10, 13.10, 14.10, 20.10 MEDIUM LateralMovement EC2InstanceSSHKeyPushed: o.cherep (08.10), development_servers (13.10, 7 разів, IP 34.252.219.252), o.baiduzh (14.10, 20 разів), o.kuleba (20.10 17:22) — схоже на адмінів, але для ролі development_servers (скомпрометована роль) потрібне підтвердження.
- 13.10 16:57 MEDIUM InitialAccess:IAM/ValidAccounts; 13.10 вхід без MFA у m.vyshtykaluik — вирішено (MFA налаштовано).
- 13.10 LOW Persistence:IAM/AccountManipulation (IAMAccessKeyCreated, vv.berest — flume, підтверджено).
- 16.10 20:24 WAF: 2 запити з 176.65.144.175 (IOC /24) заблоковано правилом block-dedik-services-limited.
- 20.10 15:08 AWS audit: jenkins CreateRole AccessDenied (ключ досі живий).
- 20.10 17:18 MEDIUM Persistence:EC2/ExternalRemoteServices (публічний SSH у SG) від development_servers з IP jenkins-legacy — НОВЕ, потрібно перевірити.
- 20.10 03:17: o.cherep створив роль GuardDuty S3 Malware Protection (контрольовано).
- Криптомайнінгу та Runtime-подій, окрім ElevationToRoot від netdata, не було.
#security_report:
- 09.10 01:53/02:53/09:54 ЧЕРВОНИЙ «ознаки атаки»: 96.62.224.135 створював акаунти; заблоковано IP, сесії, видалено 18 акаунтів і 17 абонентів (Roman Soproniuk), ендпоінти /subscribers/new і newsubscriber видалено з коду й релізу (Pavlo Piiakivskyi, Roman Soproniuk, Artem Lokotosh).
- 10–19.10: десятки ЖОВТИХ «розвідка/сканування» та ПОМАРАНЧЕВИХ «спроба проникнення» (path traversal на user-activity-gateway, вебшел/session-introspection на pwildfire — усе неуспішне, 4xx/5xx).
- 19.10 13:03: хвиля path traversal (24 запити) — неуспішна; Viktor Tsyhannyk заблокував на WAF php-сканер (UA libredtail) і закрив ALB production-user-activity-gateway дефолтним 403.
- Datadog P1 «ec2-payment error rate» і P2 Portmone — переважно шум; Tymur вимагає прибрати їх або переписати; Volodymyr Bilorus/Andrii Lytvyn прибирають.
- P2 [Security] зміни IAM (CloudTrail) — це роботи y.diduk, vv.berest, v.tsyhannyk, o.cherep.

## 6. Ключові висновки/оновлення (#devops-pm-direct, переважно Oleg Cherep)
- 19.10 02:38 ФАКТ (висока впевненість): ПОВТОРНА АТАКА — 10.10 12:00–13:59 з 96.62.224.135 було 823 відповіді 200 на GET /vidmind-stb-ws/api/v1/subscribers/all (≈801 accountId, ≈1,37 МБ); ендпоінт публічний без авторизації; 11.10 — ще 4 відповіді 200, 17.10 з .203 — 37. 6 POST /logs/loggers з 200 (змінювали рівні логування). Рекомендовано закрити /v1/subscribers/all і /logs/loggers, повернути рівні логування, заблокувати AS207043/AS209413 (40 префіксів, CSV-реєстр готовий).
- 19.10 02:56: правило WAF блокує лише 176.65.144.0/24; решта префіксів DEDIK проходить; 37.114.41.96/28 ніде не заблоковано.
- 19.10 00:44: за CloudTrail 07.09–18.10 після 29.09 18:40 активності нападника в AWS немає (ключ production-epg-ro останнім).
- 19.10: internalzabbix.production вказував на IP нападника ≈12,4 доби (29.09 15:37 – 12.10 01:14); 27 хостів 29.09 відправляли дані агента Zabbix нападнику; запис повернув o.cherep. Zabbix ≈12 діб був «сліпий».
- 19.10: порт 8080 у prod SG sg-55… був відкритий для 0.0.0.0/0 до 29.09 16:21 (закрив Artem Lokotosh). 20.10 Oleksii Kuleba: у SG майже всього prod є прямий вихід 0.0.0.0/0; знаючи публічну IP, CloudFront/WAF можна обійти.
- 19.10: DenyAttackerIP звужено до /32 на 2 ролях (Viktor Tsyhannyk заперечив, що це був він; повернув /24 лише на development_servers; на production-ecs-instance-role і preproduction-ecs-rankmate досі /32 — за його ж виводом). Oleg пропонує єдиний IP set.
- 18.10 23:54 (#secret) ГІПОТЕЗА Oleg Cherep: у звітах SSM-агентів досі раз на годину трапляються команди /dev/tcp до internal.gwildfire — можливе шкідливе ПЗ всередині; джерело не встановлено. Tymur вимагає підтвердження.
- 14.10: термін ~29.10 — історія команд SSM зникне; 16.10 o.cherep додав ir-readonly права на SSM command output (видно в audit).
- 20.10 09:00: хтось почистив бакет, куди писав нападник — «докази знищено»; бакет не чіпати.
- 19.10: Oleksandr Baiduzh — GitLab prod оновлено 11.11.8 → 15.11.13; аудит публічних IP preprod (64 з 88 EC2 з авто-публічними IP), Terraform-патч на рев'ю (VID-42786), apply ще не було; Yurii Diduk — dev переведено на окремі ролі з найменшими привілеями, preprod у роботі (VID-42550).
- 19–20.10: Route53 зона demo.vidmind.com — Oleksii Kuleba знайшов висячі записи (ризик subdomain takeover); Artem Lokotosh вичистив зону, вимкнув 2 CloudFront (cdn/cdn2.demo), видалив бакет vidmind-testing (VID-42956); Oleg поставив логування дій з цими distribution.
- 09–16.10: вимкнення dev/preprod з 22:00 09.10 до 07:00 12.10; Wizzard/DataLake/Hyperion повертали 14–16.10; Hyperion — Oleg: OpenSearch лише з паролем і з однієї IP-адреси.
- 11.10: Pavlo Piiakivskyi вбив пропущену сесію нападника в Redis (запити SocketIO повз балансер).
- 15.10: ELK закритий ззовні (лише VPN) → клієнти не пишуть логи; 17.10 протермінувався сертифікат (попередження Vladyslav Dzinziura).
- 19.10: Artem Lokotosh/Oleksandr Baiduzh хотіли прибрати зовнішні IP з інстансів preprod; тести зупинили, роботи відклали («зміни підозрілі»).
- 17.10: гострий конфлікт Oleg Cherep ↔ Andrii Lytvyn щодо шуму в алертах; Oleg замʼютив канал бота.
- Організаційне: усі дії з безпеки — як задачі (Volodymyr Bilorus, 13.10); Andrii Lytvyn 19–20.10 збирає список зробленого для презентації CEO (четвер 22.10), нагадує, що відповіли не всі.

## 7. Хто що зробив (дати за Києвом)
- Oleg Cherep — 08.10 тріаж jenkins/OpenVPN; 14.10 аналіз SSM; 18–19.10 серія звітів (повторна атака, CyberArk, Zabbix, WAF-реєстр, CVE Jenkins); 12.10 повернув DNS Zabbix; 16.10 права IR на SSM; 20.10 GuardDuty S3 malware role.
- Viktor Tsyhannyk — 09.10 знизив поріг GD у Slack до LOW; 19.10 WAF-блок php-сканера, дефолтний 403 на ALB user-activity-gateway, CIDR нападників у WAF, повернув DenyAttackerIP /24.
- Oleksandr Baiduzh — basic auth nginx Jenkins; GitLab 15.11.13; аудит публічних IP preprod (VID-42786).
- Artem Lokotosh — розслідування спроб входу в pmongo (12.10, 20.10); чистка Route53 demo (19–20.10); раніше закрив 8080 (29.09).
- Yurii Diduk — ролі dev за least privilege, preprod у роботі (VID-42550); ролі в Terraform; інфо про бекапи.
- Victor Berest — flume (нові ключі/конфіги), підтвердив 14.10.
- Pavlo Piiakivskyi / Roman Soproniuk — 09.10 видалення фейкових акаунтів і ендпоінтів; Roman — щогодинні звіти бота, щотижневий звіт (19.10).
- Oleksii Kuleba — аналіз Route53 demo, переробка SG на ipsec, пояснення щодо SG 0.0.0.0/0 (20.10).
- Serhii Semenykhin — збирає списки колекцій Mongo (19.10).

## 8. Відкриті питання / блокери
1. jenkins-legacy досі працює, ключ 2017 року активний (20.10); Jenkins 2.414.1 з CVE-2024-23897 (9.8).
2. IMDSv1 відкритий на 27/28 wildfire; AdministratorAccess на development_servers і *wildfire.
3. /v1/subscribers/all і /logs/loggers — у Slack немає підтвердження, що закрито; 96.62.224.0/24 та інші префікси DEDIK, 37.114.41.96/28 — блокування неповне.
4. Ротації (Mongo keyFile, PG titan, ключ Datadog, 8 SSM-параметрів, 5 облікових записів CyberArk, PSK Zabbix) — не підтверджено.
5. Гіпотеза про постійну присутність (щогодинні команди /dev/tcp) — не підтверджена й не спростована.
6. Термін ~29.10 — вивантажити історію команд SSM.
7. Докази в бакеті нападника знищено; не робиться snapshot хостів перед заміною.
8. SG prod із 0.0.0.0/0, публічні IP у preprod (патч на рев'ю, не застосований).
9. VPN: заражений клієнт не знайдений; спільні облікові записи БД, немає атрибуції.
10. Бекап playback-session-mongo не працює з 29.09.
11. Немає Datadog для preprod (67 інстансів + ECS); моніторинг шумний; власник стріму Secrets Manager не визначений.
12. Новий GD 20.10 17:18 — публічний SSH у SG через development_servers з IP jenkins-legacy — треба перевірити.
