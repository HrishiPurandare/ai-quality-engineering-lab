import pytest
from fastapi.testclient import TestClient

from app.llm import OllamaError
from app.main import app, get_pipeline
from app.rag import RAGPipeline


@pytest.fixture
def client(pipeline: RAGPipeline):
    # Swap the real Ollama-backed pipeline for the fake one for the duration of the test.
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_reports_indexed_chunks(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["indexed_chunks"] > 0


def test_chat_returns_answer_with_citations_and_contexts(client: TestClient, fake_llm):
    fake_llm.reply = "Freeze the card in the app [1]."
    response = client.post("/chat", json={"question": "My card was stolen, what should I do?"})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Freeze the card in the app [1]."
    assert body["citations"][0]["source"] == "cards.md"
    assert body["contexts"]
    assert body["refused"] is False


@pytest.mark.parametrize("payload", [{}, {"question": ""}, {"question": "   "}, {"question": "x" * 1001}])
def test_chat_rejects_invalid_input(client: TestClient, payload: dict):
    assert client.post("/chat", json=payload).status_code == 422


def test_chat_returns_503_when_model_is_down(client: TestClient, fake_llm, monkeypatch):
    def broken_chat(_messages):
        raise OllamaError("connection refused")

    monkeypatch.setattr(fake_llm, "chat", broken_chat)
    response = client.post("/chat", json={"question": "What is the daily transfer limit?"})
    assert response.status_code == 503
