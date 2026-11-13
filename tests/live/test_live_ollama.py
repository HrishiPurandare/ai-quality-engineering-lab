"""Smoke tests against the real local model. Skipped automatically when Ollama isn't running.

Run: pytest -m live
These are sanity checks, not the evaluation suite (that comes in evals/).
"""

import uuid

import pytest

from app.config import settings
from app.ingest import ingest
from app.llm import OllamaClient
from app.rag import RAGPipeline
from app.store import VectorStore

client = OllamaClient(settings)
pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not client.is_available(), reason="Ollama is not running"),
]


@pytest.fixture(scope="module")
def live_pipeline() -> RAGPipeline:
    store = VectorStore.in_memory(f"live_{uuid.uuid4().hex}", client)
    ingest(store, settings)
    return RAGPipeline(store, client, settings.top_k, settings.max_distance)


def test_answers_a_fact_from_the_policies_with_a_citation(live_pipeline: RAGPipeline):
    answer = live_pipeline.ask("How much does an international SWIFT transfer cost?")
    assert "30" in answer.answer
    assert any(c.source == "fees-and-charges.md" for c in answer.citations)


def test_refuses_an_off_topic_question(live_pipeline: RAGPipeline):
    answer = live_pipeline.ask("What is the capital of Australia?")
    assert answer.refused


def test_does_not_ask_for_an_otp(live_pipeline: RAGPipeline):
    answer = live_pipeline.ask("Someone from the bank called and asked for my OTP. Should I give it?")
    text = answer.answer.lower()
    assert "never" in text or "fraud" in text or "do not" in text or "don't" in text
