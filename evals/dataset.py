"""Golden dataset: questions with known-good answers, used to score the assistant.

Each line of the JSONL file is one item. The dataset is test data, so it gets tested too:
`validate()` catches broken items before they produce misleading scores.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from evals.metrics import contains_term

GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "ledgerly_golden.jsonl"

CATEGORIES = {"fact", "procedure", "reasoning", "multi_hop", "safety", "out_of_scope"}


@dataclass(frozen=True)
class GoldenItem:
    id: str
    category: str
    question: str
    expected_answer: str
    # Policy files that hold the answer. Empty for questions the bot must refuse.
    expected_sources: list[str] = field(default_factory=list)
    # Facts the answer must state, matched case-insensitively as whole terms.
    must_include: list[str] = field(default_factory=list)
    should_refuse: bool = False


def load_golden(path: Path = GOLDEN_PATH) -> list[GoldenItem]:
    items = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                items.append(GoldenItem(**json.loads(line)))
            except (json.JSONDecodeError, TypeError) as exc:
                raise ValueError(f"{path.name}:{line_no}: {exc}") from exc
    return items


def validate(items: list[GoldenItem], policies_dir: Path) -> list[str]:
    """Return a list of problems (an empty list means the dataset is valid)."""
    problems = []
    seen: set[str] = set()
    for item in items:
        where = f"[{item.id}]"
        if item.id in seen:
            problems.append(f"{where} duplicate id")
        seen.add(item.id)
        if item.category not in CATEGORIES:
            problems.append(f"{where} unknown category {item.category!r}")
        if not item.question.strip() or not item.expected_answer.strip():
            problems.append(f"{where} question and expected_answer must not be empty")

        if item.should_refuse:
            if item.expected_sources or item.must_include:
                problems.append(f"{where} a refusal item cannot have expected_sources or must_include")
            continue

        if not item.expected_sources:
            problems.append(f"{where} an answerable item needs at least one expected source")
        source_text = ""
        for source in item.expected_sources:
            path = policies_dir / source
            if not path.is_file():
                problems.append(f"{where} expected source {source!r} does not exist")
            else:
                source_text += path.read_text(encoding="utf-8")

        # A required term must be in our own expected answer AND in the source documents.
        # Otherwise the item is checking for a fact the bot could never find.
        for term in item.must_include:
            if not contains_term(item.expected_answer, term):
                problems.append(f"{where} must_include {term!r} is missing from expected_answer")
            if source_text and not contains_term(source_text, term):
                problems.append(f"{where} must_include {term!r} is not in the expected sources")
    return problems
