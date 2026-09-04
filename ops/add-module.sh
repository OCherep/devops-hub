#!/usr/bin/env bash
# Usage: add-module.sh <id> [git_url] [git_ref]
# Creates /opt/ops/<id> from _template and appends modules.env
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ID="${1:-}"
URL="${2:-}"
REF="${3:-main}"

if [[ -z "$ID" ]]; then
  echo "Usage: $0 <id> [git_url] [git_ref]"
  exit 1
fi

if [[ -e "$ROOT/$ID" ]]; then
  echo "ERROR: $ROOT/$ID already exists"
  exit 1
fi

cp -a "$ROOT/_template" "$ROOT/$ID"
# rename placeholders
if command -v sed >/dev/null; then
  find "$ROOT/$ID" -type f \( -name '*.yml' -o -name '*.md' -o -name 'Caddyfile.snippet' \) -print0 |
    xargs -0 sed -i.bak "s/__MODULE_ID__/$ID/g" 2>/dev/null || true
  find "$ROOT/$ID" -name '*.bak' -delete 2>/dev/null || true
fi

if [[ -n "$URL" ]]; then
  rm -rf "$ROOT/$ID"
  git clone --branch "$REF" --single-branch "$URL" "$ROOT/$ID" || git clone "$URL" "$ROOT/$ID"
fi

echo "${ID}|${URL:-.}|${REF}|docker-compose.yml" >> "$ROOT/modules.env"
echo "Added $ID. Next:"
echo "  1) Edit $ROOT/$ID/docker-compose.yml"
echo "  2) Optional: merge $ROOT/$ID/Caddyfile.snippet into $ROOT/edge/Caddyfile"
echo "  3) Add card to devops-hub tools.json"
echo "  4) $ROOT/up.sh $ID && $ROOT/up.sh edge"
