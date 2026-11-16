"""The eval runner and report, driven by the fake LLM (no Ollama needed)."""

from evals.dataset import GoldenItem
from evals.metrics import summarise
from evals.report import failure_reasons, render_report
from evals.run import evaluate_item, run

OVERDRAFT_FEE = GoldenItem(
    id="fee-09",
    category="fact",
    question="What is the charge for an unarranged overdraft?",
    expected_answer="AED 50 per occurrence, at most once per calendar day.",
    expected_sources=["fees-and-charges.md"],
    must_include=["AED 50"],
)
OFF_TOPIC = GoldenItem(
    id="oos-05",
    category="out_of_scope",
    question="Who won the football World Cup in 2022?",
    expected_answer="I don't have that information.",
    should_refuse=True,
)
META = {
    "date": "2026-11-16",
    "chat_model": "fake",
    "embed_model": "fake",
    "top_k": 4,
    "max_distance": 0.75,
    "machine": "test",
    "avg_latency_s": 0.0,
}


def test_correct_answer_with_citation_passes(pipeline, fake_llm):
    fake_llm.reply = "An unarranged overdraft costs AED 50 per occurrence [1]."
    record, score = evaluate_item(pipeline, OVERDRAFT_FEE)
    assert score.hit
    assert score.passed, failure_reasons(score)
    assert record["cited_sources"] and record["contexts"]
    # Raw hits keep their distances so the threshold can be tuned from the results.
    assert all("distance" in hit for hit in record["retrieved"])


def test_wrong_fact_fails_with_a_reason(pipeline, fake_llm):
    fake_llm.reply = "An unarranged overdraft costs AED 5 [1]."
    _, score = evaluate_item(pipeline, OVERDRAFT_FEE)
    assert not score.passed
    assert failure_reasons(score) == ["missing facts (0/1 found)"]


def test_off_topic_is_refused_by_the_gate_without_calling_the_model(pipeline, fake_llm):
    record, score = evaluate_item(pipeline, OFF_TOPIC)
    assert score.passed and score.gate_refused
    assert record["refused"]
    assert fake_llm.chat_calls == []


def test_report_lists_failures(pipeline, fake_llm):
    fake_llm.reply = "It is free [1]."
    records, scores = run(pipeline, [OVERDRAFT_FEE, OFF_TOPIC])
    report = render_report(META, summarise(scores), scores, records)
    assert "**Overall pass rate: 50%**" in report
    assert "| fee-09 | missing facts (0/1 found) |" in report
    assert "oos-05 |" not in report
