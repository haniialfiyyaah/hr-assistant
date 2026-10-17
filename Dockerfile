# Starter: complete the app image for FastAPI AND Streamlit on Compose.
# Build must not require OPENAI_API_KEY; model config is supplied at runtime.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt ./
# TODO(M2): Install Python dependencies from requirements.txt.
# TODO(M2): Copy src/, data/, app.py, ui_contract.py, demo_personas.json,
#           and tests/ into the image. Use .dockerignore so .env is not copied.
# TODO(M2): Create a non-root user, ensure app files are readable, then USER that user.
# TODO(M2): EXPOSE port 8000 for the API.
# TODO(M2): CMD run uvicorn src.api:create_app --factory on 0.0.0.0:8000.
#           Compose overrides CMD for the Streamlit service; do not use an ENTRYPOINT
#           that forces the API so seed/test commands and the UI can still run.
