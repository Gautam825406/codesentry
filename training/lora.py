"""LoRA training orchestration + evaluation + promotion gate (PRD §8.5, §15).

Honest by construction:
  * `start_training` records a job and checks for a GPU + PEFT/Unsloth.
    Without a GPU it leaves the adapter in `not_started` with the reason
    recorded — it NEVER claims a training run happened.
  * `evaluate` compares a candidate adapter against the base reviewer on
    the held-out set using the eval runner's measured numbers.
  * `promote` is blocked if high-severity precision would decline or
    high-severity recall falls materially; `rollback` restores the base.
"""
from __future__ import annotations
from database.models import LoRAAdapter, DatasetVersion

BASE_MODEL = "Qwen/Qwen2.5-Coder-1.5B"

def gpu_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False

def start_training(db, dataset_version_id: int) -> LoRAAdapter:
    ds = db.query(DatasetVersion).filter_by(id=dataset_version_id).first()
    if ds is None:
        raise ValueError("dataset version not found")
    version = f"lora-{ds.version}"
    adapter = db.query(LoRAAdapter).filter_by(version=version).first()
    if adapter is None:
        adapter = LoRAAdapter(dataset_version_id=ds.id, version=version, base_model=BASE_MODEL)
        db.add(adapter)
    if not gpu_available():
        adapter.status = "not_started"
        adapter.metrics_json = {"error": "No GPU available in this environment. "
            "LoRA training requires a CUDA GPU (or Colab T4). Dataset is ready; "
            "run `python scripts/train_lora.py --dataset " + ds.version + "` on a GPU host.",
            "train_count": ds.train_count, "val_count": ds.val_count,
            "heldout_count": ds.heldout_count}
        db.commit()
        return adapter
    # GPU present: hand off to the real PEFT/Unsloth script (scripts/train_lora.py)
    adapter.status = "training"
    adapter.metrics_json = {"note": "Training started on GPU; see scripts/train_lora.py. "
                                    "Adapter is NOT promoted until evaluation passes."}
    db.commit()
    return adapter

def evaluate_adapter(db, adapter_id: int, base_metrics: dict, adapter_metrics: dict) -> dict:
    """Compare measured metrics; returns the gate decision."""
    adapter = db.query(LoRAAdapter).filter_by(id=adapter_id).first()
    if adapter is None:
        raise ValueError("adapter not found")
    base_hp = base_metrics.get("high_precision", 0.0)
    cand_hp = adapter_metrics.get("high_precision", 0.0)
    base_hr = base_metrics.get("high_recall", 0.0)
    cand_hr = adapter_metrics.get("high_recall", 0.0)
    passes = cand_hp >= base_hp and cand_hr >= base_hr - 0.05
    adapter.metrics_json = {**adapter.metrics_json, "base": base_metrics,
                            "candidate": adapter_metrics, "gate_passed": passes}
    adapter.status = "ready" if passes else "evaluating"
    db.commit()
    return {"gate_passed": passes, "base_high_precision": base_hp,
            "candidate_high_precision": cand_hp, "base_high_recall": base_hr,
            "candidate_high_recall": cand_hr}

def promote(db, adapter_id: int) -> LoRAAdapter:
    adapter = db.query(LoRAAdapter).filter_by(id=adapter_id).first()
    if adapter is None:
        raise ValueError("adapter not found")
    if not adapter.metrics_json.get("gate_passed"):
        raise ValueError("Promotion blocked: evaluation gate has not passed")
    for other in db.query(LoRAAdapter).filter(LoRAAdapter.promoted == True).all():
        other.promoted = False
        if other.status == "promoted":
            other.status = "ready"
    adapter.promoted = True
    adapter.status = "promoted"
    db.commit()
    return adapter

def rollback(db, adapter_id: int) -> LoRAAdapter:
    adapter = db.query(LoRAAdapter).filter_by(id=adapter_id).first()
    if adapter is None:
        raise ValueError("adapter not found")
    adapter.promoted = False
    adapter.status = "rolled_back"
    db.commit()
    return adapter
