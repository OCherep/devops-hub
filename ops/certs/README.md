# ops/certs — SSL/TLS inventory + renew

## Навіщо
На платформі багато сертифікатів (OnCall :85, edge :443, CloudFront/ALB/ACM, історичні LE).
Модуль:

1. **Інвентар + статус** (`inventory.sh` → `status.json`)
2. **Renew** ZeroSSL/LE ACME (`renew-loop.sh`)
3. **Копія PEM** у `/opt/ops/oncall/certs`
4. **Hook ACM** (`hooks/acm-import.sh`) — імпорт PEM у вже існуючий ARN

## Швидкий статус на хості

```bash
cd /opt/ops/certs
chmod +x inventory.sh
# локальні PEM + /etc/letsencrypt
sudo ./inventory.sh

# плюс ACM (усі ISSUED в регіоні)
AWS_REGION=eu-central-1 ./inventory.sh
cat status.json
```

Пороги: `WARN_DAYS=21` (жовтий `expiring`, інакше `ok` / `expired`).

### Let's Encrypt «безліч»

LE **не має** єдиного порталу «всі сертифікати акаунта» без доступу до:

| Де лежить | Як перевірити |
|-----------|----------------|
| Цей EC2 `/etc/letsencrypt/live/*` | `sudo certbot certificates` або `inventory.sh` |
| Інші EC2 / старі інстанси | той самий `certbot certificates` на кожній машині |
| AWS ACM (імпорт або ACM-issued) | `aws acm list-certificates --region …` |
| CloudFront / ALB listener | ACM ARN у listener / distribution |
| Зовнішній випуск (ZeroSSL UI) | ZeroSSL dashboard + локальний PEM |

Масово по доменах (без приватного ключа):

```bash
# дата закінчення з публічного ланцюга
echo | openssl s_client -servername s.ks.tv -connect s.ks.tv:443 2>/dev/null \
  | openssl x509 -noout -issuer -subject -dates
echo | openssl s_client -servername s.ks.tv -connect s.ks.tv:85 2>/dev/null \
  | openssl x509 -noout -issuer -subject -dates
```

Список доменів для регулярної перевірки — файл `domains.txt` (по одному імені на рядок).

## Автооновлення

1. Edge віддає `/.well-known/acme-challenge/` (вже в Caddyfile).
2. `/opt/ops/certs/.env` — `DOMAIN`, `CERT_EMAIL`, `ZEROSSL_EAB_*` або звичайний certbot LE.
3. `docker compose up -d` у `/opt/ops/certs` — цикл кожні `RENEW_INTERVAL_HOURS`.
4. Після renew: PEM → OnCall `certs/` + опційно `hooks/post-renew.sh` / `hooks/acm-import.sh`.

Для **багатьох імен** — або SAN в одному сертифікаті (`-d a -d b`), або окремий рядок у `domains.txt` + цикл у `renew-loop.sh`.

## AWS ACM

ACM сам публічні сертифікати для довільних імен **не renew-ить**, якщо це імпорт.
Стратегія платформи:

- публічні сайти на ALB/CloudFront — **ACM-issued + DNS validation** (AWS renew сам);
- OnCall :85 / внутрішній nginx — **ZeroSSL/LE PEM** + за потреби `import-certificate` в існуючий ARN.

## Відновлення криптоматеріалу зі git stash

**Не коміть і не stash-те `privkey.pem` / `private.key` у git.** Якщо скрипт (не ключ) попав у stash:

```bash
cd /opt/ops/oncall
git stash list
# знайти запис, напр. stash@{0}: local-zerossl

# тільки подивитись файли в stash
git stash show --stat stash@{0}

# відновити скрипт поверх робочого дерева (не ключі)
git stash show -p stash@{0} -- scripts/install-zerossl.sh | git apply --include=scripts/install-zerossl.sh

# або повернути весь stash
git stash pop stash@{0}

# ключі мають лежати лише в ./certs (volume), не в git:
ls -l certs/fullchain.pem certs/privkey.pem certs/s.ks.tv/
```

Якщо **приватний ключ зник** і його не було в stash (так і має бути):

1. ZeroSSL / LE — **re-issue** (новий ключ + новий CRT).
2. Скопіювати в `./certs` через `bash scripts/install-zerossl.sh ./certs/s.ks.tv`.
3. `docker compose up -d --force-recreate nginx`.
4. Старий імпорт в ACM — новий `import-certificate` на той самий ARN.

Перевірка після відновлення:

```bash
openssl x509 -in certs/fullchain.pem -noout -subject -issuer -dates
curl -sS -m 5 -o /dev/null -w '%{http_code}\n' https://s.ks.tv:85/
```
