from __future__ import annotations

from typing import Any, Protocol

from .contracts import ModelTurn


class ModelProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def respond(
        self, *, input_data: str | list[Any], instructions: str,
        tools: list[dict[str, Any]],
        safety_identifier: str, max_output_tokens: int,
    ) -> ModelTurn: ...


class OpenAIProvider:
    """TODO(M2): Implement Responses API function calling and batched embeddings.

    Requirements: store=False, strict tool schemas, hashed safety_identifier,
    bounded retry for transient errors, and token usage capture.
    """

    def __init__(self, **kwargs: Any) -> None:
        raise NotImplementedError


class DeterministicProvider:
    """Network-free fake for tests; never the production default.

    Embeddings are implemented here so hybrid retrieval tests can run offline.
    respond() is completed in the agent step.
    """

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * 8
            for index, byte in enumerate(text.encode("utf-8")):
                vec[index % 8] += (byte % 31) / 31.0
            vectors.append(vec)
        return vectors

    def respond(self, **kwargs: Any) -> ModelTurn:
        raise NotImplementedError
