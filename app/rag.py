"""Retrieval-augmented generation: retrieve -> filter -> prompt -> answer -> citations."""

import re
from dataclasses import dataclass, field

from app.llm import LLM
from app.prompts import NO_ANSWER, SYSTEM_PROMPT, build_user_prompt
from app.store import Retrieved, VectorStore


@dataclass
class Citation:
    number: int
    source: str
    section: str


@dataclass
class Answer:
    question: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    # Every passage given to the model, cited or not. Evals (faithfulness,
    # context precision) need these, so the API returns them too.
    contexts: list[str] = field(default_factory=list)
    refused: bool = False


class RAGPipeline:
    def __init__(self, store: VectorStore, llm: LLM, top_k: int, max_distance: float):
        self.store = store
        self.llm = llm
        self.top_k = top_k
        self.max_distance = max_distance

    def retrieve(self, question: str) -> list[Retrieved]:
        hits = self.store.search(question, self.top_k)
        return [h for h in hits if h.distance <= self.max_distance]

    def ask(self, question: str) -> Answer:
        question = question.strip()
        if not question:
            raise ValueError("question must not be empty")

        relevant = self.retrieve(question)
        if not relevant:
            # Nothing relevant was retrieved: refuse without calling the model,
            # so it has no chance to make something up.
            return Answer(question=question, answer=NO_ANSWER, refused=True)

        passages = [hit.text for hit in relevant]
        reply = self.llm.chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(question, passages)},
            ]
        )
        cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", reply) if 1 <= int(n) <= len(relevant)})
        return Answer(
            question=question,
            answer=reply,
            citations=[
                Citation(number=n, source=relevant[n - 1].source, section=relevant[n - 1].section)
                for n in cited
            ],
            contexts=passages,
            refused=NO_ANSWER in reply,
        )
