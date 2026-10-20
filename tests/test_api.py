from __future__ import annotations

from fastapi.testclient import TestClient


AUTH = {"Authorization": "Bearer token-alya"}


def test_health_and_auth_contract(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.post("/api/v1/chat", json={"message": "saldo cuti"}).status_code == 401


def test_chat_returns_contract_and_trace(client: TestClient) -> None:
    response = client.post("/api/v1/chat", headers=AUTH, json={"message": "Berapa jatah cuti tahunan?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "answered"
    assert payload["citations"][0]["document_id"] == "HR-LEAVE-001"
    trace = client.get(f"/api/v1/traces/{payload['trace_id']}", headers=AUTH)
    assert trace.status_code == 200
    body = trace.json()
    assert "message" not in body
    assert body["citations"][0]["document_id"] == "HR-LEAVE-001"
    assert body["citations"][0]["excerpt"]
    assert "HR-LEAVE-001" in body["retrieved_document_ids"]
    assert any(item["document_id"] == "HR-LEAVE-001" for item in body["retrieved_documents"])
    assert any(
        item["document_id"] == "HR-LEAVE-001" and item.get("section")
        for item in body["retrieved_documents"]
    )
    assert body["agent_model"]
    assert body["embedding_model"]
    assert body["model_mode"]
    assert body["turn_count"] >= 1
    assert any(step["kind"] == "model" for step in body["steps"])
    assert any(
        step["kind"] == "tool" and step["name"] == "search_hr_policy"
        for step in body["steps"]
    )


def test_monitoring_is_admin_only(client: TestClient) -> None:
    assert client.get("/api/v1/monitoring/summary", headers=AUTH).status_code == 403
    response = client.get(
        "/api/v1/monitoring/summary", headers={"Authorization": "Bearer token-admin"}
    )
    assert response.status_code == 200


def test_trace_cannot_be_read_by_another_employee(client: TestClient) -> None:
    chat = client.post("/api/v1/chat", headers=AUTH, json={"message": "saldo saya"}).json()
    response = client.get(
        f"/api/v1/traces/{chat['trace_id']}",
        headers={"Authorization": "Bearer token-bima"},
    )
    assert response.status_code == 403

