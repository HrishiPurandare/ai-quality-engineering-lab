"""Thin client for a local Ollama server.

The rest of the app depends on the `LLM` protocol, not on Ollama directly,
so tests can swap in a fake model and run without a GPU, a network or a server.
"""

from typing import Protocol

import httpx

from app.config import Settings


class LLM(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def chat(self, messages: list[dict[str, str]]) -> str: ...


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._http = httpx.Client(base_url=settings.ollama_url, timeout=settings.request_timeout)

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._post("/api/embed", {"model": self.settings.embed_model, "input": texts})
        return response["embeddings"]

    def chat(self, messages: list[dict[str, str]]) -> str:
        response = self._post(
            "/api/chat",
            {
                "model": self.settings.chat_model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": self.settings.temperature},
            },
        )
        return response["message"]["content"].strip()

    def is_available(self) -> bool:
        try:
            return self._http.get("/api/tags", timeout=3).status_code == 200
        except httpx.HTTPError:
            return False

    def _post(self, path: str, payload: dict) -> dict:
        try:
            response = self._http.post(path, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama request to {path} failed: {exc}") from exc
        return response.json()
