#!/usr/bin/env bash
set -euo pipefail
NAME="${OPSNET_NAME:-opsnet}"
if docker network inspect "$NAME" >/dev/null 2>&1; then
  echo "network $NAME already exists"
else
  docker network create "$NAME"
  echo "created network $NAME"
fi
