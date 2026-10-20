"""Policy chunking and PostgreSQL / pgvector seed helpers."""
from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from .config import Settings, get_settings
from .security import token_hash

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def chunk_policy(path: Path) -> list[dict[str, str]]:
    """Parse Markdown front matter and section headings into stable chunks."""
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"Policy file missing front matter: {path}")
    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Policy file front matter is malformed: {path}")
    front_matter, body = parts[1], parts[2]

    meta: dict[str, str] = {}
    for line in front_matter.strip().splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            continue
        meta[key.strip()] = value.strip()

    required = ("document_id", "title", "version", "effective_date")
    missing = [key for key in required if key not in meta]
    if missing:
        raise ValueError(f"Missing front matter keys {missing} in {path}")

    chunks: list[dict[str, str]] = []
    sections = re.split(r"^##\s+", body.strip(), flags=re.MULTILINE)
    for block in sections:
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        section = lines[0].strip()
        content = "\n".join(lines[1:]).strip()
        if not content:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", section.lower()).strip("-")
        chunks.append(
            {
                "chunk_id": f"{meta['document_id']}:{slug}",
                "document_id": meta["document_id"],
                "title": meta["title"],
                "section": section,
                "version": meta["version"],
                "effective_date": meta["effective_date"],
                "content": content,
            }
        )
    return chunks


def _schema_sql(embedding_dimensions: int) -> str:
    # Dimension is an integer from settings, not user input.
    dim = int(embedding_dimensions)
    return f"""
    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE IF NOT EXISTS employees (
        employee_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('employee', 'monitoring_admin')),
        token_hash TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS leave_balances (
        employee_id TEXT NOT NULL REFERENCES employees(employee_id),
        leave_type TEXT NOT NULL,
        available_days INTEGER NOT NULL CHECK (available_days >= 0),
        as_of_date DATE NOT NULL,
        PRIMARY KEY (employee_id, leave_type)
    );

    CREATE TABLE IF NOT EXISTS leave_requests (
        request_id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL REFERENCES employees(employee_id),
        leave_type TEXT NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        business_days INTEGER NOT NULL CHECK (business_days > 0),
        status TEXT NOT NULL CHECK (
            status IN ('pending_manager_review', 'approved', 'cancelled', 'rejected')
        ),
        created_at TIMESTAMPTZ NOT NULL,
        reason TEXT
    );

    CREATE TABLE IF NOT EXISTS action_proposals (
        proposal_id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL REFERENCES employees(employee_id),
        leave_type TEXT NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        business_days INTEGER NOT NULL CHECK (business_days > 0),
        reason TEXT,
        validation_summary JSONB NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        idempotency_key TEXT,
        request_id TEXT REFERENCES leave_requests(request_id),
        audit_reference TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS hr_tickets (
        ticket_id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL REFERENCES employees(employee_id),
        category TEXT NOT NULL,
        summary TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS policy_chunks (
        chunk_id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        title TEXT NOT NULL,
        section TEXT NOT NULL,
        version TEXT NOT NULL,
        effective_date DATE NOT NULL,
        content TEXT NOT NULL,
        embedding vector({dim}) NOT NULL,
        index_version TEXT NOT NULL,
        tsv tsvector GENERATED ALWAYS AS (
            to_tsvector(
                'simple',
                coalesce(title, '') || ' ' || coalesce(section, '') || ' ' || coalesce(content, '')
            )
        ) STORED
    );

    CREATE INDEX IF NOT EXISTS policy_chunks_tsv_idx ON policy_chunks USING GIN (tsv);

    CREATE TABLE IF NOT EXISTS traces (
        trace_id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL,
        payload JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS conversations (
        conversation_id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL REFERENCES employees(employee_id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS conversations_employee_updated_idx
        ON conversations (employee_id, updated_at DESC);

    CREATE TABLE IF NOT EXISTS conversation_messages (
        message_id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
        role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
        content TEXT NOT NULL,
        outcome TEXT,
        proposal_id TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        seq BIGINT GENERATED ALWAYS AS IDENTITY
    );

    CREATE INDEX IF NOT EXISTS conversation_messages_lookup_idx
        ON conversation_messages (conversation_id, seq);
    """


def _drop_schema_sql() -> str:
    return """
    DROP TABLE IF EXISTS conversation_messages CASCADE;
    DROP TABLE IF EXISTS conversations CASCADE;
    DROP TABLE IF EXISTS traces CASCADE;
    DROP TABLE IF EXISTS policy_chunks CASCADE;
    DROP TABLE IF EXISTS hr_tickets CASCADE;
    DROP TABLE IF EXISTS action_proposals CASCADE;
    DROP TABLE IF EXISTS leave_requests CASCADE;
    DROP TABLE IF EXISTS leave_balances CASCADE;
    DROP TABLE IF EXISTS employees CASCADE;
    """


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in embedding) + "]"


def _local_embeddings(texts: list[str], dimensions: int) -> list[list[float]]:
    """Deterministic offline embeddings for seed when live credentials are absent."""
    vectors: list[list[float]] = []
    for text in texts:
        vec = [0.0] * dimensions
        data = text.encode("utf-8")
        for index, byte in enumerate(data):
            vec[index % dimensions] += (byte % 31) / 31.0
        # Light L2 normalize for stable cosine behavior.
        norm = sum(value * value for value in vec) ** 0.5 or 1.0
        vectors.append([value / norm for value in vec])
    return vectors


def _build_embedder(settings: Settings) -> Callable[[list[str]], list[list[float]]]:
    if settings.openai_api_key and settings.embedding_model:
        from .providers import OpenAIProvider

        provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            agent_model=settings.agent_model or settings.embedding_model,
            embedding_model=settings.embedding_model,
            embedding_dimensions=settings.embedding_dimensions,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.model_timeout_seconds,
        )
        return provider.embed

    logger.warning(
        "OPENAI_API_KEY/EMBEDDING_MODEL not set; seeding with local deterministic embeddings"
    )
    dim = settings.embedding_dimensions

    def embed(texts: list[str]) -> list[list[float]]:
        return _local_embeddings(texts, dim)

    return embed


def ensure_schema(conn, settings: Settings, *, reset: bool) -> None:
    with conn.cursor() as cur:
        if reset:
            cur.execute(_drop_schema_sql())
        cur.execute(_schema_sql(settings.embedding_dimensions))
        # ivfflat needs analyze / optional rebuild after first inserts; ignore empty-index errors later.


def seed_identities(conn) -> None:
    employees = json.loads((DATA / "employees.json").read_text(encoding="utf-8"))
    as_of = date(2026, 1, 1)
    with conn.cursor() as cur:
        for row in employees:
            cur.execute(
                """
                INSERT INTO employees (employee_id, display_name, role, token_hash)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (employee_id) DO UPDATE
                SET display_name = EXCLUDED.display_name,
                    role = EXCLUDED.role,
                    token_hash = EXCLUDED.token_hash
                """,
                (
                    row["employee_id"],
                    row["display_name"],
                    row["role"],
                    token_hash(row["token"]),
                ),
            )
            for leave_type, days in row.get("balances", {}).items():
                cur.execute(
                    """
                    INSERT INTO leave_balances (employee_id, leave_type, available_days, as_of_date)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (employee_id, leave_type) DO UPDATE
                    SET available_days = EXCLUDED.available_days,
                        as_of_date = EXCLUDED.as_of_date
                    """,
                    (row["employee_id"], leave_type, int(days), as_of),
                )


def seed_historical_requests(conn) -> None:
    rows = json.loads((DATA / "historical_requests.json").read_text(encoding="utf-8"))
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                """
                INSERT INTO leave_requests (
                    request_id, employee_id, leave_type, start_date, end_date,
                    business_days, status, created_at, reason
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL)
                ON CONFLICT (request_id) DO NOTHING
                """,
                (
                    row["request_id"],
                    row["employee_id"],
                    row["leave_type"],
                    date.fromisoformat(row["start_date"]),
                    date.fromisoformat(row["end_date"]),
                    int(row["business_days"]),
                    row["status"],
                    datetime.fromisoformat(row["created_at"]),
                ),
            )


def seed_policy_chunks(conn, settings: Settings, embed: Callable[[list[str]], list[list[float]]]) -> int:
    policy_dir = DATA / "policies"
    chunks: list[dict[str, str]] = []
    for path in sorted(policy_dir.glob("*.md")):
        chunks.extend(chunk_policy(path))

    texts = [f"{item['title']}\n{item['section']}\n{item['content']}" for item in chunks]
    vectors = embed(texts)
    if len(vectors) != len(chunks):
        raise RuntimeError("Embedding count does not match chunk count")

    for vector in vectors:
        if len(vector) != settings.embedding_dimensions:
            raise RuntimeError(
                f"Embedding width {len(vector)} != EMBEDDING_DIMENSIONS "
                f"{settings.embedding_dimensions}"
            )

    with conn.cursor() as cur:
        for item, vector in zip(chunks, vectors, strict=True):
            cur.execute(
                """
                INSERT INTO policy_chunks (
                    chunk_id, document_id, title, section, version, effective_date,
                    content, embedding, index_version
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector, %s)
                ON CONFLICT (chunk_id) DO UPDATE SET
                    document_id = EXCLUDED.document_id,
                    title = EXCLUDED.title,
                    section = EXCLUDED.section,
                    version = EXCLUDED.version,
                    effective_date = EXCLUDED.effective_date,
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    index_version = EXCLUDED.index_version
                """,
                (
                    item["chunk_id"],
                    item["document_id"],
                    item["title"],
                    item["section"],
                    item["version"],
                    date.fromisoformat(item["effective_date"]),
                    item["content"],
                    _vector_literal(vector),
                    settings.policy_index_version,
                ),
            )
    return len(chunks)


def reset_and_seed(*, reset: bool = False, settings: Settings | None = None) -> None:
    """Create schema (optionally wipe) and seed synthetic identities, history, and policies."""
    import psycopg

    settings = settings or get_settings()
    embed = _build_embedder(settings)
    logger.info("Connecting to %s", settings.database_url)
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        ensure_schema(conn, settings, reset=reset)
        seed_identities(conn)
        seed_historical_requests(conn)
        count = seed_policy_chunks(conn, settings, embed)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM policy_chunks WHERE document_id = %s",
                ("HR-LEAVE-001",),
            )
            leave_chunks = cur.fetchone()[0]
    logger.info(
        "Seed complete: %s policy chunks (%s for HR-LEAVE-001), reset=%s",
        count,
        leave_chunks,
        reset,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Seed the HR assistant database")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate tables before seeding (destructive)",
    )
    args = parser.parse_args()
    reset_and_seed(reset=args.reset)
