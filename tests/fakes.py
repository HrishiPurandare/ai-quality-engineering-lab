"""Test doubles for the LLM, so unit tests are fast, free and deterministic."""

import hashlib
import math
import re

STOPWORDS = {
    "a", "an", "the", "is", "are", "to", "of", "in", "on", "for", "and", "or", "my", "i", "can",
    "how", "what", "do", "does", "it", "be", "by", "with", "at", "if", "from", "this", "that",
}  # fmt: skip


class FakeLLM:
    """Bag-of-words "embeddings" (hashed into a fixed-size vector) plus a scripted chat reply.

    Texts that share words get nearby vectors, which is enough to test retrieval logic
    without a real embedding model.
    """

    def __init__(self, reply: str = "Here is the answer [1].", dims: int = 1024):
        self.reply = reply
        self.dims = dims
        self.chat_calls: list[list[dict[str, str]]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def chat(self, messages: list[dict[str, str]]) -> str:
        self.chat_calls.append(messages)
        return self.reply

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dims
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            if word in STOPWORDS:
                continue
            index = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dims
            vec[index] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        # Chroma rejects all-zero vectors under cosine distance, so give empty text a tiny signal.
        return [v / norm for v in vec] if any(vec) else [1e-6] * self.dims
