"""Dependency scanning via the OSV API (https://api.osv.dev).

Real API call with a 10s timeout. If OSV is unreachable, the result is
honestly marked 'unavailable' — never guessed, never fabricated.
"""
from __future__ import annotations
import re
import httpx

ECOSYSTEMS = {"requirements.txt": "PyPI", "pyproject.toml": "PyPI",
              "package.json": "npm", "package-lock.json": "npm"}

def parse_added_dependencies(diff_text: str) -> list[dict]:
    """Extract added/changed dependencies from a diff."""
    deps = []
    cur_file = ""
    for line in (diff_text or "").splitlines():
        if line.startswith("+++ b/"):
            cur_file = line[6:]
        if not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:].strip()
        if cur_file.endswith("requirements.txt"):
            m = re.match(r"([A-Za-z0-9_.\-]+)\s*==\s*([^\s;]+)", body)
            if m:
                deps.append({"ecosystem": "PyPI", "name": m.group(1), "version": m.group(2)})
        elif cur_file.endswith("package.json"):
            m = re.match(r'"([@\w\-/\.]+)"\s*:\s*"[\^~]?([0-9][^"]*)"', body)
            if m:
                deps.append({"ecosystem": "npm", "name": m.group(1), "version": m.group(2)})
    return deps

def query_osv(deps: list[dict]) -> dict:
    """Returns {"status": "ok"|"unavailable", "vulnerabilities": [...]}."""
    if not deps:
        return {"status": "ok", "vulnerabilities": []}
    payload = {"queries": [{"package": {"name": d["name"], "ecosystem": d["ecosystem"]},
                            "version": d["version"]} for d in deps]}
    try:
        r = httpx.post("https://api.osv.dev/v1/querybatch", json=payload, timeout=10)
        r.raise_for_status()
        vulns = []
        for dep, res in zip(deps, r.json().get("results", [])):
            for v in res.get("vulns", []):
                sev = "high"
                for s in v.get("severity", []):
                    if s.get("type") == "CVSS_V3":
                        score = float(s.get("score", "0").split("/")[0]) if "/" in s.get("score", "") else 0
                        sev = "critical" if score >= 9 else "high" if score >= 7 else "medium"
                vulns.append({"package": dep["name"], "version": dep["version"],
                              "ecosystem": dep["ecosystem"], "advisory_id": v.get("id"),
                              "summary": v.get("summary", ""), "severity": sev,
                              "references": [x.get("url") for x in v.get("references", [])][:3]})
        return {"status": "ok", "vulnerabilities": vulns}
    except Exception as e:
        return {"status": "unavailable", "error": str(e), "vulnerabilities": []}
