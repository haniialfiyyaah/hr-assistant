from __future__ import annotations

import json
import logging
import time
from typing import Any, Protocol

from .contracts import ModelToolCall, ModelTurn

logger = logging.getLogger(__name__)


class ModelProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def respond(
        self,
        *,
        input_data: str | list[Any],
        instructions: str,
        tools: list[dict[str, Any]],
        safety_identifier: str,
        max_output_tokens: int,
    ) -> ModelTurn: ...


class OpenAIProvider:
    """Live OpenAI embeddings + Responses API function calling.

    respond() is completed for the live/Docker step; embed() is available for seeding now.
    """

    def __init__(
        self,
        *,
        api_key: str,
        agent_model: str,
        embedding_model: str,
        embedding_dimensions: int,
        base_url: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        from openai import OpenAI

        self.agent_model = agent_model
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout_seconds}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                create_kwargs: dict[str, Any] = {
                    "model": self.embedding_model,
                    "input": texts,
                }
                # text-embedding-3-* supports explicit dimensions.
                if self.embedding_dimensions:
                    create_kwargs["dimensions"] = self.embedding_dimensions
                response = self.client.embeddings.create(**create_kwargs)
                vectors = [list(item.embedding) for item in response.data]
                for vector in vectors:
                    if len(vector) != self.embedding_dimensions:
                        raise RuntimeError(
                            f"Embedding width {len(vector)} != {self.embedding_dimensions}"
                        )
                return vectors
            except Exception as exc:  # noqa: BLE001 - bounded retry for transient failures
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(0.5 * (attempt + 1))
        assert last_error is not None
        raise last_error

    def respond(
        self,
        *,
        input_data: str | list[Any],
        instructions: str,
        tools: list[dict[str, Any]],
        safety_identifier: str,
        max_output_tokens: int,
    ) -> ModelTurn:
        # Full Responses API loop wiring lands with the live/Docker step.
        raise NotImplementedError("OpenAIProvider.respond is implemented in Step 7")


class DeterministicProvider:
    """Network-free fake for tests; never the production default."""

    def __init__(self, dimensions: int = 8) -> None:
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dimensions
            for index, byte in enumerate(text.encode("utf-8")):
                vec[index % self.dimensions] += (byte % 31) / 31.0
            vectors.append(vec)
        return vectors

    def respond(
        self,
        *,
        input_data: str | list[Any],
        instructions: str,
        tools: list[dict[str, Any]],
        safety_identifier: str,
        max_output_tokens: int,
    ) -> ModelTurn:
        blob = (
            input_data
            if isinstance(input_data, str)
            else json.dumps(input_data, default=str, ensure_ascii=False)
        )
        lower = blob.lower()
        has_tool_results = '"role": "tool"' in blob or "'role': 'tool'" in blob

        if has_tool_results:
            if "hr-leave-001" in lower or "12 hari" in lower:
                return ModelTurn(
                    response_id="final-policy",
                    text=(
                        "Pegawai tetap memperoleh 12 hari kerja cuti tahunan "
                        "per tahun kalender. [HR-LEAVE-001]"
                    ),
                    input_tokens=24,
                    output_tokens=48,
                )
            if "available_days" in lower or "leave_type" in lower:
                return ModelTurn(
                    response_id="final-balance",
                    text="Berikut saldo cuti Anda sesuai data HR untuk akun yang sedang masuk.",
                    input_tokens=18,
                    output_tokens=28,
                )
            return ModelTurn(
                response_id="final-generic",
                text="Permintaan selesai.",
                input_tokens=12,
                output_tokens=12,
            )

        if any(token in lower for token in ("jatah", "cuti tahunan", "berapa cuti")):
            return ModelTurn(
                response_id="tool-search",
                tool_calls=[
                    ModelToolCall(
                        call_id="search-1",
                        name="search_hr_policy",
                        arguments={"query": "jatah cuti tahunan", "top_k": 3},
                    )
                ],
                input_tokens=16,
                output_tokens=8,
            )

        if "saldo" in lower:
            return ModelTurn(
                response_id="tool-balance",
                tool_calls=[
                    ModelToolCall(
                        call_id="balance-1",
                        name="get_my_leave_balance",
                        arguments={},
                    )
                ],
                input_tokens=14,
                output_tokens=6,
            )

        return ModelTurn(
            response_id="tool-search-default",
            tool_calls=[
                ModelToolCall(
                    call_id="search-default",
                    name="search_hr_policy",
                    arguments={"query": lower[:200] or "kebijakan hr", "top_k": 3},
                )
            ],
            input_tokens=12,
            output_tokens=6,
        )
