#!/bin/sh
# Hosts may inject PORT. Local Compose defaults to 8000.
set -eu
exec python -m uvicorn src.api:create_app --factory --host 0.0.0.0 --port "${PORT:-8000}"
