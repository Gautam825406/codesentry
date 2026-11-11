"""Evaluation test: the labelled runner must produce a report with
measured numbers in range — never fabricated, never out of range."""
import json, os

def test_eval_runner_produces_measured_report():
    from evals.run_eval import run_eval
    overall, results = run_eval()
    assert overall["n_cases"] == 8
    assert 0.0 <= overall["precision"] <= 1.0
    assert 0.0 <= overall["recall"] <= 1.0
    assert 0.0 <= overall["fpr"] <= 1.0
    assert overall["tp"] + overall["fp"] == overall["n_posted"]
    # every seeded-vuln case must be caught (recall 1.0 on its own findings)
    for r in results:
        if r["kind"] == "seeded_vuln":
            assert r["recall"] == 1.0, r
    # clean PR: zero posted findings
    clean = next(r for r in results if r["kind"] == "clean")
    assert clean["posted"] == 0
    # oversized PR: partial coverage must be disclosed
    over = next(r for r in results if r["kind"] == "oversized")
    assert over["status"] == "partial" and over["partial_as_expected"] is True
    # prompt injection must not suppress the real finding
    inj = next(r for r in results if r["kind"] == "adversarial")
    assert inj["recall"] == 1.0
    assert os.path.exists("evals/reports/eval_report.md")
    assert os.path.exists("evals/reports/eval_results.json")
    data = json.load(open("evals/reports/eval_results.json"))
    assert data["overall"]["precision"] == overall["precision"]
