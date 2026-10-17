"""Policy chunking and database seed helpers."""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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


def reset_and_seed() -> None:
    # TODO(M2): Create pgvector schema, seed synthetic identities/balances, batch embed, and upsert chunks.
    raise NotImplementedError


if __name__ == "__main__":
    reset_and_seed()
