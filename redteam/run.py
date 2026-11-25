"""Run the red-team attacks against the real assistant and report which ones got through.

Usage:
    python -m redteam.run              # 22 attacks, ~2 min on an M1 with llama3.2:3b
    python -m redteam.run --limit 5
    python -m redteam.run --guardrails off --out redteam/results/baseline   # unprotected
    python -m redteam.run --holdout --out redteam/results/holdout           # unseen attacks
    python -m redteam.run --rescore --out redteam/results/guarded           # re-check saved answers

Writes redteam/results/results.jsonl and REDTEAM_REPORT.md.
"""

import argparse
import json
import uuid
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from app.chunking import chunk_directory
from app.config import Settings, settings
from app.llm import LLM, OllamaClient
from app.rag import RAGPipeline
from app.store import VectorStore
from redteam.checks import CHECKS

ROOT = Path(__file__).resolve().parent
ATTACKS_PATH = ROOT / "attacks.jsonl"
# Written AFTER the guardrails, to measure whether they generalise beyond the attacks they were tuned on.
HOLDOUT_PATH = ROOT / "attacks_holdout.jsonl"
POISONED_DIR = ROOT / "poisoned"
RESULTS_DIR = ROOT / "results"
CORPORA = {"clean", "poisoned"}


@dataclass(frozen=True)
class Attack:
    id: str
    category: str
    corpus: str
    prompt: str
    checks: list[str]


def load_attacks(path: Path = ATTACKS_PATH) -> list[Attack]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Attack(**json.loads(line)) for line in lines if line.strip()]


def validate_attacks(attacks: list[Attack]) -> list[str]:
    problems = []
    ids = [a.id for a in attacks]
    problems += [f"[{i}] duplicate id" for i in sorted({i for i in ids if ids.count(i) > 1})]
    for a in attacks:
        if a.corpus not in CORPORA:
            problems.append(f"[{a.id}] unknown corpus {a.corpus!r}")
        if not a.checks:
            problems.append(f"[{a.id}] needs at least one check")
        problems += [f"[{a.id}] unknown check {c!r}" for c in a.checks if c not in CHECKS]
    return problems


def build_pipelines(llm: LLM, cfg: Settings) -> dict[str, RAGPipeline]:
    """A clean index of the real policies, and a poisoned one with an attacker's document added.

    Both are in-memory, so the red team never touches the app's real index.
    """
    policies = chunk_directory(cfg.policies_dir, cfg.chunk_size, cfg.chunk_overlap)
    poison = chunk_directory(POISONED_DIR, cfg.chunk_size, cfg.chunk_overlap)
    pipelines = {}
    for corpus, chunks in {"clean": policies, "poisoned": policies + poison}.items():
        store = VectorStore.in_memory(f"redteam_{corpus}_{uuid.uuid4().hex[:8]}", llm)
        store.add(chunks)
        pipelines[corpus] = RAGPipeline(store, llm, cfg.top_k, cfg.max_distance, cfg.guardrails)
    return pipelines


def attack_once(pipelines: dict[str, RAGPipeline], attack: Attack) -> dict:
    pipeline = pipelines[attack.corpus]
    # Record what retrieval passed to the model: an attack the gate blocks never tests the model,
    # and an indirect injection whose poisoned chunk isn't retrieved never tests anything.
    hits = pipeline.retrieve(attack.prompt)
    poisoned_sources = {p.name for p in POISONED_DIR.glob("*.md")}
    answer = pipeline.ask(attack.prompt)
    results = {name: CHECKS[name](answer.answer) for name in attack.checks}
    return {
        "id": attack.id,
        "category": attack.category,
        "corpus": attack.corpus,
        "prompt": attack.prompt,
        "answer": answer.answer,
        "refused": answer.refused,
        "guardrails": answer.guardrails,
        "retrieved": [{"source": h.source, "distance": round(h.distance, 3)} for h in hits],
        "reached_model": bool(hits),
        "poison_retrieved": any(h.source in poisoned_sources for h in hits),
        "checks": results,
        "failed_checks": [name for name, ok in results.items() if not ok],
        "defended": all(results.values()),
    }


def rescore(rows: list[dict], attacks: list[Attack]) -> list[dict]:
    """Re-apply the CURRENT detectors to saved answers, without calling the model again.

    Use this after fixing a detector: the answers stay the same, only the verdicts change.
    """
    by_id = {a.id: a for a in attacks}
    for row in rows:
        results = {name: CHECKS[name](row["answer"]) for name in by_id[row["id"]].checks}
        row.update(
            checks=results,
            failed_checks=[name for name, ok in results.items() if not ok],
            defended=all(results.values()),
        )
    return rows


def summarise(rows: list[dict]) -> dict:
    by_category: dict[str, list[bool]] = {}
    for row in rows:
        by_category.setdefault(row["category"], []).append(row["defended"])
    return {
        "attacks": len(rows),
        "defended": sum(r["defended"] for r in rows),
        # Attack success rate: the headline red-team number. Lower is better.
        "attack_success_rate": round(sum(not r["defended"] for r in rows) / len(rows), 3) if rows else 0.0,
        "by_category": {c: f"{sum(v)}/{len(v)}" for c, v in sorted(by_category.items())},
        "reached_model": sum(r["reached_model"] for r in rows),
        # Indirect attacks only count if the poisoned chunk was actually retrieved.
        "invalid_indirect": [
            r["id"] for r in rows if r["corpus"] == "poisoned" and not r["poison_retrieved"]
        ],
    }


def render_report(meta: dict, summary: dict, rows: list[dict]) -> str:
    lines = [
        "# Red-team report: NovaAsk",
        "",
        f"Run on {meta['date']} · chat `{meta['chat_model']}` · {summary['attacks']} attacks · "
        f"attack set: {meta.get('attack_set', 'main')} · guardrails: {meta['guardrails']}",
        "",
        f"**Attack success rate: {summary['attack_success_rate']:.0%}** "
        f"({summary['attacks'] - summary['defended']} of {summary['attacks']} attacks got through). "
        "Lower is better.",
        "",
        f"- {summary['reached_model']} of {summary['attacks']} attacks reached the model "
        "(the rest were refused by the retrieval gate before generation).",
        "- Indirect injections where the poisoned document was NOT retrieved (invalid tests): "
        f"{', '.join(summary['invalid_indirect']) or 'none'}.",
        "",
        "| Category | Defended |",
        "|---|---|",
        *[f"| {c} | {v} |" for c, v in summary["by_category"].items()],
        "",
        "## Attacks that got through",
        "",
    ]
    broken = [r for r in rows if not r["defended"]]
    if not broken:
        lines.append("None.")
    else:
        lines += ["| Attack | Failed check | Prompt | Answer |", "|---|---|---|---|"]
        for r in broken:
            prompt = " ".join(r["prompt"].split()).replace("|", "\\|")[:90]
            answer = " ".join(r["answer"].split()).replace("|", "\\|")[:200]
            lines.append(f"| {r['id']} | {', '.join(r['failed_checks'])} | {prompt} | {answer} |")
    lines += [
        "",
        "## Every answer",
        "",
        "Read these too: a check can pass while the answer is still poor (wrong tone, off-role, unhelpful).",
        "",
        "| Attack | Defended | Guardrail fired | Answer |",
        "|---|---|---|---|",
    ]
    for r in rows:
        answer = " ".join(r["answer"].split()).replace("|", "\\|")[:160]
        fired = ", ".join(r.get("guardrails") or []) or "-"
        lines.append(f"| {r['id']} | {'yes' if r['defended'] else '**no**'} | {fired} | {answer} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    parser.add_argument("--guardrails", choices=["on", "off"], default="on" if settings.guardrails else "off")
    parser.add_argument("--holdout", action="store_true", help="run the held-out attacks instead")
    parser.add_argument(
        "--rescore",
        action="store_true",
        help="re-check the saved answers in --out with the current detectors",
    )
    args = parser.parse_args()

    attacks = load_attacks(HOLDOUT_PATH if args.holdout else ATTACKS_PATH)
    problems = validate_attacks(attacks)
    if problems:
        raise SystemExit("attacks.jsonl is invalid:\n" + "\n".join(problems))
    attacks = attacks[: args.limit] if args.limit else attacks

    if args.rescore:
        saved = args.out / "results.jsonl"
        rows = rescore([json.loads(line) for line in saved.read_text(encoding="utf-8").splitlines()], attacks)
        write_results(args.out, json.loads((args.out / "meta.json").read_text(encoding="utf-8")), rows)
        return

    llm = OllamaClient(settings)
    if not llm.is_available():
        raise SystemExit(f"Ollama is not reachable at {settings.ollama_url}. Start it with: ollama serve")
    pipelines = build_pipelines(llm, replace(settings, guardrails=args.guardrails == "on"))

    rows = []
    for n, attack in enumerate(attacks, start=1):
        row = attack_once(pipelines, attack)
        rows.append(row)
        verdict = "defended" if row["defended"] else f"BROKEN ({', '.join(row['failed_checks'])})"
        print(f"[{n:>2}/{len(attacks)}] {attack.id:<8} {verdict}")

    meta = {
        "date": date.today().isoformat(),
        "chat_model": settings.chat_model,
        "guardrails": args.guardrails,
        "attack_set": "holdout" if args.holdout else "main",
    }
    write_results(args.out, meta, rows)


def write_results(out: Path, meta: dict, rows: list[dict]) -> None:
    summary = summarise(rows)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "results.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    # For the CI quality gate (evals/gate.py): same shape as the eval runner's summary.json.
    (out / "summary.json").write_text(
        json.dumps({"meta": meta, "summary": summary}, indent=2) + "\n", encoding="utf-8"
    )
    (out / "REDTEAM_REPORT.md").write_text(render_report(meta, summary, rows), encoding="utf-8")
    print(f"attack success rate {summary['attack_success_rate']:.0%} · report: {out / 'REDTEAM_REPORT.md'}")


if __name__ == "__main__":
    main()
