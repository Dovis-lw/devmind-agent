from __future__ import annotations

import asyncio
from fastapi.testclient import TestClient

from app.main import app, store


AUTH = {"Authorization": "Bearer demo-token"}


def test_health_and_auth_contract() -> None:
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.post("/api/auth/login", json={"email": "demo@devmind.local", "password": "devmind-demo"}).status_code == 200
        assert client.post("/api/auth/login", json={"email": "demo@devmind.local", "password": "wrong"}).status_code == 401
        assert client.get("/api/workspaces").status_code == 401


def test_models_only_expose_enabled_backend_models() -> None:
    with TestClient(app) as client:
        response = client.get("/api/models", headers=AUTH)
        assert response.status_code == 200
        models = response.json()
        assert {model["id"] for model in models} >= {"mock-chat", "local-embedding"}
        assert all(model["enabled"] for model in models)


def test_paste_text_and_task_permission_contract() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/knowledge-bases/kb-demo/documents/text",
            headers=AUTH,
            json={"name": "api-contract.md", "content": "FastAPI 422 Pydantic", "document_type": "markdown"},
        )
        assert response.status_code == 200
        task_id = response.json()["task"]["id"]
        for _ in range(20):
            task = client.get(f"/api/tasks/{task_id}", headers=AUTH).json()
            if task["status"] in {"succeeded", "failed"}:
                break
            asyncio.run(asyncio.sleep(0.01))
        assert task["status"] == "succeeded"
        docs = client.get("/api/knowledge-bases/kb-demo/documents", headers=AUTH).json()
        assert any(item["name"] == "api-contract.md" for item in docs)
        assert client.get(f"/api/tasks/{task_id}").status_code == 401


def test_upload_validation_and_git_p1_contract() -> None:
    with TestClient(app) as client:
        empty = client.post(
            "/api/knowledge-bases/kb-demo/documents",
            headers=AUTH,
            files={"file": ("empty.md", b"")},
        )
        assert empty.status_code == 400
        unsupported = client.post(
            "/api/knowledge-bases/kb-demo/documents",
            headers=AUTH,
            files={"file": ("payload.exe", b"MZ")},
        )
        assert unsupported.status_code == 415
        git = client.post("/api/knowledge-bases/kb-demo/imports/git", headers=AUTH)
        assert git.status_code == 501


def test_model_allowlist_rejects_unknown_chat_and_embedding() -> None:
    with TestClient(app) as client:
        payload = {
            "workspace_id": "ws-demo",
            "knowledge_base_id": "kb-demo",
            "question": "FastAPI 422 Pydantic",
            "model_id": "not-enabled",
            "embedding_model_id": "local-embedding",
        }
        assert client.post("/api/chat/stream", headers=AUTH, json=payload).status_code == 400
        payload["model_id"] = "mock-chat"
        payload["embedding_model_id"] = "not-enabled"
        assert client.post("/api/chat/stream", headers=AUTH, json=payload).status_code == 400


def test_chat_stream_returns_citation_and_refusal() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/chat/stream",
            headers=AUTH,
            json={
                "workspace_id": "ws-demo",
                "knowledge_base_id": "kb-demo",
                "question": "FastAPI 返回 422，如何定位 Pydantic 参数校验？",
                "model_id": "mock-chat",
                "embedding_model_id": "local-embedding",
            },
        )
        assert response.status_code == 200
        assert "event: citation" in response.text
        assert "fastapi-troubleshooting.md" in response.text

        refusal = client.post(
            "/api/chat/stream",
            headers=AUTH,
            json={
                "workspace_id": "ws-demo",
                "knowledge_base_id": "kb-demo",
                "question": "如何种植火星土豆？",
                "model_id": "mock-chat",
                "embedding_model_id": "local-embedding",
            },
        )
        assert refusal.status_code == 200
        assert "证据不足" in refusal.text
        assert '"citations": []' in refusal.text


def test_filter_contract() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/chat/stream",
            headers=AUTH,
            json={
                "workspace_id": "ws-demo",
                "knowledge_base_id": "kb-demo",
                "question": "RAG 检索必须带来源信息",
                "model_id": "mock-chat",
                "embedding_model_id": "local-embedding",
                "filters": {"document_types": ["pdf"]},
            },
        )
        assert response.status_code == 200
        assert '"citations": []' in response.text
