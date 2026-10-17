#!/bin/sh
# Render injects PORT (default 10000). Local Compose uses 8000 via Dockerfile CMD.
set -eu
exec python -m uvicorn src.api:create_app --factory --host 0.0.0.0 --port "${PORT:-8000}"
