"""Repository name normalization.

Why this exists: the Connect box accepted whatever the user typed, so the
same repository could be recorded under several spellings — e.g. the live
site ended up with both ``https://github.com/Gautam825406/querypilot`` and
``https://github.com/Gautam825406/querypilot.git`` for one repo. The
``full_name`` column is unique, but those are different strings, so the
uniqueness guard never fired.

Canonical form is lowercase ``owner/repo`` (GitHub treats repository names
case-insensitively, and the REST API accepts lowercase). Every write path
(connect, webhook lookup) normalizes first; the list endpoint additionally
collapses any legacy rows that were stored before normalization existed.
"""
from __future__ import annotations
import re

_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$")
_HOSTS = ("https://github.com/", "http://github.com/",
          "https://www.github.com/", "http://www.github.com/",
          "github.com/", "www.github.com/")


def normalize_repo_full_name(raw: str) -> str:
    """Return the canonical ``owner/repo`` for any user-supplied spelling.

    Accepts ``owner/repo``, a full ``https://github.com/owner/repo`` URL
    (with or without a trailing slash or ``.git`` suffix), and the SSH form
    ``git@github.com:owner/repo.git``. Raises ``ValueError`` for anything
    that is not a single ``owner/repo`` after stripping.
    """
    s = (raw or "").strip()
    if not s:
        raise ValueError("Repository name is empty")
    # SSH form: git@github.com:owner/repo.git
    if s.startswith("git@"):
        s = s[4:]
        if ":" in s:
            host, s = s.split(":", 1)
            if host.lower() not in ("github.com", "www.github.com"):
                raise ValueError(f"Not a github.com repository: {raw!r}")
        else:
            raise ValueError(f"Not a github.com repository: {raw!r}")
    # Scheme form: https://github.com/owner/repo(.git)
    if "://" in s:
        scheme, rest = s.split("://", 1)
        if scheme.lower() not in ("http", "https", "git", "ssh"):
            raise ValueError(f"Unsupported URL scheme in repository name: {raw!r}")
        s = rest
    lowered = s.lower()
    for host in _HOSTS:
        if lowered.startswith(host):
            s = s[len(host):]
            break
    s = s.strip().strip("/")
    if s.lower().endswith(".git"):
        s = s[:-4]
    s = s.strip().strip("/")
    if not _NAME_RE.match(s):
        raise ValueError(
            f"Repository name must be owner/repo, got {raw!r} "
            "(a full github.com URL is also accepted)")
    return s.lower()
