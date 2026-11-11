"""Secret scanning on changed lines.

Values are NEVER stored or shown in full: a found secret is recorded as
its type + location + a masked value (first 3 chars + '***'). The PR
comment tells the author what to rotate without reproducing the secret.
"""
from __future__ import annotations
import math, re

PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws_access_key_id", "critical"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "github_token", "critical"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "github_pat", "critical"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "slack_token", "critical"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private_key", "critical"),
    (re.compile(r"(?i)(?:api[_-]?key|apikey|secret|password|passwd|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]"), "credential_assignment", "high"),
    (re.compile(r"sk-(?:live|test)-[A-Za-z0-9]{16,}"), "stripe_key", "critical"),
]

def _entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    return -sum((c / len(s)) * math.log2(c / len(s)) for c in freq.values())

def mask(value: str) -> str:
    return (value[:3] + "***") if len(value) > 3 else "***"

def scan_lines(path: str, lines: list[tuple[int, str]]) -> list[dict]:
    """lines: [(line_no, text)] for ADDED lines only."""
    out = []
    for lineno, text in lines:
        for rx, typ, sev in PATTERNS:
            m = rx.search(text)
            if m:
                out.append({"type": typ, "path": path, "line": lineno,
                            "severity": sev, "masked": mask(m.group(0)),
                            "evidence": text.strip()[:200].replace(m.group(0), mask(m.group(0)))})
        # high-entropy string candidates (not in comments)
        for tok in re.findall(r"['\"]([A-Za-z0-9_\-+/=]{20,})['\"]", text):
            if _entropy(tok) > 4.5 and not text.strip().startswith("#"):
                out.append({"type": "high_entropy_secret_candidate", "path": path,
                            "line": lineno, "severity": "medium", "masked": mask(tok),
                            "evidence": text.strip()[:200].replace(tok, mask(tok))})
    return out
