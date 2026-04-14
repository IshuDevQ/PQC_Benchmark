#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
IMAGE_NAME="pqc-kem-benchmark:latest"

if ! command -v docker >/dev/null 2>&1; then
  echo "[error] Docker is not installed or not available in PATH."
  exit 1
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose -f "${COMPOSE_FILE}")
else
  echo "[error] Docker Compose v2 is required ('docker compose')."
  exit 1
fi

if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
  echo "[info] Docker image not found. Building ${IMAGE_NAME} first."
  "${COMPOSE_CMD[@]}" build pqc-bench
fi

if [ "$#" -eq 0 ]; then
  echo "[info] No command supplied. Defaulting to: python main.py --help"
  set -- python main.py --help
fi

"${COMPOSE_CMD[@]}" run --rm pqc-bench "$@"
