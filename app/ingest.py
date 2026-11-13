"""Build (or rebuild) the vector index from the policy documents.

Usage: python -m app.ingest
"""

from app.chunking import chunk_directory
from app.config import Settings, settings
from app.llm import LLM, OllamaClient
from app.store import VectorStore


def ingest(store: VectorStore, cfg: Settings) -> int:
    chunks = chunk_directory(cfg.policies_dir, cfg.chunk_size, cfg.chunk_overlap)
    store.reset()  # full rebuild keeps the index in sync with the documents
    store.add(chunks)
    return len(chunks)


def build_store(llm: LLM, cfg: Settings = settings) -> VectorStore:
    return VectorStore.persistent(str(cfg.chroma_dir), cfg.collection, llm)


if __name__ == "__main__":
    client = OllamaClient(settings)
    if not client.is_available():
        raise SystemExit(f"Ollama is not reachable at {settings.ollama_url}. Start it with: ollama serve")
    count = ingest(build_store(client), settings)
    print(f"Indexed {count} chunks from {settings.policies_dir} into {settings.chroma_dir}")
