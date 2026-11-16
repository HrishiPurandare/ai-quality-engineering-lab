import pytest

from evals.metrics import contains_term, reciprocal_rank, score_item, source_recall, summarise


@pytest.mark.parametrize(
    ("text", "term", "expected"),
    [
        ("It costs AED 2.", "AED 2", True),
        ("It costs AED 25.", "AED 2", False),  # no partial-number matches
        ("a 2.5% fee", "2.5%", True),
        ("FREEZE the card", "freeze", True),
        ("antifreeze", "freeze", False),
        ("1 to 3 business days", "3 business days", True),
    ],
)
def test_contains_term(text, term, expected):
    assert contains_term(text, term) is expected


def test_reciprocal_rank():
    assert reciprocal_rank(["a.md", "b.md"], ["a.md"]) == 1.0
    assert reciprocal_rank(["b.md", "c.md", "a.md"], ["a.md"]) == pytest.approx(1 / 3)
    assert reciprocal_rank(["b.md"], ["a.md"]) == 0.0
    assert reciprocal_rank([], ["a.md"]) == 0.0


def test_source_recall_counts_each_expected_source():
    assert source_recall(["a.md", "a.md"], ["a.md", "b.md"]) == 0.5
    assert source_recall(["a.md", "b.md"], ["a.md", "b.md"]) == 1.0
    assert source_recall([], []) == 1.0


def _score(**overrides):
    args = {
        "item_id": "fee-06",
        "category": "fact",
        "should_refuse": False,
        "expected_sources": ["fees.md"],
        "must_include": ["AED 30"],
        "retrieved_sources": ["fees.md", "transfers.md"],
        "answer": "International transfers cost AED 30 [1].",
        "refused": False,
        "cited_sources": ["fees.md"],
    }
    return score_item(**{**args, **overrides})


def test_good_answer_passes():
    score = _score()
    assert score.hit and score.cited_expected_source and score.refusal_correct
    assert score.passed


def test_missing_fact_fails():
    assert not _score(answer="It is cheap [1].").passed


def test_citing_the_wrong_source_fails():
    assert not _score(cited_sources=["transfers.md"]).passed


def test_wrong_refusal_fails_and_is_flagged():
    score = _score(answer="I don't have that information.", refused=True, cited_sources=[])
    assert not score.passed
    assert not score.refusal_correct


def test_out_of_scope_refused_by_gate():
    score = _score(
        should_refuse=True,
        expected_sources=[],
        must_include=[],
        retrieved_sources=[],
        answer="I don't have that information.",
        refused=True,
        cited_sources=[],
    )
    assert score.passed and score.gate_refused


def test_summarise_splits_answerable_and_refusal_items():
    scores = [
        _score(),
        _score(item_id="fee-07", answer="No idea", refused=True, cited_sources=[]),
        _score(
            item_id="oos-01",
            category="out_of_scope",
            should_refuse=True,
            expected_sources=[],
            must_include=[],
            retrieved_sources=["fees.md"],  # slipped past the gate...
            answer="I don't have that information.",
            refused=True,  # ...but the model still refused
            cited_sources=[],
        ),
    ]
    summary = summarise(scores)
    assert summary["items"] == 3
    assert summary["pass_rate"] == pytest.approx(0.667)
    assert summary["refusal"] == {"correct_refusals": 1.0, "refused_by_gate": 0.0, "false_refusals": 0.5}
    assert summary["answer"]["term_coverage"] == 0.5
    assert summary["by_category"] == {"fact": 0.5, "out_of_scope": 1.0}
