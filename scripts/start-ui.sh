#!/bin/sh
# Render injects PORT. Streamlit local default is 8501.
set -eu
exec python -m streamlit run app.py \
  --server.address 0.0.0.0 \
  --server.port "${PORT:-8501}" \
  --server.headless true
