"""LLM-as-a-judge metrics with DeepEval, using a local Ollama model as the judge.

Run evals/run.py first: the judge scores the cached answers in evals/results/answers.jsonl,
so you can re-judge (other judge model, other thresholds) without regenerating answers.

Usage:
    pip install -r requirements-evals.txt
    ollama pull qwen2.5:3b
    python -m evals.judge --limit 10       # ~1-2 min per item on an M1 with a 3B judge
    JUDGE_MODEL=llama3.2:3b python -m evals.judge

The judge is a different model family from the chat model on purpose: a model grading its
own answers tends to be too generous (self-preference bias).
"""

import argparse
import json
import os
import time
from datetime import date
from pathlib import Path

from app.config import settings

RESULTS_DIR = Path(__file__).resolve().parent / "results"
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "qwen2.5:3b")
THRESHOLD = 0.7
METRIC_NAMES = ["faithfulness", "answer_relevancy", "contextual_precision", "contextual_recall"]

# What each metric asks the judge (shown in the report).
METRIC_HELP = {
    "faithfulness": "Is every claim in the answer supported by the retrieved context? (hallucination check)",
    "answer_relevancy": "Does the answer address the question, without padding?",
    "contextual_precision": "Are the chunks that matter ranked above the ones that don't?",
    "contextual_recall": "Does the retrieved context contain everything needed for the expected answer?",
}


def select_records(records: list[dict]) -> list[dict]:
    """Judge metrics only make sense for answered, in-scope questions with context."""
    return [r for r in records if not r["should_refuse"] and not r["refused"] and r["contexts"]]


def summarise_judge(rows: list[dict], threshold: float = THRESHOLD) -> dict:
    """Average score and pass rate per metric. Judge errors are counted, not hidden."""
    summary = {}
    for name in METRIC_NAMES:
        scores = [row["metrics"][name]["score"] for row in rows if name in row["metrics"]]
        valid = [s for s in scores if s is not None]
        summary[name] = {
            "mean": round(sum(valid) / len(valid), 3) if valid else None,
            "pass_rate": round(sum(s >= threshold for s in valid) / len(valid), 3) if valid else None,
            "judged": len(valid),
            "errors": len(scores) - len(valid),
        }
    return summary


def build_metrics(judge_model: str, threshold: float) -> dict:
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")  # keep everything local
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
    )
    from deepeval.models import OllamaModel

    # num_predict caps the reply: small models in JSON mode sometimes generate until they time out.
    judge = OllamaModel(
        model=judge_model,
        base_url=settings.ollama_url,
        temperature=0,
        generation_kwargs={"num_predict": 768},
    )
    # async_mode=False: one judge call at a time, so an 8 GB machine doesn't run out of memory.
    common = {"model": judge, "threshold": threshold, "include_reason": True, "async_mode": False}
    return {
        "faithfulness": FaithfulnessMetric(**common),
        "answer_relevancy": AnswerRelevancyMetric(**common),
        "contextual_precision": ContextualPrecisionMetric(**common),
        "contextual_recall": ContextualRecallMetric(**common),
    }


def judge_record(record: dict, metrics: dict) -> dict:
    from deepeval.test_case import LLMTestCase

    case = LLMTestCase(
        input=record["question"],
        actual_output=record["answer"],
        expected_output=record["expected_answer"],
        retrieval_context=record["contexts"],
    )
    results = {}
    for name, metric in metrics.items():
        try:
            metric.measure(case)
            results[name] = {"score": round(metric.score, 3), "reason": metric.reason}
        except Exception as exc:  # small judges sometimes return unparseable JSON
            results[name] = {"score": None, "reason": f"judge error: {type(exc).__name__}: {exc}"[:300]}
    return {"id": record["id"], "category": record["category"], "metrics": results}


def render_judge_report(meta: dict, summary: dict, rows: list[dict], threshold: float) -> str:
    lines = [
        "# LLM-judge report: NovaAsk",
        "",
        f"Run on {meta['date']} · judge `{meta['judge_model']}` (local, via Ollama) · answers from "
        f"`{meta['chat_model']}` · {meta['items']} answered questions · threshold {threshold} · "
        f"{meta['minutes']} min",
        "",
        "| Metric | Mean | Pass rate | Judged | Judge errors | Question it asks |",
        "|---|---|---|---|---|---|",
    ]
    for name in METRIC_NAMES:
        s = summary[name]
        mean = "n/a" if s["mean"] is None else s["mean"]
        rate = "n/a" if s["pass_rate"] is None else f"{s['pass_rate']:.0%}"
        lines.append(f"| {name} | {mean} | {rate} | {s['judged']} | {s['errors']} | {METRIC_HELP[name]} |")

    lines += [
        "",
        "## Lowest scores",
        "",
        "Read the judge's reason before trusting a low score: a 3B judge is cheap but noisy.",
        "",
        "| Item | Metric | Score | Judge's reason |",
        "|---|---|---|---|",
    ]
    low = [
        (row["id"], name, result)
        for row in rows
        for name, result in row["metrics"].items()
        if result["score"] is not None and result["score"] < threshold
    ]
    for item_id, name, result in sorted(low, key=lambda x: x[2]["score"])[:15]:
        reason = " ".join(str(result["reason"]).split()).replace("|", "\\|")[:220]
        lines.append(f"| {item_id} | {name} | {result['score']} | {reason} |")
    if not low:
        lines.append("| none | | | |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--limit", type=int, help="only judge the first N answered items")
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    parser.add_argument("--threshold", type=float, default=THRESHOLD)
    parser.add_argument("--results", type=Path, default=RESULTS_DIR)
    parser.add_argument("--tag", default="", help="suffix for output files, to keep several judge runs")
    args = parser.parse_args()

    answers_path = args.results / "answers.jsonl"
    if not answers_path.exists():
        raise SystemExit(f"{answers_path} not found. Run `python -m evals.run` first.")
    records = [json.loads(line) for line in answers_path.read_text(encoding="utf-8").splitlines() if line]
    selected = select_records(records)
    selected = selected[: args.limit] if args.limit else selected

    metrics = build_metrics(args.judge_model, args.threshold)
    started = time.perf_counter()
    rows = []
    for n, record in enumerate(selected, start=1):
        row = judge_record(record, metrics)
        rows.append(row)
        scores = ", ".join(f"{k}={v['score']}" for k, v in row["metrics"].items())
        print(f"[{n:>2}/{len(selected)}] {record['id']:<8} {scores}")

    meta = {
        "date": date.today().isoformat(),
        "judge_model": args.judge_model,
        "chat_model": settings.chat_model,
        "items": len(rows),
        "minutes": round((time.perf_counter() - started) / 60, 1),
    }
    summary = summarise_judge(rows, args.threshold)
    suffix = f"-{args.tag}" if args.tag else ""
    with (args.results / f"judge{suffix}.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (args.results / f"judge_summary{suffix}.json").write_text(
        json.dumps({"meta": meta, "summary": summary}, indent=2) + "\n", encoding="utf-8"
    )
    report = render_judge_report(meta, summary, rows, args.threshold)
    report_path = args.results / f"JUDGE_REPORT{suffix}.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nreport: {report_path}")


if __name__ == "__main__":
    main()
