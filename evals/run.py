"""Run the golden dataset through the real assistant and score it (no judge model needed).

Usage:
    python -m evals.run               # all items, ~8 s per answer on an M1 with llama3.2:3b
    python -m evals.run --limit 5     # quick check

Writes to evals/results/: answers.jsonl (raw answers, reused by the judge), summary.json, REPORT.md
"""

import argparse
import json
import platform
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path

from app.config import settings
from app.ingest import build_store, ingest
from app.llm import OllamaClient
from app.rag import RAGPipeline
from evals.dataset import GoldenItem, load_golden, validate
from evals.gate import load_config
from evals.metrics import ItemScore, score_item, summarise
from evals.report import render_report

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def evaluate_item(pipeline: RAGPipeline, item: GoldenItem) -> tuple[dict, ItemScore]:
    """Ask one golden question and score it. Returns the raw record and its score."""
    # All top-k hits with distances (for threshold tuning), then the ones the model actually sees.
    raw_hits = pipeline.store.search(item.question, pipeline.top_k)
    kept = [h for h in raw_hits if h.distance <= pipeline.max_distance]

    started = time.perf_counter()
    answer = pipeline.ask(item.question)
    latency = round(time.perf_counter() - started, 2)

    cited_sources = [c.source for c in answer.citations]
    score = score_item(
        item_id=item.id,
        category=item.category,
        should_refuse=item.should_refuse,
        expected_sources=item.expected_sources,
        must_include=item.must_include,
        retrieved_sources=[h.source for h in kept],
        answer=answer.answer,
        refused=answer.refused,
        cited_sources=cited_sources,
    )
    record = {
        "id": item.id,
        "category": item.category,
        "question": item.question,
        "expected_answer": item.expected_answer,
        "should_refuse": item.should_refuse,
        "answer": answer.answer,
        "refused": answer.refused,
        "cited_sources": cited_sources,
        "contexts": answer.contexts,
        "retrieved": [
            {"source": h.source, "section": h.section, "distance": round(h.distance, 3)} for h in raw_hits
        ],
        "guardrails": answer.guardrails,
        "latency_s": latency,
        "passed": score.passed,
    }
    return record, score


def run(pipeline: RAGPipeline, items: list[GoldenItem]) -> tuple[list[dict], list[ItemScore]]:
    records, scores = [], []
    for n, item in enumerate(items, start=1):
        record, score = evaluate_item(pipeline, item)
        records.append(record)
        scores.append(score)
        verdict = "PASS" if score.passed else "FAIL"
        print(f"[{n:>2}/{len(items)}] {verdict} {item.id:<8} {record['latency_s']:>5}s  {item.question}")
    return records, scores


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--limit", type=int, help="only run the first N items")
    parser.add_argument(
        "--smoke", action="store_true", help="only the smoke items in evals/quality_gate.json"
    )
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    parser.add_argument("--guardrails", choices=["on", "off"], default="on" if settings.guardrails else "off")
    args = parser.parse_args()

    items = load_golden()
    problems = validate(items, settings.policies_dir)
    if problems:
        raise SystemExit("Golden dataset is invalid:\n" + "\n".join(problems))
    if args.smoke:
        smoke_ids = set(load_config()["smoke_ids"])
        items = [item for item in items if item.id in smoke_ids]
    items = items[: args.limit] if args.limit else items

    llm = OllamaClient(settings)
    if not llm.is_available():
        raise SystemExit(f"Ollama is not reachable at {settings.ollama_url}. Start it with: ollama serve")
    store = build_store(llm)
    ingest(store, settings)  # always evaluate against a fresh index of the current documents
    pipeline = RAGPipeline(store, llm, settings.top_k, settings.max_distance, args.guardrails == "on")

    records, scores = run(pipeline, items)
    meta = {
        "date": date.today().isoformat(),
        "chat_model": settings.chat_model,
        "embed_model": settings.embed_model,
        "top_k": settings.top_k,
        "max_distance": settings.max_distance,
        "guardrails": args.guardrails,
        "chunk_size": settings.chunk_size,
        "machine": f"{platform.system()} {platform.machine()}",
        "avg_latency_s": round(sum(r["latency_s"] for r in records) / len(records), 2),
    }
    summary = summarise(scores)

    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "answers.jsonl").open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    (args.out / "summary.json").write_text(
        json.dumps({"meta": meta, "summary": summary, "scores": [asdict(s) for s in scores]}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (args.out / "REPORT.md").write_text(render_report(meta, summary, scores, records), encoding="utf-8")
    print(f"\npass rate {summary['pass_rate']:.0%} · report: {args.out / 'REPORT.md'}")


if __name__ == "__main__":
    main()
