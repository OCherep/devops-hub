#!/bin/sh
# Future hook: import renewed PEM into AWS Certificate Manager.
# Requires AWS CLI in image + IAM: acm:ImportCertificate, acm:ListCertificates
# Env: AWS_REGION, AWS_ACM_ARN (existing cert to re-import) or empty to create.
set -e
REGION="${AWS_REGION:-eu-central-1}"
CHAIN="${ONCALL_CERTS_DIR:-/oncall-certs}/fullchain.pem"
KEY="${ONCALL_CERTS_DIR:-/oncall-certs}/privkey.pem"
[ -f "$CHAIN" ] && [ -f "$KEY" ] || { echo "[acm] no pem"; exit 0; }
if ! command -v aws >/dev/null 2>&1; then
  echo "[acm] aws cli not installed — skip"
  exit 0
fi
if [ -n "$AWS_ACM_ARN" ]; then
  aws acm import-certificate --region "$REGION" \
    --certificate-arn "$AWS_ACM_ARN" \
    --certificate fileb://"$CHAIN" \
    --private-key fileb://"$KEY" \
    --certificate-chain fileb://"$CHAIN"
  echo "[acm] re-imported $AWS_ACM_ARN"
else
  echo "[acm] AWS_ACM_ARN empty — set it to re-import an existing ACM cert"
fi
