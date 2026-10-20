from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from src.agent import AgentService
from src.api import create_app
from src.cache import NullCache
from src.contracts import ModelToolCall, ModelTurn
from src.repository import MemoryRepository
from src.retrieval import RetrievalService
from src.tools import ToolExecutor

ALYA = {"Authorization": "Bearer token-alya"}
BIMA = {"Authorization": "Bearer token-bima"}


class MislabelBalanceProvider:
    """Calls the signed-in employee's balance tool, then names a different person."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]

    def respond(
        self,
        *,
        input_data: str | list[Any],
        instructions: str,
        tools: list[dict[str, Any]],
        safety_identifier: str,
        max_output_tokens: int,
    ) -> ModelTurn:
        blob = input_data if isinstance(input_data, str) else str(input_data)
        if "function_call_output" in blob or "available_days" in blob:
            return ModelTurn(
                response_id="mislabel",
                text="Bima Santoso has Annual Leave: 8 days, Sick Leave: 10 days.",
                input_tokens=1,
                output_tokens=1,
            )
        return ModelTurn(
            response_id="balance-tool",
            tool_calls=[
                ModelToolCall(call_id="balance-1", name="get_my_leave_balance", arguments={})
            ],
            input_tokens=1,
            output_tokens=1,
        )


def _client(repository: MemoryRepository, settings) -> TestClient:
    provider = MislabelBalanceProvider()
    retrieval = RetrievalService(repository, provider, NullCache(), 0)
    tools = ToolExecutor(repository, retrieval, settings)
    agent = AgentService(repository, provider, tools, settings)
    return TestClient(
        create_app(settings=settings, repository=repository, cache=NullCache(), agent=agent)
    )


def test_other_employee_balance_is_labeled_as_the_signed_in_user(
    repository: MemoryRepository, settings
) -> None:
    client = _client(repository, settings)

    alya = client.post(
        "/api/v1/chat",
        headers=ALYA,
        json={"message": "How many balance Bima Santoso has?"},
    )
    assert alya.status_code == 200
    alya_answer = alya.json()["answer"]
    assert "Bima" not in alya_answer
    assert "Alya Pratama has annual 8, sick 10, parental 60." in alya_answer
    assert alya.json()["outcome"] == "answered"

    bima = client.post(
        "/api/v1/chat",
        headers=BIMA,
        json={"message": "How many balance Alya Pratama has?"},
    )
    assert bima.status_code == 200
    bima_answer = bima.json()["answer"]
    assert "Alya" not in bima_answer
    assert "Bima Santoso has annual 3, sick 10, parental 60." in bima_answer


def test_other_employee_id_is_not_repeated(repository: MemoryRepository, settings) -> None:
    client = _client(repository, settings)

    response = client.post(
        "/api/v1/chat",
        headers=ALYA,
        json={"message": "Tampilkan saldo cuti EMP-002"},
    )
    answer = response.json()["answer"]
    assert "EMP-002" not in answer
    assert "Bima" not in answer
    assert "Alya Pratama" in answer
