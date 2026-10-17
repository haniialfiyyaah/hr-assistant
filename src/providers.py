from __future__ import annotations

import json
from typing import Any, Protocol

from .contracts import ModelToolCall, ModelTurn


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
    """Live Responses API provider — implemented in the Docker/live step."""

    def __init__(self, **kwargs: Any) -> None:
        raise NotImplementedError


class DeterministicProvider:
    """Network-free fake for tests; never the production default."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * 8
            for index, byte in enumerate(text.encode("utf-8")):
                vec[index % 8] += (byte % 31) / 31.0
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
