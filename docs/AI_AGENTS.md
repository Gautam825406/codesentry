# AI Agents

## The graph

LangGraph `StateGraph` (`agents/graph.py`): `START` fans out to three agent
nodes, which converge on a filter node, then a patch node, then `END`.
Parallel nodes write separate state keys — three nodes writing one `drafts`
key would silently overwrite each other (a bug found during development).

## Agents

| Agent | Mandate | Typical findings |
|---|---|---|
| Security | Exploitability and data flow | SQL/OS/command injection (CWE-89/78), unsafe deserialisation (CWE-502), path traversal (CWE-22), XSS (CWE-79), code injection (CWE-94), hard-coded credentials (CWE-798) |
| Logic | Correctness against contracts | bare `except`, swallowed exceptions, unguarded division, mutable default args, resource leaks |
| Style | Opted-in maintainability only | >60-line functions, duplicated bodies, stub functions |

## How the security agent reasons (heuristic taint)

1. **Source:** a function parameter in the changed symbol.
2. **Taint:** that value is interpolated into a string (f-string, `+`, `.format`, JS template literal).
3. **Sink:** a dangerous call in the changed symbol — or in a direct callee
   whose body executes its argument (call-graph context). A sink with no
   tainted input is not a finding; a parameterised call (`execute("... %s", (x,))`)
   is explicitly not a finding.
4. Direct-parameter sinks (`pickle.loads(data)`, `eval(data)`) are findings
   without interpolation, because the parameter itself is the vulnerability.

This is **heuristic taint analysis, not a verified data-flow proof** — the
product says so wherever it matters.

## LLM modes

- `deterministic` (default): the rule engine above. No key, no cost, no
  network. Findings are real and tested.
- `groq`: `GROQ_API_KEY` → Groq chat completions (`llama-3.3-70b-versatile`
  by default). Model output must parse as JSON and validate as `FindingDraft`;
  invalid output is dropped. It still passes citation verification.
- `ollama`: `OLLAMA_HOST` → local Qwen2.5-Coder, for code that must not leave
  the host.

## Finding contract

Every finding carries: source, category, severity, title, description, file,
start/end line, exact evidence, CWE id + title + OWASP ref (security only),
confidence 0–1, patch (optional, validated), model/prompt version, context
provenance. The filter drops anything uncited, below threshold, duplicated,
previously rejected, on an excluded path, or a security finding without a
valid CWE. Suppressed findings are persisted with a reason and shown on the
run-detail page.

## LoRA fine-tuning

Feedback → dataset (`training/dataset_builder.py`): only verified correctness
verdicts (`accept`/`fixed` = correct, `reject_wrong` = incorrect) from
authorised reviewers, only on opt-in repositories, deduplicated by code hash,
split 70/15/15 train/val/held-out by hash. Training (`scripts/train_lora.py`,
PEFT/Unsloth) requires a CUDA GPU; without one the adapter stays
`not_started` with the reason recorded — never claimed. Promotion
(`training/lora.py::promote`) is blocked unless the held-out gate passes
(high-severity precision must not decline, high-severity recall must not fall
materially). Rollback is one API call.
