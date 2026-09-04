#!/usr/bin/env bash
# Usage: bootstrap.sh [/opt/ops]
set -euo pipefail

ROOT="${1:-/opt/ops}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HUB_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

mkdir -p "$ROOT"

echo "==> ops root: $ROOT"
echo "==> hub source: $HUB_ROOT"

# Layout scripts & template into ROOT
install_file() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  cp -a "$src" "$dst"
  if [[ "$dst" == *.sh ]]; then chmod +x "$dst"; fi
}

install_file "$SCRIPT_DIR/network.sh" "$ROOT/network.sh"
install_file "$SCRIPT_DIR/up.sh" "$ROOT/up.sh"
install_file "$SCRIPT_DIR/down.sh" "$ROOT/down.sh"
install_file "$SCRIPT_DIR/modules.env" "$ROOT/modules.env"
install_file "$SCRIPT_DIR/add-module.sh" "$ROOT/add-module.sh"

rm -rf "$ROOT/_template"
cp -a "$SCRIPT_DIR/_template" "$ROOT/_template"

rm -rf "$ROOT/edge"
cp -a "$SCRIPT_DIR/edge" "$ROOT/edge"

# hub module dir
if [[ ! -e "$ROOT/hub" ]]; then
  if [[ "$HUB_ROOT" != "$ROOT/hub" ]]; then
    ln -sfn "$HUB_ROOT" "$ROOT/hub"
    echo "linked hub -> $HUB_ROOT"
  fi
elif [[ -d "$ROOT/hub" ]]; then
  echo "hub dir exists: $ROOT/hub"
fi

# Ensure hub has its compose at module root
if [[ -f "$HUB_ROOT/docker-compose.yml" ]]; then
  echo "hub docker-compose.yml OK"
fi

# Clone other modules from modules.env
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  IFS='|' read -r id url ref compose <<<"$line"
  id="$(echo "$id" | xargs)"
  url="$(echo "$url" | xargs)"
  ref="$(echo "$ref" | xargs)"
  [[ "$id" == "hub" || "$id" == "edge" ]] && continue
  [[ "$url" == "." ]] && continue
  target="$ROOT/$id"
  if [[ -d "$target/.git" ]]; then
    echo "exists $id — skip clone"
    continue
  fi
  if [[ -e "$target" ]]; then
    echo "path $target exists but not git — skip"
    continue
  fi
  echo "clone $id ($ref)"
  git clone --branch "$ref" --single-branch "$url" "$target" || git clone "$url" "$target"
  # drop module compose if we ship one in ops for static apps
  if [[ "$id" == "radar" && -f "$SCRIPT_DIR/modules/radar.docker-compose.yml" ]]; then
    cp -a "$SCRIPT_DIR/modules/radar.docker-compose.yml" "$target/docker-compose.yml"
  fi
done < "$ROOT/modules.env"

# radar compose from modules pack if radar cloned without compose
if [[ -d "$ROOT/radar" && ! -f "$ROOT/radar/docker-compose.yml" ]]; then
  cp -a "$SCRIPT_DIR/modules/radar.docker-compose.yml" "$ROOT/radar/docker-compose.yml"
fi

echo "==> bootstrap done"
echo "    $ROOT/network.sh"
echo "    $ROOT/up.sh"
echo "    OnCall: cd $ROOT/oncall && docker compose up -d   # port 85"
