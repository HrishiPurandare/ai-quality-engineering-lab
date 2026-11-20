"""Trend report and drift detection across quality-gate runs.

The gate answers "is THIS run good enough?". This module answers "is it getting worse, and why?":

- every run is appended to a history file (metrics, each question's verdict, each attack's verdict);
- each new run is compared with the last COMPARABLE run (same questions, same attack set);
- it flags metric drops bigger than a tolerance, even when the gate still passes (slow decay);
- it lists questions that flipped pass -> fail, and says whether anything changed between the runs.
  If nothing changed (same inputs, same config, same model files), the flip is FLAKINESS, not a
  regression: the model gave a different answer to the same question.

Drift findings are warnings by default: the gate decides pass/fail, the trend explains movement.

Usage:
    python -m evals.trend record --eval evals/results/ci --redteam redteam/results/ci --source local
    python -m evals.trend report       # rebuild evals/history/TREND.md from the history file
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from evals.gate import load_config, lookup

ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = Path(__file__).resolve().parent / "history"
HISTORY_PATH = HISTORY_DIR / "history.jsonl"
TREND_PATH = HISTORY_DIR / "TREND.md"
LATENCY = "eval.avg_latency_s"
CONFIG_KEYS = ("chat_model", "embed_model", "top_k", "max_distance", "guardrails", "chunk_size")
# Everything that can change an answer. A commit that only touches docs leaves this hash unchanged.
INPUT_PATHS = ("app", "data", "evals/golden", "evals/quality_gate.json", "redteam", "requirements.txt")
INPUT_SUFFIXES = {".py", ".md", ".jsonl", ".json", ".txt"}
SPARK = "▁▂▃▄▅▆▇█"


# ---------- building a history row ----------


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def suite_id(item_ids: list[str]) -> str:
    """Name a question set by its size and content, so runs on different sets are never compared."""
    digest = hashlib.sha1(",".join(sorted(item_ids)).encode()).hexdigest()[:6]
    return f"{len(item_ids)} questions #{digest}"


def _is_input(path: str) -> bool:
    if Path(path).suffix not in INPUT_SUFFIXES:  # also skips __pycache__/*.pyc
        return False
    # Results written by the runs themselves are outputs, not inputs.
    return "/results/" not in f"/{path}" and not path.startswith(("evals/history", "redteam/results"))


def _blob_id(data: bytes) -> str:
    """The id git gives a file's contents, so the working tree and a commit hash the same way."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def inputs_fingerprint(root: Path = ROOT, commit: str | None = None) -> str:
    """Hash every file that can change an answer: from the working tree, or from a past commit."""
    if commit:
        out = subprocess.run(
            ["git", "ls-tree", "-r", commit, "--", *INPUT_PATHS],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        entries = [(line.split("\t")[1], line.split()[2]) for line in out.splitlines()]
    else:
        entries = []
        for name in INPUT_PATHS:
            base = root / name
            files = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file())
            entries += [(p.relative_to(root).as_posix(), _blob_id(p.read_bytes())) for p in files]
    lines = sorted(f"{path} {blob}" for path, blob in entries if _is_input(path))
    return hashlib.sha1("\n".join(lines).encode()).hexdigest()[:10]


def current_commit(root: Path = ROOT) -> str:
    if sha := os.getenv("GITHUB_SHA"):
        return sha[:7]
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def model_runtime(ollama_url: str, models: list[str]) -> dict:
    """Ollama version and the exact model files used. A re-pulled tag can silently change the model."""
    try:
        version = httpx.get(f"{ollama_url}/api/version", timeout=3).json().get("version")
        tags = httpx.get(f"{ollama_url}/api/tags", timeout=3).json().get("models", [])
    except (httpx.HTTPError, ValueError):
        return {}
    names = {m["name"]: m["digest"][:12] for m in tags}
    names |= {n.removesuffix(":latest"): d for n, d in names.items()}
    return {"ollama": version, "models": {m: names.get(m) for m in models}}


def build_row(
    eval_dir: Path,
    redteam_dir: Path | None,
    rules: list[dict],
    *,
    source: str,
    commit: str,
    inputs: str,
    runtime: dict | None = None,
    run_url: str = "",
) -> dict:
    eval_file = json.loads((eval_dir / "summary.json").read_text(encoding="utf-8"))
    meta = eval_file["meta"]
    answers = load_jsonl(eval_dir / "answers.jsonl")
    results = {"eval": {**eval_file["summary"], "avg_latency_s": meta.get("avg_latency_s")}}
    attacks, attack_set = {}, None
    if redteam_dir:
        rows = load_jsonl(redteam_dir / "results.jsonl")
        summary_path = redteam_dir / "summary.json"
        if summary_path.exists():
            redteam_file = json.loads(summary_path.read_text(encoding="utf-8"))
        else:  # runs from before summary.json existed: rebuild it from the saved verdicts
            from redteam.run import summarise

            meta_path = redteam_dir / "meta.json"
            redteam_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            redteam_file = {"meta": redteam_meta, "summary": summarise(rows)}
        results["redteam"] = redteam_file["summary"]
        attack_set = redteam_file["meta"].get("attack_set", "main")
        attacks = {r["id"]: r["defended"] for r in rows}
    return {
        "date": meta["date"],
        "source": source,
        "commit": commit,
        "run_url": run_url,
        "suite": suite_id([a["id"] for a in answers]),
        "attack_set": attack_set,
        "machine": meta.get("machine", "?"),
        "inputs": inputs,
        "config": {key: meta.get(key) for key in CONFIG_KEYS},
        "runtime": runtime or {},
        "metrics": {metric: lookup(results, metric) for metric in tracked_metrics(rules)},
        "items": {
            a["id"]: {
                "passed": a["passed"],
                "top_source": a["retrieved"][0]["source"] if a["retrieved"] else None,
            }
            for a in answers
        },
        "attacks": attacks,
    }


# ---------- comparing runs ----------


def tracked_metrics(rules: list[dict]) -> list[str]:
    return [r["metric"] for r in rules] + [LATENCY]


def higher_is_better(rules: list[dict]) -> dict[str, bool]:
    """Read the direction from the gate rule: '>=' means higher is better, '<=' lower."""
    return {r["metric"]: r["op"] in (">=", ">") for r in rules if r["op"] != "=="}


def comparable(history: list[dict], row: dict) -> list[dict]:
    """Earlier runs on the same question set. Attack verdicts additionally need the same attack set."""
    return [r for r in history if r["suite"] == row["suite"]]


def _same_attacks(a: dict, b: dict) -> bool:
    return a["attack_set"] is not None and a["attack_set"] == b["attack_set"]


def what_changed(before: dict, after: dict) -> list[str]:
    """Everything that differs between two runs and could explain a different answer."""
    changes = [
        f"{k}: {before['config'].get(k)} -> {after['config'].get(k)}"
        for k in CONFIG_KEYS
        if before["config"].get(k) != after["config"].get(k)
    ]
    if before.get("inputs") != after.get("inputs"):
        changes.append("code or data")
    if before["machine"] != after["machine"]:
        changes.append(f"machine: {before['machine']} -> {after['machine']}")
    old, new = before.get("runtime") or {}, after.get("runtime") or {}
    if old.get("ollama") and new.get("ollama") and old["ollama"] != new["ollama"]:
        changes.append(f"ollama: {old['ollama']} -> {new['ollama']}")
    for model, digest in (new.get("models") or {}).items():
        previous = (old.get("models") or {}).get(model)
        if previous and digest and previous != digest:
            changes.append(f"model file {model}: {previous} -> {digest}")
    return changes


@dataclass
class Drift:
    baseline: dict | None = None
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    regressed: list[str] = field(default_factory=list)  # question passed last time, fails now
    fixed: list[str] = field(default_factory=list)
    retrieval_moved: list[str] = field(default_factory=list)  # top retrieved document changed
    attacks_broken: list[str] = field(default_factory=list)
    attacks_fixed: list[str] = field(default_factory=list)

    @property
    def flaky(self) -> bool:
        """Verdicts moved although nothing that could change an answer did."""
        moved = self.regressed or self.fixed or self.attacks_broken or self.attacks_fixed
        return bool(self.baseline and not self.changes and moved)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def compare(history: list[dict], row: dict, rules: list[dict], drift_cfg: dict) -> Drift:
    previous_runs = comparable(history, row)
    if not previous_runs:
        return Drift()
    prev = previous_runs[-1]
    window = previous_runs[-drift_cfg.get("window", 5) :]
    tolerance = drift_cfg.get("tolerance", 0.05)
    drift = Drift(baseline=prev, changes=what_changed(prev, row))

    for metric, higher in higher_is_better(rules).items():
        now, before = row["metrics"].get(metric), prev["metrics"].get(metric)
        if now is None or before is None or (metric.startswith("redteam.") and not _same_attacks(prev, row)):
            continue
        drop = (before - now) if higher else (now - before)
        if drop > tolerance + 1e-9:
            drift.warnings.append(f"`{metric}` got worse: {before:.3f} -> {now:.3f} (vs previous run)")
            continue
        # Slow decay: each step is small, but the run is clearly worse than the recent average.
        values = [
            r["metrics"][metric]
            for r in window
            if r["metrics"].get(metric) is not None
            and (not metric.startswith("redteam.") or _same_attacks(r, row))
        ]
        if len(values) >= 2:
            average = _mean(values)
            decay = (average - now) if higher else (now - average)
            if decay > tolerance + 1e-9:
                drift.warnings.append(
                    f"`{metric}` is {now:.3f}, worse than the average of the last {len(values)} runs "
                    f"({average:.3f})"
                )

    now, before = row["metrics"].get(LATENCY), prev["metrics"].get(LATENCY)
    limit = drift_cfg.get("latency_increase", 0.5)
    # Latency is only comparable on the same kind of machine (an M1 is ~3x faster than a CI runner).
    if now and before and row["machine"] == prev["machine"] and now > before * (1 + limit):
        drift.warnings.append(f"`{LATENCY}` rose {before:.2f} s -> {now:.2f} s (more than {limit:.0%})")

    for item_id, item in row["items"].items():
        old = prev["items"].get(item_id)
        if old is None:
            continue
        if old["passed"] and not item["passed"]:
            drift.regressed.append(item_id)
        elif item["passed"] and not old["passed"]:
            drift.fixed.append(item_id)
        if old["top_source"] != item["top_source"]:
            drift.retrieval_moved.append(item_id)
    for attack_id, defended in row["attacks"].items() if _same_attacks(prev, row) else []:
        old = prev["attacks"].get(attack_id)
        if old is True and not defended:
            drift.attacks_broken.append(attack_id)
        elif old is False and defended:
            drift.attacks_fixed.append(attack_id)
    if drift.regressed:
        drift.warnings.append(
            f"{len(drift.regressed)} question(s) went from pass to fail: " + ", ".join(drift.regressed)
        )
    if drift.attacks_broken:
        drift.warnings.append(
            f"{len(drift.attacks_broken)} attack(s) now get through: " + ", ".join(drift.attacks_broken)
        )
    return drift


def flake_counts(history: list[dict]) -> dict[str, int]:
    """How often each question flipped between two comparable runs where nothing changed."""
    counts: dict[str, int] = {}
    for i, row in enumerate(history):
        earlier = comparable(history[:i], row)
        if not earlier or what_changed(earlier[-1], row):
            continue
        prev = earlier[-1]
        for item_id, item in row["items"].items():
            old = prev["items"].get(item_id)
            if old is not None and old["passed"] != item["passed"]:
                counts[item_id] = counts.get(item_id, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


# ---------- reports ----------


def render_drift(row: dict, drift: Drift) -> str:
    lines = ["## Drift vs previous comparable run", ""]
    if drift.baseline is None:
        return "\n".join(lines + [f"First run of this suite ({row['suite']}): nothing to compare yet.", ""])
    base = drift.baseline
    lines.append(f"Compared with {base['date']} · {base['source']} · `{base['commit']}` ({row['suite']}).")
    lines.append("")
    if drift.changes:
        lines.append("Changed since then: " + "; ".join(drift.changes) + ".")
    else:
        lines.append("Nothing that can change an answer changed (code, data, config, machine).")
        if not (base.get("runtime") and row.get("runtime")):
            lines.append(
                "Model versions weren't recorded for both runs, so a re-pulled model can't be ruled out."
            )
    lines.append("")
    if drift.flaky:
        lines += [
            "**Flaky:** verdicts moved with nothing changed, so this is the model being "
            "non-deterministic, not a regression. Make the check or the prompt more robust.",
            "",
        ]
    lines += [f"- ⚠️ {w}" for w in drift.warnings] or ["- No drift beyond tolerance."]
    for label, ids in (
        ("Fixed (fail -> pass)", drift.fixed),
        ("Top retrieved document changed", drift.retrieval_moved),
        ("Attacks now defended", drift.attacks_fixed),
    ):
        if ids:
            lines.append(f"- {label}: {', '.join(ids)}")
    return "\n".join(lines) + "\n"


def sparkline(values: list[float | None]) -> str:
    known = [v for v in values if v is not None]
    if not known:
        return ""
    low, high = min(known), max(known)
    if high == low:
        return "".join("·" if v is None else SPARK[3] for v in values)
    return "".join(
        "·" if v is None else SPARK[round((v - low) / (high - low) * (len(SPARK) - 1))] for v in values
    )


def _fmt(value: float | None, digits: int = 3) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def render_trend(history: list[dict], rules: list[dict], drift_cfg: dict) -> str:
    metrics = tracked_metrics(rules)
    short = {m: m.split(".")[-1] for m in metrics}
    lines = [
        "# Quality trend: Ask Ledgerly",
        "",
        "Generated by `python -m evals.trend` from [history.jsonl](history.jsonl). One row per run; runs are "
        "only compared with runs on the same question set. Drift tolerance: "
        f"{drift_cfg.get('tolerance', 0.05)} on any gated metric.",
        "",
    ]
    suites: dict[str, list[dict]] = {}
    for row in history:
        suites.setdefault(row["suite"], []).append(row)
    for suite, rows in sorted(suites.items(), key=lambda kv: kv[1][-1]["date"], reverse=True):
        header = "| Trend (oldest → newest) | Metric | First | Latest |"
        lines += [f"## {suite}", "", header, "|---|---|---|---|"]
        for m in metrics:
            values = [r["metrics"].get(m) for r in rows]
            first, last = (_fmt(v, 2 if m == LATENCY else 3) for v in (values[0], values[-1]))
            lines.append(f"| `{sparkline(values)}` | {m} | {first} | {last} |")
        lines += [
            "",
            "| Date | Source | Commit | Machine | Guardrails | "
            + " | ".join(short[m] for m in metrics)
            + " |",
            "|" + "---|" * (5 + len(metrics)),
        ]
        for r in rows:
            commit = f"[`{r['commit']}`]({r['run_url']})" if r.get("run_url") else f"`{r['commit']}`"
            guardrails = r["config"].get("guardrails") or "-"
            values = " | ".join(_fmt(r["metrics"].get(m), 2 if m == LATENCY else 3) for m in metrics)
            lines.append(
                f"| {r['date']} | {r['source']} | {commit} | {r['machine']} | {guardrails} | {values} |"
            )
        flakes = flake_counts(rows)
        lines += [
            "",
            "Flaky questions (flipped with nothing changed): "
            + (", ".join(f"{k} ×{v}" for k, v in flakes.items()) or "none seen yet")
            + ".",
            "",
        ]
        latest = rows[-1]
        drift = compare(rows[:-1], latest, rules, drift_cfg)
        lines.append(render_drift(latest, drift).replace("## ", "### "))
    return "\n".join(lines).rstrip() + "\n"


def load_history(path: Path) -> list[dict]:
    return load_jsonl(path) if path.exists() else []


def append_row(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("record", help="add a run to the history and report drift")
    record.add_argument("--eval", type=Path, required=True, help="eval results folder")
    record.add_argument("--redteam", type=Path, help="red-team results folder")
    record.add_argument("--source", default="local", help="where it ran, e.g. local, ci-push, ci-schedule")
    record.add_argument("--commit", help="defaults to GITHUB_SHA or git HEAD")
    record.add_argument(
        "--inputs-from-commit",
        action="store_true",
        help="hash inputs as of --commit (for recording past runs), not the working tree",
    )
    record.add_argument("--run-url", default="")
    record.add_argument("--no-runtime", action="store_true", help="don't ask Ollama for versions")
    record.add_argument("--fail-on-drift", action="store_true", help="exit 1 if any drift warning")
    report = sub.add_parser("report", help="rebuild TREND.md from the history")
    for p in (record, report):
        p.add_argument("--history", type=Path, default=HISTORY_PATH)
        p.add_argument("--trend", type=Path, default=TREND_PATH)
    args = parser.parse_args()

    config = load_config()
    rules, drift_cfg = config["rules"], config.get("drift", {})
    history = load_history(args.history)

    if args.command == "record":
        from app.config import settings

        commit = args.commit or current_commit()
        runtime = (
            {}
            if args.no_runtime
            else model_runtime(settings.ollama_url, [settings.chat_model, settings.embed_model])
        )
        row = build_row(
            args.eval,
            args.redteam,
            rules,
            source=args.source,
            commit=commit,
            inputs=inputs_fingerprint(commit=commit if args.inputs_from_commit else None),
            runtime=runtime,
            run_url=args.run_url,
        )
        drift = compare(history, row, rules, drift_cfg)
        append_row(args.history, row)
        history.append(row)
        text = render_drift(row, drift)
        print(text)
        if summary_path := os.getenv("GITHUB_STEP_SUMMARY"):
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(text)
        if os.getenv("GITHUB_ACTIONS"):
            for warning in drift.warnings:  # yellow annotations on the run page, without failing it
                print(f"::warning title=Quality drift::{warning.replace('`', '')}")

    args.trend.parent.mkdir(parents=True, exist_ok=True)
    args.trend.write_text(render_trend(history, rules, drift_cfg), encoding="utf-8")
    print(f"trend report: {args.trend}")
    if args.command == "record" and args.fail_on_drift and drift.warnings:
        sys.exit(1)


if __name__ == "__main__":
    main()
