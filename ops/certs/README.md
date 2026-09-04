# ops/certs — certificate renew module

## Role
- Renew **ZeroSSL** (ACME EAB) for `DOMAIN` (default `s.ks.tv`)
- Copy `fullchain.pem` / `privkey.pem` into OnCall `./certs`
- Placeholder for **AWS Certificate Manager** import later

## Host ports
None. HTTP-01 needs **edge** (Caddy) to serve `/.well-known/acme-challenge/` from shared webroot **or** temporary publish.

### Recommended with edge
Mount the same `certbot_www` volume into Caddy and add:

```caddy
handle /.well-known/acme-challenge/* {
  root * /var/www/certbot
  file_server
}
```

## Env (`/opt/ops/certs/.env`)
```
DOMAIN=s.ks.tv
CERT_EMAIL=ops@s.ks.tv
ZEROSSL_EAB_KID=...
ZEROSSL_EAB_HMAC=...
ONCALL_CERTS_HOST=/opt/ops/oncall/certs
RENEW_INTERVAL_HOURS=12
```

EAB keys: ZeroSSL Developer → ACME.

## Register
`modules.env`:
```
certs|.|main|docker-compose.yml
```
(or path under ops)

```bash
/opt/ops/network.sh
cd /opt/ops/certs && docker compose up -d
```

## Slack BRB status (OnCall)
Bot needs `users.profile:write`. Workspace policies may block setting **other** users' status without a user token; preference is per-user «BRB → статус у Slack».
