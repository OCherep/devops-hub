#!/bin/sh
# Inventory TLS certs on this host + optional AWS ACM.
# Writes /opt/ops/certs/status.json (or $STATUS_OUT).
set -eu
OUT="${STATUS_OUT:-/opt/ops/certs/status.json}"
WARN_DAYS="${WARN_DAYS:-21}"
NOW=$(date +%s)
TMP=$(mktemp)
echo '[' > "$TMP"
first=1

add_json() {
  # name issuer not_after source path days_left status
  name=$1 issuer=$2 not_after=$3 source=$4 path=$5
  exp=$(date -d "$not_after" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$not_after" +%s 2>/dev/null || echo 0)
  if [ "$exp" = 0 ]; then
    days=9999; st="unknown"
  else
    days=$(( (exp - NOW) / 86400 ))
    if [ "$days" -lt 0 ]; then st="expired"
    elif [ "$days" -le "$WARN_DAYS" ]; then st="expiring"
    else st="ok"
    fi
  fi
  [ "$first" = 1 ] || echo ',' >> "$TMP"
  first=0
  printf '{"name":"%s","issuer":"%s","not_after":"%s","days_left":%s,"status":"%s","source":"%s","path":"%s"}\n' \
    "$name" "$issuer" "$not_after" "$days" "$st" "$source" "$path" >> "$TMP"
}

scan_pem() {
  f="$1"; src="$2"
  [ -f "$f" ] || return 0
  sub=$(openssl x509 -in "$f" -noout -subject 2>/dev/null | sed 's/.*CN *= *//' | head -1)
  iss=$(openssl x509 -in "$f" -noout -issuer 2>/dev/null | sed 's/.*CN *= *//' | head -1)
  end=$(openssl x509 -in "$f" -noout -enddate 2>/dev/null | sed 's/notAfter=//')
  [ -n "$sub" ] && add_json "$sub" "$iss" "$end" "$src" "$f"
}

# Local PEM / ZeroSSL / OnCall
for f in \
  /opt/ops/oncall/certs/fullchain.pem \
  /opt/ops/oncall/certs/s.ks.tv/certificate.crt \
  /opt/oncall-app-5/certs/fullchain.pem \
  /etc/letsencrypt/live/*/fullchain.pem
do
  for g in $f; do
    [ -e "$g" ] || continue
    case "$g" in
      /etc/letsencrypt/*) src=letsencrypt ;;
      *) src=local-pem ;;
    esac
    scan_pem "$g" "$src"
  done
done

# certbot account inventory if CLI present
if command -v certbot >/dev/null 2>&1; then
  certbot certificates 2>/dev/null | awk '
    /^Found/{next}
    /Certificate Name:/{name=$3}
    /Domains:/{dom=$2}
    /Expiry Date:/{exp=$3" "$4; print name"|"dom"|"exp}
  ' | while IFS='|' read -r name dom exp; do
    [ -n "$name" ] || continue
    add_json "${dom:-$name}" "Let's Encrypt" "$exp" "certbot" "/etc/letsencrypt/live/${name}"
  done || true
fi

# AWS ACM (optional)
if command -v aws >/dev/null 2>&1 && [ -n "${AWS_REGION:-}" ]; then
  aws acm list-certificates --region "$AWS_REGION" --certificate-statuses ISSUED PENDING_VALIDATION EXPIRED \
    --query 'CertificateSummaryList[].{arn:CertificateArn,dom:DomainName}' --output text 2>/dev/null \
  | while read -r arn dom; do
      [ -n "$arn" ] || continue
      end=$(aws acm describe-certificate --region "$AWS_REGION" --certificate-arn "$arn" \
        --query 'Certificate.NotAfter' --output text 2>/dev/null || echo "")
      add_json "$dom" "AWS ACM" "$end" "acm" "$arn"
    done || true
fi

echo ']' >> "$TMP"
mkdir -p "$(dirname "$OUT")"
mv "$TMP" "$OUT"
echo "[certs] inventory → $OUT"
python3 - "$OUT" << 'PY' 2>/dev/null || cat "$OUT"
import json,sys
rows=json.load(open(sys.argv[1]))
print(f"{'STATUS':<10} {'DAYS':>5}  {'NAME':<40} {'SOURCE'}")
for r in sorted(rows, key=lambda x: x.get('days_left',9999)):
    print(f"{r.get('status',''):<10} {str(r.get('days_left','')):>5}  {r.get('name',''):<40} {r.get('source','')}")
PY
