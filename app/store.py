"""Vector store on top of Chroma. Embeddings come from our own LLM client, not Chroma's default."""

from dataclasses import dataclass

import chromadb
from chromadb.api import ClientAPI

from app.chunking import Chunk
from app.llm import LLM


@dataclass(frozen=True)
class Retrieved:
    id: str
    text: str
    source: str
    section: str
    distance: float


class VectorStore:
    def __init__(self, client: ClientAPI, collection: str, llm: LLM):
        self.client = client
        self.name = collection
        self.llm = llm
        self.collection = self._open()

    @classmethod
    def persistent(cls, path: str, collection: str, llm: LLM) -> "VectorStore":
        return cls(chromadb.PersistentClient(path=path), collection, llm)

    @classmethod
    def in_memory(cls, collection: str, llm: LLM) -> "VectorStore":
        return cls(chromadb.EphemeralClient(), collection, llm)

    def _open(self):
        # Cosine distance suits text embeddings: it compares direction, not vector length.
        return self.client.get_or_create_collection(self.name, metadata={"hnsw:space": "cosine"})

    def reset(self) -> None:
        self.client.delete_collection(self.name)
        self.collection = self._open()

    def add(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        self.collection.add(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            embeddings=self.llm.embed([c.text for c in chunks]),
            metadatas=[{"source": c.source, "section": c.section} for c in chunks],
        )

    def count(self) -> int:
        return self.collection.count()

    def search(self, query: str, k: int) -> list[Retrieved]:
        if self.count() == 0:
            return []
        result = self.collection.query(
            query_embeddings=self.llm.embed([query]),
            n_results=min(k, self.count()),
        )
        return [
            Retrieved(
                id=result["ids"][0][i],
                text=result["documents"][0][i],
                source=result["metadatas"][0][i]["source"],
                section=result["metadatas"][0][i]["section"],
                distance=float(result["distances"][0][i]),
            )
            for i in range(len(result["ids"][0]))
        ]
