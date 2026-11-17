"""The parts of the judge that don't need DeepEval or a judge model (so they run in CI)."""

from evals.judge import render_judge_report, select_records, summarise_judge


def _record(item_id, *, should_refuse=False, refused=False, contexts=("ctx",)):
    return {"id": item_id, "should_refuse": should_refuse, "refused": refused, "contexts": list(contexts)}


def test_only_answered_in_scope_items_are_judged():
    records = [
        _record("answered"),
        _record("wrongly-refused", refused=True),
        _record("out-of-scope", should_refuse=True, refused=True),
        _record("no-context", contexts=()),
    ]
    assert [r["id"] for r in select_records(records)] == ["answered"]


def _row(item_id, **scores):
    return {
        "id": item_id,
        "category": "fact",
        "metrics": {name: {"score": score, "reason": f"{name} reason"} for name, score in scores.items()},
    }


def test_summary_counts_judge_errors_separately():
    rows = [
        _row("a", faithfulness=1.0, answer_relevancy=0.5),
        _row("b", faithfulness=0.6, answer_relevancy=None),  # the judge returned bad JSON
    ]
    summary = summarise_judge(rows, threshold=0.7)
    assert summary["faithfulness"] == {"mean": 0.8, "pass_rate": 0.5, "judged": 2, "errors": 0}
    assert summary["answer_relevancy"] == {"mean": 0.5, "pass_rate": 0.0, "judged": 1, "errors": 1}
    assert summary["contextual_recall"]["mean"] is None


def test_report_shows_low_scores_with_reasons():
    rows = [_row("fee-01", faithfulness=0.25, answer_relevancy=1.0)]
    meta = {"date": "2026-11-16", "judge_model": "j", "chat_model": "c", "items": 1, "minutes": 0.1}
    report = render_judge_report(meta, summarise_judge(rows), rows, threshold=0.7)
    assert "| faithfulness | 0.25 | 0% | 1 | 0 |" in report
    assert "| fee-01 | faithfulness | 0.25 | faithfulness reason |" in report
    assert "contextual_recall | n/a" in report
