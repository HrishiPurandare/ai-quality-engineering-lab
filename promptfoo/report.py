"""Turn Promptfoo's results.json into a short Markdown table that is safe to commit.

The raw results.json holds local file paths and full request logs, so it stays out of git.

Usage: python -m promptfoo.report   (after running the Promptfoo eval)
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results" / "results.json"
REPORT = HERE / "results" / "PROMPTFOO_REPORT.md"


def render(data: dict) -> str:
    rows = data["results"]["results"]
    providers = sorted({r["provider"]["label"] for r in rows})
    tests: dict[str, dict[str, dict]] = {}
    for r in rows:
        tests.setdefault(r["testCase"]["description"], {})[r["provider"]["label"]] = r
    totals = {p: sum(r["success"] for r in rows if r["provider"]["label"] == p) for p in providers}
    lines = [
        "# Promptfoo report: Ask Ledgerly",
        "",
        f"Promptfoo calls the real `/chat` API on two servers: {', '.join(f'`{p}`' for p in providers)}.",
        "",
        "| Server | Tests passed |",
        "|---|---|",
        *[f"| {p} | {totals[p]}/{len(tests)} |" for p in providers],
        "",
        "| Test | " + " | ".join(providers) + " |",
        "|---|" + "---|" * len(providers),
    ]
    for description, by_provider in tests.items():
        cells = []
        for p in providers:
            r = by_provider[p]
            output = " ".join((r.get("response") or {}).get("output", "").split()).replace("|", "\\|")[:90]
            cells.append(f"{'PASS' if r['success'] else '**FAIL**'}: {output}")
        lines.append(f"| {description} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    REPORT.write_text(render(json.loads(RESULTS.read_text(encoding="utf-8"))), encoding="utf-8")
    print(f"report: {REPORT}")


if __name__ == "__main__":
    main()
