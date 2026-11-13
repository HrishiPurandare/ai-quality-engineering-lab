import uuid
from dataclasses import replace

import pytest

from app.config import settings
from app.ingest import ingest
from app.rag import RAGPipeline
from app.store import VectorStore
from tests.fakes import FakeLLM

# The fake bag-of-words embeddings are cruder than real ones, so their distances
# run higher. This threshold is for the fake only; the real one lives in app/config.py.
FAKE_MAX_DISTANCE = 0.75  # relevant hits score <= 0.70, off-topic >= 0.83 (measured)


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def store(fake_llm: FakeLLM) -> VectorStore:
    # A unique collection name per test keeps the in-memory Chroma state isolated.
    vector_store = VectorStore.in_memory(f"test_{uuid.uuid4().hex}", fake_llm)
    ingest(vector_store, replace(settings, chunk_size=800, chunk_overlap=120))
    return vector_store


@pytest.fixture
def pipeline(store: VectorStore, fake_llm: FakeLLM) -> RAGPipeline:
    return RAGPipeline(store, fake_llm, top_k=4, max_distance=FAKE_MAX_DISTANCE)
