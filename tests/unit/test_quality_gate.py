"""The CI quality gate. A gate that can't fail is decoration, so every branch is tested."""

import json
import subprocess
import sys

import pytest

from evals.dataset import CATEGORIES, load_golden
from evals.gate import CONFIG_PATH, Check, evaluate, load_config, lookup, render

RESULTS = {
    "eval": {"pass_rate": 0.92, "refusal": {"false_refusals": 0.0, "correct_refusals": 1.0}},
    "redteam": {"attack_success_rate": 0.0},
}


def test_lookup_follows_dotted_paths_and_reports_missing_metrics():
    assert lookup(RESULTS, "eval.refusal.false_refusals") == 0.0
    assert lookup(RESULTS, "eval.pass_rate") == 0.92
    assert lookup(RESULTS, "eval.refusal.nope") is None
    assert lookup(RESULTS, "eval.refusal") is None  # a dict is not a number
    assert lookup({"eval": {"flag": True}}, "eval.flag") is None  # nor is a bool


@pytest.mark.parametrize(
    ("op", "threshold", "value", "passed"),
    [
        (">=", 0.9, 0.9, True),  # the boundary passes
        (">=", 0.9, 0.89, False),
        ("<=", 0.05, 0.05, True),
        ("<=", 0.05, 0.0455, True),  # 1 of 22 attacks
        ("<=", 0.05, 0.0909, False),  # 2 of 22 attacks
    ],
)
def test_rule_boundaries(op, threshold, value, passed):
    assert Check("m", op, threshold, value).passed is passed


def test_a_missing_metric_fails_the_rule():
    [check] = evaluate(RESULTS, [{"metric": "eval.typo", "op": ">=", "value": 0}])
    assert check.value is None and not check.passed


def test_report_names_every_failed_rule():
    checks = evaluate(
        RESULTS,
        [
            {"metric": "eval.pass_rate", "op": ">=", "value": 0.95},
            {"metric": "redteam.attack_success_rate", "op": "<=", "value": 0.05},
        ],
    )
    report = render(checks)
    assert "❌ Quality gate failed (1 rule(s))" in report
    assert "| `eval.pass_rate` | 0.920 | >= 0.95 | **FAIL** |" in report
    assert "| `redteam.attack_success_rate` | 0.000 | <= 0.05 | pass |" in report


def test_config_is_valid_and_the_smoke_set_covers_every_category():
    config = load_config()
    golden = {item.id: item for item in load_golden()}
    assert set(config["smoke_ids"]) <= set(golden), "smoke id not in the golden dataset"
    assert {golden[i].category for i in config["smoke_ids"]} == CATEGORIES
    assert any(golden[i].should_refuse for i in config["smoke_ids"])  # refusals are gated too


def test_unknown_operator_is_rejected(tmp_path):
    bad = tmp_path / "gate.json"
    bad.write_text(json.dumps({"smoke_ids": [], "rules": [{"metric": "m", "op": "=>", "value": 1}]}))
    with pytest.raises(ValueError, match="unknown operator"):
        load_config(bad)


def _run_gate(tmp_path, eval_summary: dict, redteam_summary: dict) -> subprocess.CompletedProcess:
    (tmp_path / "eval.json").write_text(json.dumps({"meta": {}, "summary": eval_summary}))
    (tmp_path / "rt.json").write_text(json.dumps({"meta": {}, "summary": redteam_summary}))
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "evals.gate",
            "--eval",
            tmp_path / "eval.json",
            "--redteam",
            tmp_path / "rt.json",
        ],
        capture_output=True,
        text=True,
        env={"PATH": "", "PYTHONPATH": str(CONFIG_PATH.parent.parent)},
    )


GOOD_EVAL = {
    "items": 12,
    "pass_rate": 1.0,
    "retrieval": {"hit_rate": 1.0},
    "refusal": {"correct_refusals": 1.0, "false_refusals": 0.0},
    "answer": {"cited_rate": 1.0},
}
GOOD_REDTEAM = {"attacks": 22, "attack_success_rate": 0.0}


def test_exit_codes(tmp_path):
    assert _run_gate(tmp_path, GOOD_EVAL, GOOD_REDTEAM).returncode == 0
    broken = _run_gate(tmp_path, {**GOOD_EVAL, "pass_rate": 0.5}, GOOD_REDTEAM)
    assert broken.returncode == 1 and "**FAIL**" in broken.stdout
    # A pipeline that lost a metric must not look like a pass or an ordinary failure.
    missing = {key: value for key, value in GOOD_EVAL.items() if key != "answer"}
    assert _run_gate(tmp_path, missing, GOOD_REDTEAM).returncode == 2
