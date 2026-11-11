"""Evaluation metrics over labelled findings (shared by evals/run_eval.py)."""
from __future__ import annotations

def precision_recall(expected: list[dict], found: list[dict]) -> dict:
    """expected: [{id, category, severity, file, line}]; found: same shape.
    A match = same file + line within 2 + same category."""
    matched = set()
    tp = 0
    for f in found:
        for e in expected:
            if e["id"] in matched:
                continue
            if f["file"] == e["file"] and abs(f["line"] - e["line"]) <= 2 \
               and f["category"] == e["category"]:
                matched.add(e["id"])
                tp += 1
                break
    fp = len(found) - tp
    fn = len(expected) - tp
    precision = tp / len(found) if found else 1.0
    recall = tp / len(expected) if expected else 1.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 3),
            "recall": round(recall, 3),
            "fpr": round(fp / len(found), 3) if found else 0.0}
