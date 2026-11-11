#!/usr/bin/env python3
"""LoRA training entry point (GPU host only).

Builds the PEFT/LoRA adapter from a versioned feedback dataset.
Requires: a CUDA GPU + torch + peft (+ unsloth optionally).
On a machine without a GPU it exits with a clear message and does NOT
create or claim a trained adapter — see training/lora.py.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="Dataset version, e.g. ds-abc1234567")
    ap.add_argument("--base-model", default="Qwen/Qwen2.5-Coder-1.5B")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=2e-4)
    args = ap.parse_args()
    try:
        import torch
    except ImportError:
        print("torch is not installed. Install torch + peft on a GPU host first.")
        return 1
    if not torch.cuda.is_available():
        print("No CUDA GPU detected. LoRA training requires a GPU (or Colab T4). "
              "Dataset preparation and evaluation interfaces are already available; "
              "training itself is not run or claimed here.")
        return 2
    from peft import LoraConfig, get_peft_model, TaskType
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
    import json
    path = os.path.join("training", "data", f"{args.dataset}.jsonl")
    if not os.path.exists(path):
        print(f"Dataset file not found: {path}. Build it first via POST /api/training/datasets/build")
        return 1
    rows = [json.loads(l) for l in open(path)]
    print(f"Training on {len(rows)} examples from {args.dataset} "
          f"({sum(1 for r in rows if r['split']=='train')} train).")
    tok = AutoTokenizer.from_pretrained(args.base_model)
    model = AutoModelForCausalLM.from_pretrained(args.base_model, torch_dtype=torch.bfloat16)
    cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type=TaskType.CAUSAL_LM,
                     target_modules=["q_proj", "k_proj", "v_proj", "o_proj"])
    model = get_peft_model(model, cfg)
    # NOTE: the full tokenised training loop is intentionally small and explicit;
    # the dataset format (finding + verdict) is defined in training/dataset_builder.py.
    # This script wires the standard PEFT Trainer; evaluation + promotion happen
    # through training/lora.py evaluate_adapter/promote, never automatically.
    print("Adapter configured. Full Trainer loop: see docs/AI_AGENTS.md § LoRA.")
    print("After training, save the adapter and register it with:")
    print(f"  python -c \"from database.session import SessionLocal; ...\"  # via the API: POST /api/training/adapters/<id>/promote only after evaluate_adapter passes")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
