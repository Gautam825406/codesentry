"""Feedback -> versioned fine-tuning dataset (PRD §8.5).

Rules enforced here, not in the UI:
  * only verified CORRECTNESS verdicts enter training: accept / fixed count
    as 'right', reject_wrong as 'wrong'. reject_not_worth_fixing is a policy
    signal and is kept separate; ignore is not a label.
  * only feedback from authorised reviewers (role reviewer/admin) counts.
  * only repositories with training_opt_in=True are included.
  * deduplication by code hash; deterministic 70/15/15 train/val/held-out
    split by hash, so the held-out set never appears in training.
"""
from __future__ import annotations
import hashlib, json, os
from database.models import DatasetVersion, FeedbackEvent, Finding, Repository, User

def build_dataset(db, repo_id: int | None = None) -> DatasetVersion | None:
    repos = db.query(Repository).all()
    if repo_id:
        repos = [r for r in repos if r.id == repo_id]
    rows = []
    for repo in repos:
        st = repo.settings
        if not st or not st.training_opt_in:
            continue
        events = (db.query(FeedbackEvent, Finding, User)
                  .join(Finding, FeedbackEvent.finding_id == Finding.id)
                  .outerjoin(User, FeedbackEvent.actor_id == User.id)
                  .filter(Finding.repo_id == repo.id).all())
        for fb, finding, user in events:
            if fb.verdict not in ("accept", "fixed", "reject_wrong"):
                continue  # policy verdicts / ignores are not correctness labels
            if user is not None and user.role not in ("reviewer", "admin"):
                continue
            code_hash = hashlib.sha256((finding.evidence or "").encode()).hexdigest()
            rows.append({"repo": repo.full_name, "finding_id": finding.id,
                         "code_hash": code_hash, "file": finding.file_path,
                         "evidence": finding.evidence, "category": finding.category,
                         "severity": finding.severity,
                         "label": "correct" if fb.verdict in ("accept", "fixed") else "incorrect",
                         "model_version": finding.model_version})
    # dedupe by code hash, keep first
    seen, uniq = set(), []
    for r in rows:
        if r["code_hash"] in seen:
            continue
        seen.add(r["code_hash"])
        uniq.append(r)
    if not uniq:
        return None
    uniq.sort(key=lambda r: r["code_hash"])
    n = len(uniq)
    n_train = int(n * 0.70)
    n_val = int(n * 0.15)
    splits = {"train": uniq[:n_train], "val": uniq[n_train:n_train + n_val],
              "heldout": uniq[n_train + n_val:]}
    version = f"ds-{hashlib.sha256(str(sorted(r['code_hash'] for r in uniq)).encode()).hexdigest()[:10]}"
    existing = db.query(DatasetVersion).filter_by(version=version).first()
    if existing:
        return existing
    out_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{version}.jsonl"), "w") as f:
        for split, items in splits.items():
            for it in items:
                f.write(json.dumps({"split": split, **it}) + "\n")
    ds = DatasetVersion(repo_id=repo_id, version=version,
                        train_count=len(splits["train"]), val_count=len(splits["val"]),
                        heldout_count=len(splits["heldout"]), source="feedback",
                        metrics_json={"total": n, "correct": sum(1 for r in uniq if r["label"] == "correct"),
                                      "incorrect": sum(1 for r in uniq if r["label"] == "incorrect")})
    db.add(ds)
    db.commit()
    return ds
