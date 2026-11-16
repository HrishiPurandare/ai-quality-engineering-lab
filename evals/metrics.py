"""Deterministic metrics: no judge model, so they are fast, free and repeatable.

Retrieval metrics answer "did we fetch the right policy?".
Answer checks answer "did the reply state the facts, cite a source and refuse when it should?".
"""

import re
from dataclasses import dataclass


def contains_term(text: str, term: str) -> bool:
    """Case-insensitive whole-term match: 'AED 2' matches 'AED 2.' but not 'AED 25'."""
    pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def reciprocal_rank(retrieved_sources: list[str], expected_sources: list[str]) -> float:
    """1/rank of the first retrieved chunk from an expected source; 0 if none was retrieved."""
    for rank, source in enumerate(retrieved_sources, start=1):
        if source in expected_sources:
            return 1.0 / rank
    return 0.0


def source_recall(retrieved_sources: list[str], expected_sources: list[str]) -> float:
    """Share of expected sources that appear anywhere in the retrieved chunks."""
    if not expected_sources:
        return 1.0
    return sum(1 for s in expected_sources if s in retrieved_sources) / len(expected_sources)


@dataclass
class ItemScore:
    id: str
    category: str
    should_refuse: bool
    # Retrieval (on the chunks that passed the distance threshold, i.e. what the model saw)
    hit: bool
    reciprocal_rank: float
    source_recall: float
    gate_refused: bool  # nothing passed the threshold, so the model was never called
    # Answer
    refused: bool
    refusal_correct: bool
    terms_found: int
    terms_total: int
    cited: bool
    cited_expected_source: bool

    @property
    def passed(self) -> bool:
        """Strict per-item verdict used in the report."""
        if self.should_refuse:
            return self.refused
        return not self.refused and self.terms_found == self.terms_total and self.cited_expected_source


def score_item(
    *,
    item_id: str,
    category: str,
    should_refuse: bool,
    expected_sources: list[str],
    must_include: list[str],
    retrieved_sources: list[str],
    answer: str,
    refused: bool,
    cited_sources: list[str],
) -> ItemScore:
    found = sum(1 for term in must_include if contains_term(answer, term))
    return ItemScore(
        id=item_id,
        category=category,
        should_refuse=should_refuse,
        hit=reciprocal_rank(retrieved_sources, expected_sources) > 0,
        reciprocal_rank=reciprocal_rank(retrieved_sources, expected_sources),
        source_recall=source_recall(retrieved_sources, expected_sources),
        gate_refused=not retrieved_sources,
        refused=refused,
        refusal_correct=refused == should_refuse,
        terms_found=found,
        terms_total=len(must_include),
        cited=bool(cited_sources),
        cited_expected_source=any(s in expected_sources for s in cited_sources),
    )


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def summarise(scores: list[ItemScore]) -> dict:
    answerable = [s for s in scores if not s.should_refuse]
    refusals = [s for s in scores if s.should_refuse]
    terms_total = sum(s.terms_total for s in answerable)
    return {
        "items": len(scores),
        "pass_rate": _mean([float(s.passed) for s in scores]),
        "retrieval": {
            "hit_rate": _mean([float(s.hit) for s in answerable]),
            "mrr": _mean([s.reciprocal_rank for s in answerable]),
            "source_recall": _mean([s.source_recall for s in answerable]),
        },
        "refusal": {
            # Out-of-scope questions the bot correctly refused (and how many the gate caught alone)
            "correct_refusals": _mean([float(s.refused) for s in refusals]),
            "refused_by_gate": _mean([float(s.gate_refused) for s in refusals]),
            # Answerable questions the bot wrongly refused: the cost of a strict threshold
            "false_refusals": _mean([float(s.refused) for s in answerable]),
        },
        "answer": {
            "term_coverage": round(sum(s.terms_found for s in answerable) / terms_total, 3)
            if terms_total
            else 0.0,
            "cited_rate": _mean([float(s.cited) for s in answerable]),
            "cited_expected_source_rate": _mean([float(s.cited_expected_source) for s in answerable]),
        },
        "by_category": {
            category: _mean([float(s.passed) for s in scores if s.category == category])
            for category in sorted({s.category for s in scores})
        },
    }
