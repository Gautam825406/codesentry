#!/usr/bin/env python3
"""Labelled evaluation runner (PRD §13).

Runs every case in evals/datasets/labelled.json through the REAL review
pipeline on an isolated temp DB, compares posted findings with the
hand-labelled expected findings, and writes evals/reports/eval_report.md
with MEASURED precision / recall / false-positive rate / latency / cost.
Nothing here is a target copied in as a result: every number comes from
this run, with the set size N stated next to it.
"""
import json, os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Repository, RepoSettings, PullRequest, Finding
from indexer.incremental import index_files
from services.review import run_review
from training.evaluation import precision_recall

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _oversized_diff(n_files=250):
    parts = []
    for i in range(n_files):
        parts.append(f"diff --git a/app/f{i}.py b/app/f{i}.py\n--- a/app/f{i}.py\n+++ b/app/f{i}.py\n"
                     f"@@ -1 +1,2 @@\n x = 1\n+ y = 2\n")
    return "".join(parts)

def run_eval():
    with open(os.path.join(ROOT, "evals", "datasets", "labelled.json")) as f:
        dataset = json.load(f)
    tmp = tempfile.mkdtemp(prefix="codesentry-eval-")
    engine = create_engine(f"sqlite:///{os.path.join(tmp, 'eval.db')}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    results = []
    all_expected, all_found = [], []
    for idx, case in enumerate(dataset["cases"]):
        db = Session()
        repo = Repository(full_name=f"eval/{case['id']}", name=case["id"], is_demo=True)
        db.add(repo); db.commit()
        db.add(RepoSettings(repo_id=repo.id)); db.commit()
        files = dict(case.get("files") or {})
        diff = case.get("diff") or ""
        if case["id"] == "oversized-pr":
            files = {f"app/f{i}.py": "x = 1\ny = 2\n" for i in range(250)}
            diff = _oversized_diff()
        t0 = time.time()
        index_files(db, repo, files, head_sha="eval")
        pr = PullRequest(repo_id=repo.id, number=1, title=case["id"],
                         author="eval", base_sha="base", head_sha="eval", diff_text=diff)
        db.add(pr); db.commit()
        run = run_review(db, repo, pr, files)
        latency = int((time.time() - t0) * 1000)
        posted = db.query(Finding).filter_by(run_id=run.id, state="posted").all()
        found = [{"id": f"f{f.id}", "category": f.category, "severity": f.severity,
                  "file": f.file_path, "line": f.start_line} for f in posted]
        expected = case.get("expected") or []
        m = precision_recall(expected, found)
        # severity accuracy: matched findings whose severity agrees with the label
        sev_ok = 0
        for f in found:
            for e in expected:
                if f["file"] == e["file"] and abs(f["line"] - e["line"]) <= 2 and f["category"] == e["category"]:
                    if f["severity"] == e["severity"]:
                        sev_ok += 1
        m["severity_accuracy"] = round(sev_ok / m["tp"], 3) if m["tp"] else None
        partial_ok = (run.status == "partial") if case.get("expect_partial") else None
        results.append({"case": case["id"], "kind": case["kind"], **m,
                        "latency_ms": latency, "cost_usd": run.cost_usd,
                        "gate": run.gate_result, "status": run.status,
                        "coverage_pct": (run.coverage or {}).get("pct"),
                        "partial_as_expected": partial_ok,
                        "posted": len(found), "expected_n": len(expected)})
        all_expected.extend([{**e, "id": f"{case['id']}:{e['id']}"} for e in expected])
        all_found.extend([{**f, "id": f"{case['id']}:{f['id']}"} for f in found])
        db.close()
    overall = precision_recall(all_expected, all_found)
    overall["n_cases"] = len(results)
    overall["n_expected"] = len(all_expected)
    overall["n_posted"] = len(all_found)
    overall["latency_ms_p50"] = sorted(r["latency_ms"] for r in results)[len(results) // 2]
    overall["cost_per_pr_usd"] = round(sum(r["cost_usd"] for r in results) / len(results), 4)
    by_cat = {}
    for r in results:
        by_cat.setdefault(r["kind"], []).append(r)
    report = _render(dataset, results, overall)
    out_dir = os.path.join(ROOT, "evals", "reports")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "eval_report.md"), "w") as f:
        f.write(report)
    with open(os.path.join(out_dir, "eval_results.json"), "w") as f:
        json.dump({"overall": overall, "cases": results}, f, indent=2)
    print(report)
    return overall, results

def _render(dataset, results, overall):
    lines = ["# CodeSentry Evaluation Report", "",
             f"Dataset: `{dataset['version']}` — {len(results)} labelled PRs "
             f"({sum(r['expected_n'] for r in results)} expected findings).",
             "Measured by `evals/run_eval.py` through the real review pipeline "
             "(deterministic rule engine, no LLM key). Cost is $0.00 in this mode "
             "because no LLM calls are made; Groq cost would appear here when enabled.",
             "", "## Overall (all cases)", "",
             f"- Precision: **{overall['precision']}**  (TP {overall['tp']} / posted {overall['n_posted']})",
             f"- Recall: **{overall['recall']}**  (TP {overall['tp']} / expected {overall['n_expected']})",
             f"- False-positive rate: **{overall['fpr']}**",
             f"- Median review latency: **{overall['latency_ms_p50']} ms** (local, deterministic engine)",
             f"- Mean cost per PR: **${overall['cost_per_pr_usd']}**",
             "", "## Per case", "",
             "| case | kind | precision | recall | posted | expected | latency ms | gate | status |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['case']} | {r['kind']} | {r['precision']} | {r['recall']} | "
                     f"{r['posted']} | {r['expected_n']} | {r['latency_ms']} | {r['gate']} | {r['status']} |")
    lines += ["", "## Honest notes", "",
              "- Categories with zero recall are named here, not averaged away: "
              + (", ".join(f"{r['case']} (recall {r['recall']})" for r in results if r['recall'] == 0 and r['expected_n'] > 0)
                 or "none — every seeded category was caught at least once."),
              "- The clean-PR case measures false positives: any posted finding there is a false positive.",
              "- The prompt-injection case passes only if the real SQL injection is still posted despite the injected instruction.",
              "- The oversized-PR case passes only if the run reports `partial` status with skipped files disclosed.",
              "- Patch validity is enforced by construction (invalid patches are withheld); "
              "this run does not separately measure patch applicability on a larger set — that needs more labelled patches.",
              "- No LoRA fine-tuning has been run: there is no before/after false-positive comparison yet.",
              ""]
    return "\n".join(lines)

if __name__ == "__main__":
    run_eval()
