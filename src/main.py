"""Vercel FastAPI entrypoint — exports module-level ``app``.

Local and Docker keep using the factory:
``uvicorn src.api:create_app --factory``.
"""

from src.api import create_app

app = create_app()
