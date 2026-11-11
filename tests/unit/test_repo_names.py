"""Unit tests: repository name normalization (duplicate-repo fix)."""
import pytest

from integrations.repo_names import normalize_repo_full_name


@pytest.mark.parametrize("raw,expected", [
    ("owner/repo", "owner/repo"),
    ("Owner/Repo", "owner/repo"),                       # case-insensitive
    ("  owner/repo  ", "owner/repo"),                   # whitespace
    ("https://github.com/owner/repo", "owner/repo"),    # full URL
    ("https://github.com/owner/repo/", "owner/repo"),   # trailing slash
    ("https://github.com/owner/repo.git", "owner/repo"),
    ("https://github.com/owner/repo.git/", "owner/repo"),
    ("http://github.com/owner/repo", "owner/repo"),
    ("github.com/owner/repo", "owner/repo"),
    ("www.github.com/owner/repo", "owner/repo"),
    ("HTTPS://GITHUB.COM/Owner/Repo.GIT", "owner/repo"),
    ("git@github.com:owner/repo.git", "owner/repo"),    # SSH form
    ("owner/repo-name.js", "owner/repo-name.js"),
    ("my_org/my.repo", "my_org/my.repo"),
])
def test_normalize_accepts_spellings(raw, expected):
    assert normalize_repo_full_name(raw) == expected


@pytest.mark.parametrize("raw", [
    "", "   ", "owner", "owner/", "/repo", "owner/repo/extra",
    "https://gitlab.com/owner/repo", "git@gitlab.com:owner/repo.git",
    "owner/repo?x=1", "owner /repo", "ftp://github.com/owner/repo",
])
def test_normalize_rejects_invalid(raw):
    with pytest.raises(ValueError):
        normalize_repo_full_name(raw)


def test_live_duplicate_spellings_collapse():
    """The exact pair found live on 2026-11-11: both spellings of the same
    repo must normalize to one canonical name."""
    a = normalize_repo_full_name("https://github.com/Gautam825406/querypilot")
    b = normalize_repo_full_name("https://github.com/Gautam825406/querypilot.git")
    assert a == b == "gautam825406/querypilot"
