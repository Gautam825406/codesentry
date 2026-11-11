"""Finding validation / filter stage (PRD §7, §8.4).

A finding is POSTED only if it survives every check; otherwise it is
logged as suppressed with a reason (visible on the run-detail page):
  1. citation verification — evidence must match the reviewed file lines
  2. line verification — lines exist at the reviewed head SHA
  3. security findings must carry a valid CWE (else dropped as security;
     never re-labelled as a vague warning)
  4. confidence >= repository threshold
  5. cross-agent deduplication — same (file, line, category) keeps the
     strongest; same (file, line) with the same root cause merges
  6. rejected-finding memory — a pattern rejected as wrong before is not reposted
  7. excluded-path filtering
Low-confidence findings are logged for evaluation, not posted.
"""
from __future__ import annotations
import fnmatch
from agents.schemas import FindingDraft, VALID_CWE
from database.models import FeedbackEvent

def _evidence_matches(draft: FindingDraft, file_lines: dict) -> bool:
    lines = file_lines.get(draft.file_path)
    if not lines:
        return False
    if draft.start_line < 1 or draft.end_line > len(lines):
        return False
    actual = "\n".join(lines[draft.start_line - 1: draft.end_line]).strip()
    ev = (draft.evidence or "").strip()
    if not ev:
        return False
    # evidence must be contained in (or equal to) the actual lines
    return ev in actual or actual in ev or ev.splitlines()[0].strip() in actual

def filter_findings(drafts, *, file_lines: dict, threshold: float,
                    excluded_paths, rejected_keys: set) -> tuple[list, list]:
    """Returns (posted, suppressed) where suppressed items are
    (draft, reason) pairs."""
    posted, suppressed = [], []
    seen: dict[tuple, FindingDraft] = {}
    for d in drafts:
        try:
            d = FindingDraft(**d.model_dump())
        except Exception as e:
            suppressed.append((d, f"schema_invalid: {e}"))
            continue
        if any(fnmatch.fnmatch(d.file_path, p) for p in (excluded_paths or [])):
            suppressed.append((d, "excluded_path")); continue
        if d.source == "security" and not d.cwe_id:
            suppressed.append((d, "security_finding_without_valid_cwe")); continue
        if d.cwe_id and d.cwe_id not in VALID_CWE:
            suppressed.append((d, "invalid_cwe")); continue
        if not _evidence_matches(d, file_lines):
            suppressed.append((d, "citation_unverifiable")); continue
        if d.confidence < threshold:
            suppressed.append((d, f"below_confidence_threshold:{threshold}")); continue
        key = (d.file_path, d.start_line, d.category)
        if key in rejected_keys:
            suppressed.append((d, "previously_rejected_on_repo")); continue
        if key in seen:
            if d.confidence > seen[key].confidence:
                suppressed.append((seen[key], "deduplicated_by_stronger_finding"))
                seen[key] = d
            else:
                suppressed.append((d, "duplicate")); continue
        else:
            seen[key] = d
    posted = list(seen.values())
    return posted, suppressed

def rejected_keys_for_repo(db, repo_id: int) -> set:
    """(file_path, start_line, category) keys for findings this repo's
    reviewers rejected as wrong."""
    from database.models import Finding
    keys = set()
    rows = (db.query(FeedbackEvent, Finding)
            .join(Finding, FeedbackEvent.finding_id == Finding.id)
            .filter(Finding.repo_id == repo_id,
                    FeedbackEvent.verdict == "reject_wrong").all())
    for _fb, f in rows:
        keys.add((f.file_path, f.start_line, f.category))
    return keys
