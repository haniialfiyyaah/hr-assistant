from __future__ import annotations

import json
import logging
import os
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


def _is_transient(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if status in {408, 409, 429, 500, 502, 503, 504}:
        return True
    return any(token in name for token in ("timeout", "ratelimit", "apiconnection", "internalserver"))


class OpenAIProvider:
    """Live OpenAI embeddings + Responses API function calling."""

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
        # The SDK also reads OPENAI_BASE_URL from the process env. Compose often
        # injects an empty string from .env, which breaks httpx ("missing protocol").
        cleaned_base = (base_url or "").strip() or None
        if not cleaned_base:
            os.environ.pop("OPENAI_BASE_URL", None)
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout_seconds}
        if cleaned_base:
            kwargs["base_url"] = cleaned_base
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
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= self.max_retries or not _is_transient(exc):
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
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                create_kwargs: dict[str, Any] = {
                    "model": self.agent_model,
                    "instructions": instructions,
                    "input": input_data,
                    "tools": tools,
                    "store": False,
                    "max_output_tokens": max_output_tokens,
                }
                try:
                    response = self.client.responses.create(
                        **create_kwargs,
                        safety_identifier=safety_identifier,
                    )
                except TypeError:
                    # Older SDK builds may not accept safety_identifier.
                    response = self.client.responses.create(**create_kwargs)

                return self._parse_response(response)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= self.max_retries or not _is_transient(exc):
                    break
                logger.warning("Transient Responses API failure; retrying (%s)", attempt + 1)
                time.sleep(0.5 * (attempt + 1))
        assert last_error is not None
        raise last_error

    def _parse_response(self, response: Any) -> ModelTurn:
        tool_calls: list[ModelToolCall] = []
        text_parts: list[str] = []
        output_items: list[Any] = []

        for item in getattr(response, "output", None) or []:
            item_type = getattr(item, "type", None)
            if item_type == "function_call":
                raw_args = getattr(item, "arguments", "{}")
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                call_id = str(getattr(item, "call_id", "") or getattr(item, "id", ""))
                name = str(getattr(item, "name", ""))
                tool_calls.append(
                    ModelToolCall(call_id=call_id, name=name, arguments=arguments)
                )
                output_items.append(
                    {
                        "type": "function_call",
                        "call_id": call_id,
                        "name": name,
                        "arguments": raw_args if isinstance(raw_args, str) else json.dumps(arguments),
                    }
                )
            elif item_type == "message":
                for content in getattr(item, "content", None) or []:
                    content_type = getattr(content, "type", None)
                    if content_type in {"output_text", "text"}:
                        text_parts.append(str(getattr(content, "text", "") or ""))

        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        return ModelTurn(
            response_id=str(getattr(response, "id", "response")),
            text="".join(text_parts).strip(),
            tool_calls=tool_calls,
            output_items=output_items,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


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
        has_tool_results = (
            "function_call_output" in blob
            or '"role": "tool"' in blob
            or "'role': 'tool'" in blob
        )

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
