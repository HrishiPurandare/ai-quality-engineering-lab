"""Trend and drift detection. A drift alarm that cries wolf gets ignored, so both directions are tested."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from evals.gate import load_config
from evals.trend import (
    LATENCY,
    ROOT,
    build_row,
    compare,
    flake_counts,
    inputs_fingerprint,
    render_drift,
    render_trend,
    sparkline,
    suite_id,
    what_changed,
)

RULES = load_config()["rules"]
DRIFT = {"tolerance": 0.05, "window": 5, "latency_increase": 0.5}


def make_row(
    pass_rate=1.0,
    *,
    items=None,
    attacks=None,
    asr=0.0,
    latency=4.0,
    machine="Darwin arm64",
    inputs="abc",
    guardrails="on",
    attack_set="main",
    runtime=None,
) -> dict:
    items = items if items is not None else {"q1": True, "q2": True}
    return {
        "date": "2026-11-20",
        "source": "local",
        "commit": "c0ffee1",
        "run_url": "",
        "suite": suite_id(list(items)),
        "attack_set": attack_set,
        "machine": machine,
        "inputs": inputs,
        "config": {"chat_model": "llama3.2:3b", "guardrails": guardrails},
        "runtime": runtime or {},
        "metrics": {
            "eval.pass_rate": pass_rate,
            "eval.refusal.false_refusals": 0.0,
            "redteam.attack_success_rate": asr,
            LATENCY: latency,
        },
        "items": {i: {"passed": ok, "top_source": "fees.md"} for i, ok in items.items()},
        "attacks": attacks if attacks is not None else {"a1": True},
    }


def test_suite_id_depends_on_the_questions_not_their_order():
    assert suite_id(["b", "a"]) == suite_id(["a", "b"])
    assert suite_id(["a", "b"]) != suite_id(["a", "c"])
    assert suite_id(["a", "b"]).startswith("2 questions")


def test_first_run_of_a_suite_has_nothing_to_compare():
    drift = compare([], make_row(), RULES, DRIFT)
    assert drift.baseline is None and not drift.warnings
    assert "First run" in render_drift(make_row(), drift)


def test_runs_on_a_different_question_set_are_never_compared():
    other = make_row(items={"x1": True})
    assert compare([other], make_row(), RULES, DRIFT).baseline is None


def test_a_drop_within_tolerance_is_not_drift():
    drift = compare([make_row(0.95)], make_row(0.92), RULES, DRIFT)
    assert drift.warnings == []


def test_a_drop_beyond_tolerance_is_drift_even_if_the_gate_still_passes():
    # 0.92 still passes the >= 0.9 gate rule; the trend still calls out the fall from 1.0.
    drift = compare([make_row(1.0)], make_row(0.92), RULES, DRIFT)
    assert any("eval.pass_rate" in w and "1.000 -> 0.920" in w for w in drift.warnings)


def test_direction_comes_from_the_gate_rule():
    # attack_success_rate has a '<=' rule, so going UP is the bad direction.
    worse = compare([make_row(asr=0.0)], make_row(asr=0.09), RULES, DRIFT)
    better = compare([make_row(asr=0.09)], make_row(asr=0.0), RULES, DRIFT)
    assert any("attack_success_rate" in w for w in worse.warnings)
    assert not any("attack_success_rate" in w for w in better.warnings)


def test_slow_decay_is_caught_against_the_recent_average():
    # Each step drops 0.03 (under tolerance), but the latest run is 0.06 below the average.
    history = [make_row(1.0), make_row(0.97), make_row(0.94)]
    drift = compare(history, make_row(0.91), RULES, DRIFT)
    assert any("average of the last 3 runs" in w for w in drift.warnings)


def test_latency_is_only_compared_on_the_same_machine():
    slow_ci = make_row(latency=15.0, machine="Linux x86_64")
    assert not any(LATENCY in w for w in compare([make_row()], slow_ci, RULES, DRIFT).warnings)
    slow_mac = make_row(latency=7.0)
    assert any(LATENCY in w for w in compare([make_row()], slow_mac, RULES, DRIFT).warnings)


def test_question_flips_are_listed_both_ways():
    before = make_row(items={"q1": True, "q2": False})
    after = make_row(items={"q1": False, "q2": True})
    drift = compare([before], after, RULES, DRIFT)
    assert drift.regressed == ["q1"] and drift.fixed == ["q2"]
    assert any("pass to fail: q1" in w for w in drift.warnings)


def test_a_flip_with_nothing_changed_is_flaky_not_a_regression():
    drift = compare([make_row()], make_row(items={"q1": False, "q2": True}), RULES, DRIFT)
    assert drift.changes == [] and drift.flaky
    assert "**Flaky:**" in render_drift(make_row(), drift)


def test_a_flip_after_a_code_change_is_not_called_flaky():
    after = make_row(items={"q1": False, "q2": True}, inputs="def")
    drift = compare([make_row()], after, RULES, DRIFT)
    assert drift.changes == ["code or data"] and not drift.flaky


def test_what_changed_names_config_machine_and_model_files():
    before = make_row(runtime={"ollama": "0.40.14", "models": {"llama3.2:3b": "aaa"}})
    after = make_row(
        guardrails="off",
        machine="Linux x86_64",
        runtime={"ollama": "0.40.14", "models": {"llama3.2:3b": "bbb"}},
    )
    changes = what_changed(before, after)
    assert "guardrails: on -> off" in changes
    assert "machine: Darwin arm64 -> Linux x86_64" in changes
    assert "model file llama3.2:3b: aaa -> bbb" in changes  # a silently re-pulled model


def test_attacks_are_only_compared_within_the_same_attack_set():
    before = make_row(attacks={"a1": True})
    assert compare([before], make_row(attacks={"a1": False}), RULES, DRIFT).attacks_broken == ["a1"]
    holdout = make_row(attacks={"a1": False}, attack_set="holdout", asr=0.5)
    drift = compare([before], holdout, RULES, DRIFT)
    assert drift.attacks_broken == [] and not any("attack_success_rate" in w for w in drift.warnings)


def test_flake_counts_ignore_flips_that_had_a_cause():
    history = [
        make_row(),
        make_row(items={"q1": False, "q2": True}),  # flaky
        make_row(items={"q1": True, "q2": True}),  # flaky back
        make_row(items={"q1": True, "q2": False}, inputs="new"),  # caused by a change
    ]
    assert flake_counts(history) == {"q1": 2}


def test_sparkline_scales_to_the_series_and_marks_missing_values():
    assert sparkline([0.0, 0.5, 1.0]) == "▁▅█"
    assert sparkline([1.0, 1.0]) == "▄▄"
    assert sparkline([None, 1.0]) == "·▄"
    assert sparkline([]) == ""


def test_trend_report_groups_runs_by_suite_and_shows_flaky_questions():
    history = [make_row(), make_row(items={"q1": False, "q2": True}), make_row(items={"x": True})]
    report = render_trend(history, RULES, DRIFT)
    assert report.count("## 2 questions") == 1 and "## 1 questions" in report
    assert "Flaky questions (flipped with nothing changed): q1 ×1." in report


def test_inputs_fingerprint_ignores_outputs_and_matches_git(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "rag.py").write_text("x = 1\n")
    (tmp_path / "redteam" / "results").mkdir(parents=True)
    first = inputs_fingerprint(tmp_path)
    (tmp_path / "redteam" / "results" / "report.md").write_text("new results")  # an output
    (tmp_path / "app" / "__pycache__").mkdir()
    (tmp_path / "app" / "__pycache__" / "rag.pyc").write_bytes(b"\0")
    assert inputs_fingerprint(tmp_path) == first
    (tmp_path / "app" / "rag.py").write_text("x = 2\n")  # an input
    assert inputs_fingerprint(tmp_path) != first

    # The same files hash the same from the working tree and from a commit.
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run([*git, "add", "app"], cwd=tmp_path, check=True)
    subprocess.run([*git, "commit", "-qm", "x"], cwd=tmp_path, check=True)
    assert inputs_fingerprint(tmp_path, commit="HEAD") == inputs_fingerprint(tmp_path)


@pytest.fixture
def run_dirs(tmp_path: Path) -> tuple[Path, Path]:
    eval_dir, redteam_dir = tmp_path / "eval", tmp_path / "redteam"
    eval_dir.mkdir()
    redteam_dir.mkdir()
    summary = {
        "items": 2,
        "pass_rate": 0.5,
        "retrieval": {"hit_rate": 1.0},
        "refusal": {"correct_refusals": 1.0, "false_refusals": 0.0},
        "answer": {"cited_rate": 1.0},
    }
    meta = {"date": "2026-11-20", "machine": "Darwin arm64", "guardrails": "on", "avg_latency_s": 4.2}
    (eval_dir / "summary.json").write_text(json.dumps({"meta": meta, "summary": summary}))
    answers = [
        {"id": "q1", "passed": True, "retrieved": [{"source": "fees.md"}]},
        {"id": "q2", "passed": False, "retrieved": []},
    ]
    (eval_dir / "answers.jsonl").write_text("\n".join(json.dumps(a) for a in answers) + "\n")
    rows = [{"id": "a1", "category": "x", "corpus": "clean", "defended": True, "reached_model": True}]
    (redteam_dir / "results.jsonl").write_text(json.dumps(rows[0]) + "\n")
    return eval_dir, redteam_dir


def test_build_row_reads_the_run_files_and_rebuilds_a_missing_redteam_summary(run_dirs):
    eval_dir, redteam_dir = run_dirs  # no redteam summary.json, like runs from before day 7
    row = build_row(eval_dir, redteam_dir, RULES, source="local", commit="abc", inputs="x")
    assert row["metrics"]["eval.pass_rate"] == 0.5
    assert row["metrics"][LATENCY] == 4.2
    assert row["metrics"]["redteam.attack_success_rate"] == 0.0
    assert row["items"] == {
        "q1": {"passed": True, "top_source": "fees.md"},
        "q2": {"passed": False, "top_source": None},  # refused by the retrieval gate
    }
    assert row["attacks"] == {"a1": True}


def test_cli_records_runs_writes_the_report_and_only_fails_when_asked(run_dirs, tmp_path):
    eval_dir, redteam_dir = run_dirs
    history, trend = tmp_path / "h.jsonl", tmp_path / "TREND.md"
    base = [sys.executable, "-m", "evals.trend", "record", "--eval", str(eval_dir),
            "--redteam", str(redteam_dir), "--no-runtime", "--commit", "abc",
            "--history", str(history), "--trend", str(trend)]  # fmt: skip
    env = {"PATH": "", "HOME": str(tmp_path)}  # no GITHUB_* variables

    def run(*extra: str) -> subprocess.CompletedProcess:
        return subprocess.run([*base, *extra], capture_output=True, text=True, env=env, cwd=ROOT)

    def set_q1(passed: bool) -> None:
        answers = [json.loads(line) for line in (eval_dir / "answers.jsonl").read_text().splitlines()]
        answers[0]["passed"] = passed
        (eval_dir / "answers.jsonl").write_text("\n".join(json.dumps(a) for a in answers) + "\n")

    first = run()
    assert first.returncode == 0, first.stderr
    assert "First run" in first.stdout and trend.exists()

    set_q1(False)  # q1 regresses with nothing changed
    assert run("--fail-on-drift").returncode == 1
    set_q1(True)  # a fix is good news, not drift
    assert run("--fail-on-drift").returncode == 0
    set_q1(False)
    warned = run()  # warnings alone never fail the build
    assert warned.returncode == 0 and "pass to fail: q1" in warned.stdout
    assert len(history.read_text().splitlines()) == 4
