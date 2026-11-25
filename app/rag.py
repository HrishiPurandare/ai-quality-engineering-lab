"""Retrieval-augmented generation: retrieve -> filter -> prompt -> answer -> citations."""

import re
from dataclasses import dataclass, field

from app import guardrails
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
    # Which guardrail rules fired (empty when guardrails are off or nothing fired),
    # e.g. ["input:override_instructions"] or ["context:dropped_instructions", "output:code"].
    guardrails: list[str] = field(default_factory=list)


class RAGPipeline:
    def __init__(
        self, store: VectorStore, llm: LLM, top_k: int, max_distance: float, guardrails: bool = False
    ):
        self.store = store
        self.llm = llm
        self.top_k = top_k
        self.max_distance = max_distance
        self.guardrails = guardrails

    def retrieve(self, question: str) -> list[Retrieved]:
        hits = self.store.search(question, self.top_k)
        return [h for h in hits if h.distance <= self.max_distance]

    def ask(self, question: str) -> Answer:
        question = question.strip()
        if not question:
            raise ValueError("question must not be empty")
        fired: list[str] = []

        if self.guardrails:
            verdict = guardrails.check_input(question)
            if verdict.blocked_by:
                # Blocked before retrieval: the model never sees the attack.
                return Answer(
                    question=question,
                    answer=guardrails.BLOCKED_REPLY,
                    refused=True,
                    guardrails=[verdict.blocked_by],
                )
            if verdict.redacted:
                fired.append("input:redacted_card")
            question = verdict.text

        relevant = self.retrieve(question)
        if not relevant:
            # Nothing relevant was retrieved: refuse without calling the model,
            # so it has no chance to make something up.
            return Answer(question=question, answer=NO_ANSWER, refused=True, guardrails=fired)

        passages = [hit.text for hit in relevant]
        if self.guardrails:
            cleaned = [guardrails.sanitise_passage(p) for p in passages]
            passages = [text for text, _ in cleaned]
            if any(changed for _, changed in cleaned):
                fired.append("context:dropped_instructions")

        reply = self.llm.chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(question, passages)},
            ]
        )

        if self.guardrails:
            broken_rule = guardrails.check_output(reply)
            if broken_rule:
                fired.append(broken_rule)
                return Answer(
                    question=question,
                    answer=guardrails.UNSAFE_OUTPUT_REPLY,
                    contexts=passages,
                    refused=True,
                    guardrails=fired,
                )

        refused = NO_ANSWER in reply
        # A refusal has no sources, even if the model tacks a citation marker onto it
        # ("I don't have that information... [1]"): showing a source would imply it answered.
        cited = (
            []
            if refused
            else sorted({int(n) for n in re.findall(r"\[(\d+)\]", reply) if 1 <= int(n) <= len(relevant)})
        )
        return Answer(
            question=question,
            answer=reply,
            citations=[
                Citation(number=n, source=relevant[n - 1].source, section=relevant[n - 1].section)
                for n in cited
            ],
            contexts=passages,
            refused=refused,
            guardrails=fired,
        )
