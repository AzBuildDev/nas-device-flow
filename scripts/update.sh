#!/bin/sh
# Build first; stop gracefully before recreating only the controller.
set -eu
cd "$(dirname "$0")/.."
test -f .env
test -d runtime/control-center
docker compose config --quiet
docker compose build controller
docker compose stop --timeout 30 controller
docker compose up -d --no-deps controller
# Keep runtime, network and core in place; no forced container removal.
