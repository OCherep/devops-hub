# curl з EC2

## Чому висить `https://s.ks.tv/...`
З **самого інстанса** запит на публічне ім’я часто йде hairpin NAT (вихід в інтернет і повернення на свій Elastic IP). Caddy/SG це може тримати вічно — тому `^C`.

Перевіряйте **всередині opsnet**:

```bash
docker exec ops_edge wget -qO- -T 5 http://oncall_nginx_5/api/on-grid
docker exec ops_edge wget -qO- -T 5 http://ops_hub/
curl -sS -m 5 http://127.0.0.1/   # якщо edge слухає :80 тільки внутрішньо — може не бути
```

З ноутбука `https://s.ks.tv/oncall-api/api/on-grid` має відповідати.

## `curl: (60) unable to get local issuer certificate` на `:85`
У контейнері OnCall nginx віддає сертифікат **без проміжного** ZeroSSL (або системний store EC2 його не знає). Браузер на Mac уже ок (є ланцюжок). На EC2:

```bash
curl -sS -m 5 -k https://127.0.0.1:85/api/on-grid
# або внутрішній HTTP
docker exec oncall_nginx_5 wget -qO- -T 5 http://127.0.0.1/api/on-grid
```

Ланцюжок: `fullchain.pem` = `certificate.crt` + `ca_bundle.crt` (install-zerossl.sh).

## Лапки
zsh зʼїдає `?` і `&`. Завжди:

```bash
curl -sS -m 8 'https://s.ks.tv:85/api/data?year=2026&month=9'
```
