"""Finding contract (PRD §8.4) + CWE/OWASP taxonomy.

A security finding WITHOUT a valid CWE id is not a security finding —
the filter drops it. CWE titles/OWASP references come from this table only.
"""
from __future__ import annotations
from pydantic import BaseModel, Field, field_validator

CWE = {
    "CWE-89":  ("Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')", "OWASP A03:2021 — Injection"),
    "CWE-78":  ("Improper Neutralization of Special Elements used in an OS Command ('OS Command Injection')", "OWASP A03:2021 — Injection"),
    "CWE-94":  ("Improper Control of Generation of Code ('Code Injection')", "OWASP A03:2021 — Injection"),
    "CWE-79":  ("Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting')", "OWASP A03:2021 — Injection"),
    "CWE-22":  ("Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')", "OWASP A01:2021 — Broken Access Control"),
    "CWE-798": ("Use of Hard-coded Credentials", "OWASP A07:2021 — Identification and Authentication Failures"),
    "CWE-502": ("Deserialization of Untrusted Data", "OWASP A08:2021 — Software and Data Integrity Failures"),
    "CWE-862": ("Missing Authorization", "OWASP A01:2021 — Broken Access Control"),
    "CWE-863": ("Incorrect Authorization", "OWASP A01:2021 — Broken Access Control"),
    "CWE-307": ("Improper Restriction of Excessive Authentication Attempts", "OWASP A07:2021 — Identification and Authentication Failures"),
    "CWE-918": ("Server-Side Request Forgery (SSRF)", "OWASP A10:2021 — Server-Side Request Forgery"),
    "CWE-434": ("Unrestricted Upload of File with Dangerous Type", "OWASP A03:2021 — Injection"),
    "CWE-200": ("Exposure of Sensitive Information to an Unauthorized Actor", "OWASP A01:2021 — Broken Access Control"),
    "CWE-400": ("Uncontrolled Resource Consumption", "OWASP A04:2021 — Insecure Design"),
    "CWE-20":  ("Improper Input Validation", "OWASP A03:2021 — Injection"),
    "CWE-476": ("NULL Pointer Dereference", "OWASP A04:2021 — Insecure Design"),
}
VALID_CWE = set(CWE)
SEVERITIES = {"critical", "high", "medium", "low"}
CATEGORIES = {"sql_injection", "command_injection", "code_injection", "xss",
              "path_traversal", "hardcoded_secret", "unsafe_deserialization",
              "missing_authorization", "ssrf", "input_validation",
              "logic_error", "error_handling", "resource_leak", "concurrency",
              "null_handling", "maintainability", "duplication", "dead_code",
              "secret_exposure", "dependency_vulnerability", "other"}

class FindingDraft(BaseModel):
    """One agent-produced finding. Validated by Pydantic before it can
    enter the filter stage; free-text findings are rejected, not reformatted."""
    source: str  # security | logic | style | secret-scanner | dependency-scanner
    category: str
    severity: str
    title: str
    description: str
    file_path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    evidence: str
    cwe_id: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    patch: str | None = None
    model_version: str = "deterministic-rules-v1"
    prompt_version: str = "prompts-v1"
    context_provenance: dict = Field(default_factory=dict)

    @field_validator("severity")
    @classmethod
    def _sev(cls, v):
        if v not in SEVERITIES:
            raise ValueError(f"invalid severity {v}")
        return v

    @field_validator("category")
    @classmethod
    def _cat(cls, v):
        if v not in CATEGORIES:
            raise ValueError(f"invalid category {v}")
        return v

    @field_validator("cwe_id")
    @classmethod
    def _cwe(cls, v):
        if v is not None and v not in VALID_CWE:
            raise ValueError(f"invalid CWE {v}")
        return v

    @field_validator("end_line")
    @classmethod
    def _lines(cls, v, info):
        if "start_line" in info.data and v < info.data["start_line"]:
            raise ValueError("end_line < start_line")
        return v

    def with_cwe(self):
        if self.cwe_id:
            title, owasp = CWE[self.cwe_id]
            return title, owasp
        return None, None
