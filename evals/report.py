"""Render eval results as a Markdown report that reads well on GitHub."""

from evals.metrics import ItemScore


def failure_reasons(score: ItemScore) -> list[str]:
    if score.passed:
        return []
    if score.should_refuse:
        return ["answered an out-of-scope question instead of refusing"]
    reasons = []
    if score.refused:
        reasons.append(
            "gate refused (no chunk under the threshold)" if score.gate_refused else "model refused"
        )
        return reasons
    if not score.hit:
        reasons.append("expected source not retrieved")
    if score.terms_found < score.terms_total:
        reasons.append(f"missing facts ({score.terms_found}/{score.terms_total} found)")
    if not score.cited:
        reasons.append("no citation")
    elif not score.cited_expected_source:
        reasons.append("cited the wrong source")
    return reasons


def _pct(value: float) -> str:
    return f"{value:.0%}"


def _clip(text: str, limit: int = 160) -> str:
    text = " ".join(text.split()).replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render_report(meta: dict, summary: dict, scores: list[ItemScore], records: list[dict]) -> str:
    retrieval, refusal, answer = summary["retrieval"], summary["refusal"], summary["answer"]
    lines = [
        "# Eval report: Ask Ledgerly",
        "",
        f"Run on {meta['date']} · chat `{meta['chat_model']}` · embeddings `{meta['embed_model']}` · "
        f"top_k {meta['top_k']} · max_distance {meta['max_distance']} · {meta['machine']} · "
        f"avg {meta['avg_latency_s']} s per answer",
        "",
        f"**Overall pass rate: {_pct(summary['pass_rate'])}** ({summary['items']} golden questions). "
        "An answerable item passes when it is not refused, states every required fact and cites the "
        "right policy file. An out-of-scope item passes when it is refused.",
        "",
        "## Retrieval (answerable questions)",
        "",
        "| Metric | Value | Meaning |",
        "|---|---|---|",
        f"| Hit rate | {_pct(retrieval['hit_rate'])} | an expected policy file was in the retrieved chunks |",
        f"| MRR | {retrieval['mrr']} | 1 = the right file was always ranked first |",
        f"| Source recall | {_pct(retrieval['source_recall'])} | share of expected files retrieved "
        "(matters for multi-hop) |",
        "",
        "## Refusals",
        "",
        "| Metric | Value | Meaning |",
        "|---|---|---|",
        f"| Correct refusals | {_pct(refusal['correct_refusals'])} | out-of-scope questions refused |",
        f"| Refused by the gate | {_pct(refusal['refused_by_gate'])} | of those, refused before calling the "
        "model |",
        f"| False refusals | {_pct(refusal['false_refusals'])} | answerable questions wrongly refused |",
        "",
        "## Answers (answerable questions)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Required facts present | {_pct(answer['term_coverage'])} |",
        f"| Has a citation | {_pct(answer['cited_rate'])} |",
        f"| Cites an expected source | {_pct(answer['cited_expected_source_rate'])} |",
        "",
        "## Pass rate by category",
        "",
        "| Category | Pass rate |",
        "|---|---|",
        *[f"| {category} | {_pct(rate)} |" for category, rate in summary["by_category"].items()],
        "",
    ]

    by_id = {r["id"]: r for r in records}
    failures = [s for s in scores if not s.passed]
    lines += ["## Failures", ""]
    if not failures:
        lines.append("None.")
    else:
        lines += ["| Item | Why | Question | Answer |", "|---|---|---|---|"]
        for score in failures:
            record = by_id[score.id]
            lines.append(
                f"| {score.id} | {'; '.join(failure_reasons(score))} | {_clip(record['question'], 80)} "
                f"| {_clip(record['answer'])} |"
            )
    lines.append("")
    return "\n".join(lines)
