#!/usr/bin/env sh
# One-shot local stack: Postgres, Redis, seed, API, Next UI.
set -eu

cd "$(dirname "$0")/.."
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-hr_assistant}"

echo "==> Building api + web"
docker-compose build api web

echo "==> Starting postgres + redis"
docker-compose up -d postgres redis

echo "==> Waiting for postgres"
i=0
until docker-compose exec -T postgres pg_isready -U hr_app -d hr_assistant >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 60 ]; then
    echo "Postgres did not become ready in time." >&2
    exit 1
  fi
  sleep 1
done

echo "==> Seeding database (src.setup_lab)"
docker-compose run --rm api python -m src.setup_lab

echo "==> Starting api + web"
docker-compose up -d api web

echo ""
echo "UI  http://localhost:3000  (alya@demo.local / demo)"
echo "API http://localhost:8000"
echo "Stop with: COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME} docker-compose down"
