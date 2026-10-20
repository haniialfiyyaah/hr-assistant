from __future__ import annotations

from fastapi.testclient import TestClient

ALYA = {"Authorization": "Bearer token-alya"}
BIMA = {"Authorization": "Bearer token-bima"}


def test_list_and_open_conversations(client: TestClient) -> None:
    first = client.post(
        "/api/v1/chat", headers=ALYA, json={"message": "First leave question"}
    ).json()
    second = client.post(
        "/api/v1/conversations",
        headers=ALYA,
    ).json()
    client.post(
        "/api/v1/chat",
        headers=ALYA,
        json={
            "message": "Second leave question",
            "conversation_id": second["conversation_id"],
        },
    )

    listed = client.get("/api/v1/conversations", headers=ALYA)
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) >= 2
    assert rows[0]["conversation_id"] == second["conversation_id"]
    assert "Second leave question" in rows[0]["title"]

    opened = client.get(
        f"/api/v1/conversations/{first['conversation_id']}", headers=ALYA
    )
    assert opened.status_code == 200
    assert opened.json()["messages"][0]["content"] == "First leave question"

    denied = client.get(
        f"/api/v1/conversations/{first['conversation_id']}", headers=BIMA
    )
    assert denied.status_code == 404
