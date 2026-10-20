from __future__ import annotations

import json
from datetime import date
from typing import Any

from fastapi.testclient import TestClient

from src.agent import AgentService
from src.api import create_app
from src.cache import NullCache
from src.providers import DeterministicProvider
from src.repository import MemoryRepository
from src.retrieval import RetrievalService
from src.tools import ToolExecutor

ALYA = {"Authorization": "Bearer token-alya"}
BIMA = {"Authorization": "Bearer token-bima"}
MARKER = "UNIQUE-LEAVE-INTENT-8841"


class RecordingProvider(DeterministicProvider):
    """Captures model input so tests can see whether prior turns were included."""

    def __init__(self) -> None:
        super().__init__()
        self.inputs: list[str] = []
        self.instructions: list[str] = []

    def respond(
        self,
        *,
        input_data: str | list[Any],
        instructions: str,
        tools: list[dict[str, Any]],
        safety_identifier: str,
        max_output_tokens: int,
    ):
        blob = (
            input_data
            if isinstance(input_data, str)
            else json.dumps(input_data, ensure_ascii=False)
        )
        self.inputs.append(blob)
        self.instructions.append(instructions)
        return super().respond(
            input_data=input_data,
            instructions=instructions,
            tools=tools,
            safety_identifier=safety_identifier,
            max_output_tokens=max_output_tokens,
        )


def _client(repository: MemoryRepository, settings) -> tuple[TestClient, RecordingProvider]:
    provider = RecordingProvider()

    def frozen_today() -> date:
        return date(2026, 10, 20)

    retrieval = RetrievalService(repository, provider, NullCache(), 0)
    tools = ToolExecutor(repository, retrieval, settings, today_factory=frozen_today)
    agent = AgentService(repository, provider, tools, settings, today_factory=frozen_today)
    app = create_app(settings=settings, repository=repository, cache=NullCache(), agent=agent)
    return TestClient(app), provider


def test_follow_up_includes_prior_turn_and_calendar(repository: MemoryRepository, settings) -> None:
    client, provider = _client(repository, settings)
    first = client.post("/api/v1/chat", headers=ALYA, json={"message": MARKER})
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]
    assert conversation_id

    second = client.post(
        "/api/v1/chat",
        headers=ALYA,
        json={"message": "next week", "conversation_id": conversation_id},
    )
    assert second.status_code == 200
    paired = list(zip(provider.inputs, provider.instructions, strict=True))
    follow_ups = [item for item in paired if MARKER in item[0] and "next week" in item[0]]
    assert follow_ups
    assert "2026-10-26" in follow_ups[0][1]
    assert "2026-10-30" in follow_ups[0][1]
    assert "Do not book the whole week." in follow_ups[0][1]

    solo = client.post("/api/v1/chat", headers=ALYA, json={"message": "solo turn marker"})
    assert solo.status_code == 200
    assert solo.json()["conversation_id"] != conversation_id
    paired = list(zip(provider.inputs, provider.instructions, strict=True))
    solo_turns = [item for item in paired if "solo turn marker" in item[0]]
    assert solo_turns
    assert all(MARKER not in item[0] for item in solo_turns)


def test_other_employee_cannot_read_conversation(repository: MemoryRepository, settings) -> None:
    client, _provider = _client(repository, settings)
    created = client.post("/api/v1/chat", headers=ALYA, json={"message": MARKER}).json()
    conversation_id = created["conversation_id"]

    denied = client.post(
        "/api/v1/chat",
        headers=BIMA,
        json={"message": "show me that thread", "conversation_id": conversation_id},
    )
    assert denied.status_code == 404

    bima_current = client.get("/api/v1/conversations/current", headers=BIMA)
    assert bima_current.status_code == 200
    assert bima_current.json()["conversation_id"] is None

    alya_current = client.get("/api/v1/conversations/current", headers=ALYA).json()
    assert alya_current["conversation_id"] == conversation_id
    assert alya_current["messages"][0]["content"] == MARKER
    assistant = next(
        item for item in alya_current["messages"] if item["role"] == "assistant"
    )
    assert assistant.get("trace_id")
    assert assistant["trace_id"] == created["trace_id"]


def test_new_conversation_becomes_current(client: TestClient) -> None:
    started = client.post("/api/v1/conversations", headers=ALYA)
    assert started.status_code == 200
    body = started.json()
    assert body["messages"] == []
    current = client.get("/api/v1/conversations/current", headers=ALYA).json()
    assert current["conversation_id"] == body["conversation_id"]
