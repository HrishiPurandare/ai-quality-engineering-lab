"""The golden dataset is test data, so it is tested like code."""

import json
from collections import Counter

import pytest

from app.config import settings
from evals.dataset import GoldenItem, load_golden, validate


@pytest.fixture(scope="module")
def golden() -> list[GoldenItem]:
    return load_golden()


def test_golden_dataset_is_valid(golden):
    assert validate(golden, settings.policies_dir) == []


def test_golden_dataset_size_and_balance(golden):
    assert 30 <= len(golden) <= 60
    counts = Counter(item.category for item in golden)
    # Enough negative cases to measure refusals, and every policy file is covered.
    assert counts["out_of_scope"] >= 5
    assert counts["multi_hop"] >= 2
    covered = {source for item in golden for source in item.expected_sources}
    assert covered == {p.name for p in settings.policies_dir.glob("*.md")}


def _item(**overrides) -> GoldenItem:
    data = {
        "id": "x-01",
        "category": "fact",
        "question": "What is the SWIFT fee?",
        "expected_answer": "AED 30 per transfer.",
        "expected_sources": ["fees-and-charges.md"],
        "must_include": ["AED 30"],
        "should_refuse": False,
    }
    return GoldenItem(**{**data, **overrides})


@pytest.mark.parametrize(
    ("overrides", "problem"),
    [
        ({"category": "trivia"}, "unknown category"),
        ({"expected_sources": ["missing.md"]}, "does not exist"),
        ({"expected_sources": []}, "needs at least one expected source"),
        ({"must_include": ["AED 99"], "expected_answer": "AED 99"}, "not in the expected sources"),
        ({"must_include": ["AED 30"], "expected_answer": "Thirty dirhams."}, "missing from expected_answer"),
        ({"should_refuse": True}, "refusal item cannot have"),
        ({"question": "  "}, "must not be empty"),
    ],
)
def test_validate_catches_broken_items(overrides, problem):
    problems = validate([_item(**overrides)], settings.policies_dir)
    assert any(problem in p for p in problems), problems


def test_validate_catches_duplicate_ids():
    problems = validate([_item(), _item()], settings.policies_dir)
    assert any("duplicate id" in p for p in problems)


def test_load_golden_reports_the_bad_line(tmp_path):
    path = tmp_path / "bad.jsonl"
    good = json.dumps({"id": "a", "category": "fact", "question": "q", "expected_answer": "a"})
    path.write_text(f"{good}\n{{not json}}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bad.jsonl:2"):
        load_golden(path)
