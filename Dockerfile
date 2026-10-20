# FastAPI app image. Build does not require OPENAI_API_KEY.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY data ./data
COPY tests ./tests
COPY scripts ./scripts
COPY ui_contract.py demo_personas.json pyproject.toml ./

RUN chmod +x scripts/start-api.sh \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# No ENTRYPOINT so Compose can override CMD for seed and tests.
CMD ["sh", "/app/scripts/start-api.sh"]
