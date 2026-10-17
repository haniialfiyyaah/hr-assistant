"""Hybrid policy retrieval: cache, embed, lexical+vector, RRF, keyword rerank."""
from __future__ import annotations

import hashlib
import re

from .cache import ResilientCache
from .config import get_settings
from .contracts import PolicyChunk
from .providers import ModelProvider
from .repository import Repository


def _normalize_query(query: str) -> str:
    return " ".join(query.lower().split())


def _query_terms(query: str) -> list[str]:
    return [term for term in re.split(r"\W+", query.lower()) if len(term) > 1]


def _rrf_fuse(
    lexical: list[PolicyChunk],
    semantic: list[PolicyChunk],
    *,
    k: int = 60,
) -> list[PolicyChunk]:
    scores: dict[str, float] = {}
    by_id: dict[str, PolicyChunk] = {}
    for rank, chunk in enumerate(lexical, start=1):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank)
        by_id[chunk.chunk_id] = chunk
    for rank, chunk in enumerate(semantic, start=1):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank)
        by_id[chunk.chunk_id] = chunk
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [
        by_id[chunk_id].model_copy(update={"score": score})
        for chunk_id, score in ordered
    ]


def _keyword_rerank(query: str, candidates: list[PolicyChunk]) -> list[PolicyChunk]:
    terms = _query_terms(query)
    if not terms:
        return candidates

    def boost(chunk: PolicyChunk) -> tuple[float, float]:
        haystack = f"{chunk.title} {chunk.section} {chunk.content}".lower()
        hits = sum(1 for term in terms if term in haystack)
        return (float(hits), chunk.score)

    return [
        chunk.model_copy(update={"score": float(hits) + chunk.score})
        for chunk, (hits, _) in sorted(
            ((chunk, boost(chunk)) for chunk in candidates),
            key=lambda item: item[1],
            reverse=True,
        )
    ]


class RetrievalService:
    def __init__(
        self,
        repository: Repository,
        provider: ModelProvider,
        cache: ResilientCache,
        cache_ttl_seconds: int,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.cache = cache
        self.cache_ttl_seconds = cache_ttl_seconds

    def search(self, query: str, top_k: int = 3) -> list[PolicyChunk]:
        normalized = _normalize_query(query)
        version = get_settings().policy_index_version
        digest = hashlib.sha256(f"{version}:{top_k}:{normalized}".encode()).hexdigest()[:24]
        cache_key = f"retrieval:{digest}"

        cached = self.cache.get(cache_key)
        if isinstance(cached, list):
            return [PolicyChunk.model_validate(item) for item in cached]

        candidate_limit = max(top_k * 3, 8)
        embedding = self.provider.embed([normalized])[0]
        lexical = self.repository.lexical_search(normalized, candidate_limit)
        semantic = self.repository.vector_search(embedding, candidate_limit)
        fused = _rrf_fuse(lexical, semantic)
        ranked = _keyword_rerank(normalized, fused)[:top_k]

        if self.cache_ttl_seconds > 0:
            self.cache.set(
                cache_key,
                [chunk.model_dump(mode="json") for chunk in ranked],
                self.cache_ttl_seconds,
            )
        return ranked
