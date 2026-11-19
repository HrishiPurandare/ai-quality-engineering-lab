"""Quality gate: compare eval and red-team results against rules, and fail the build if any breaks.

Usage (after a smoke eval and a red-team run):
    python -m evals.gate --eval evals/results/ci/summary.json --redteam redteam/results/ci/summary.json

Rules live in evals/quality_gate.json, e.g. {"metric": "eval.pass_rate", "op": ">=", "value": 0.9}.
Metric names are paths into the result files: "eval.refusal.false_refusals" reads
summary["refusal"]["false_refusals"] from the eval summary.

Exit code 0 = all rules pass, 1 = at least one broke, 2 = a metric is missing (a broken pipeline
must never look like a passing one). A Markdown table goes to stdout and, in GitHub Actions, to the
job summary page.
"""

import argparse
import json
import operator
import os
import sys
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "quality_gate.json"
OPS = {">=": operator.ge, "<=": operator.le, ">": operator.gt, "<": operator.lt, "==": operator.eq}


@dataclass(frozen=True)
class Check:
    metric: str
    op: str
    threshold: float
    value: float | None  # None = the metric was missing from the results

    @property
    def passed(self) -> bool:
        return self.value is not None and OPS[self.op](self.value, self.threshold)


def load_config(path: Path = CONFIG_PATH) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    for rule in config["rules"]:
        if rule["op"] not in OPS:
            raise ValueError(f"unknown operator {rule['op']!r} in rule for {rule['metric']}")
    return config


def lookup(results: dict, metric: str) -> float | None:
    """Follow a dotted path like "eval.refusal.false_refusals" through nested dicts."""
    node = results
    for key in metric.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return float(node) if isinstance(node, (int, float)) and not isinstance(node, bool) else None


def evaluate(results: dict, rules: list[dict]) -> list[Check]:
    return [Check(r["metric"], r["op"], r["value"], lookup(results, r["metric"])) for r in rules]


def render(checks: list[Check], context: str = "") -> str:
    failed = [c for c in checks if not c.passed]
    verdict = "✅ Quality gate passed" if not failed else f"❌ Quality gate failed ({len(failed)} rule(s))"
    lines = [f"## {verdict}", ""]
    if context:
        lines += [context, ""]
    lines += ["| Metric | Value | Rule | Result |", "|---|---|---|---|"]
    for c in checks:
        value = "missing" if c.value is None else f"{c.value:.3f}"
        lines.append(
            f"| `{c.metric}` | {value} | {c.op} {c.threshold} | {'pass' if c.passed else '**FAIL**'} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--eval", type=Path, required=True, help="evals summary.json")
    parser.add_argument("--redteam", type=Path, required=True, help="red-team summary.json")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()

    config = load_config(args.config)
    eval_file = json.loads(args.eval.read_text(encoding="utf-8"))
    redteam_file = json.loads(args.redteam.read_text(encoding="utf-8"))
    results = {"eval": eval_file["summary"], "redteam": redteam_file["summary"]}
    checks = evaluate(results, config["rules"])

    meta = eval_file.get("meta", {})
    context = (
        f"{eval_file['summary']['items']} golden items · {redteam_file['summary']['attacks']} attacks · "
        f"chat `{meta.get('chat_model', '?')}` · guardrails {meta.get('guardrails', '?')} · "
        f"avg {meta.get('avg_latency_s', '?')} s per answer"
    )
    report = render(checks, context)
    print(report)
    if summary_path := os.getenv("GITHUB_STEP_SUMMARY"):
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(report)

    if any(c.value is None for c in checks):
        sys.exit(2)
    sys.exit(0 if all(c.passed for c in checks) else 1)


if __name__ == "__main__":
    main()
