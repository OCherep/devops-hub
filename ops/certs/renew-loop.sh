#!/bin/sh
# Periodic ZeroSSL (ACME) renew; copy PEM to OnCall certs dir.
set -e
DOMAIN="${DOMAIN:-s.ks.tv}"
EMAIL="${EMAIL:-ops@s.ks.tv}"
INTERVAL_H="${RENEW_INTERVAL_HOURS:-12}"
DEST="${ONCALL_CERTS_DIR:-/oncall-certs}"

issue_or_renew() {
  if [ -n "$ZEROSSL_EAB_KID" ] && [ -n "$ZEROSSL_EAB_HMAC" ]; then
    echo "[certs] ZeroSSL ACME for ${DOMAIN}"
    certbot certonly --non-interactive --agree-tos       --email "$EMAIL"       --server https://acme.zerossl.com/v2/DV90       --eab-kid "$ZEROSSL_EAB_KID"       --eab-hmac-key "$ZEROSSL_EAB_HMAC"       --webroot -w /var/www/certbot       -d "$DOMAIN"       --keep-until-expiring       --preferred-challenges http       || certbot renew --server https://acme.zerossl.com/v2/DV90 --webroot -w /var/www/certbot || true
  else
    echo "[certs] ZEROSSL_EAB_KID/HMAC not set — trying certbot renew (any existing)"
    certbot renew --webroot -w /var/www/certbot || true
  fi
}

copy_to_oncall() {
  live="/etc/letsencrypt/live/${DOMAIN}"
  if [ -f "${live}/fullchain.pem" ] && [ -f "${live}/privkey.pem" ]; then
    mkdir -p "$DEST"
    cp -L "${live}/fullchain.pem" "${DEST}/fullchain.pem"
    cp -L "${live}/privkey.pem" "${DEST}/privkey.pem"
    chmod 644 "${DEST}/fullchain.pem"
    chmod 640 "${DEST}/privkey.pem" || true
    echo "[certs] copied PEM → ${DEST}"
    # optional hook: reload oncall nginx
    if [ -x /work/hooks/post-renew.sh ]; then
      /work/hooks/post-renew.sh || true
    fi
  else
    echo "[certs] no live cert at ${live}"
  fi
}

# ACM placeholder
# if [ -n "$AWS_ACM_ARN" ]; then aws acm import-certificate ...; fi

while true; do
  issue_or_renew
  copy_to_oncall
  echo "[certs] sleep ${INTERVAL_H}h"
  sleep $((INTERVAL_H * 3600))
done
