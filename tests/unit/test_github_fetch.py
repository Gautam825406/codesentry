"""Unit tests: fetching a repository from GitHub (tarball API).

No network is used: every test drives fetch_repo_files through an
httpx.MockTransport with a tarball built in memory.
"""
import io, tarfile

import httpx
import pytest

from integrations.github import (RepoFetchError, fetch_repo_files,
                                 get_default_branch,
                                 get_installation_token_for_repo)

SHA = "a" * 40


def _tarball(files: dict[str, str]) -> bytes:
    """A codeload-style tarball: top dir 'owner-repo-<sha>/...'."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for path, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(f"owner-repo-{SHA}/{path}")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _transport(tarball: bytes, branch: str = "main", repo_status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/repos/o/r"):
            return httpx.Response(repo_status, json={"default_branch": branch})
        if url.endswith("/repos/o/r/commits/main"):
            return httpx.Response(200, json={"sha": SHA})
        if url.endswith("/repos/o/r/tarball/main"):
            # codeload redirect, as the real API does
            return httpx.Response(302, headers={
                "Location": f"https://codeload.github.com/o/r/tar.gz/{SHA}"})
        if url == f"https://codeload.github.com/o/r/tar.gz/{SHA}":
            return httpx.Response(200, content=tarball,
                                  headers={"Content-Type": "application/x-gzip"})
        return httpx.Response(404, json={"message": "not found"})
    return httpx.MockTransport(handler)


def test_fetch_public_repo_no_token():
    tar = _tarball({"app/main.py": "def f():\n    return 1\n",
                    "web/app.js": "function g() { return 2; }\n",
                    "README.md": "# hi\n",
                    "notes.txt": "not code\n"})
    files, head_sha = fetch_repo_files("o/r", transport=_transport(tar))
    assert files == {"app/main.py": "def f():\n    return 1\n",
                     "web/app.js": "function g() { return 2; }\n"}
    assert head_sha == SHA  # resolved via the commits endpoint


def test_fetch_uses_explicit_ref():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/repos/o/r/tarball/dev"):
            return httpx.Response(200, content=_tarball({"a.py": "x = 1\n"}),
                                  headers={"Content-Type": "application/x-gzip"})
        return httpx.Response(404, json={})
    files, _ = fetch_repo_files("o/r", ref="dev", transport=httpx.MockTransport(handler))
    assert files == {"a.py": "x = 1\n"}


def test_fetch_missing_repo_is_a_clear_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})
    with pytest.raises(RepoFetchError, match="not found or not accessible"):
        fetch_repo_files("o/nope", transport=httpx.MockTransport(handler))


def test_fetch_rate_limit_is_a_clear_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, headers={"X-RateLimit-Remaining": "0"},
                              json={"message": "rate limited"})
    with pytest.raises(RepoFetchError, match="rate limit"):
        fetch_repo_files("o/r", transport=httpx.MockTransport(handler))


def test_fetch_empty_repo_is_a_clear_error():
    tar = _tarball({"README.md": "# empty of code\n"})
    with pytest.raises(RepoFetchError, match="No indexable"):
        fetch_repo_files("o/r", transport=_transport(tar))


def test_get_default_branch():
    assert get_default_branch("o/r", transport=_transport(b"")) == "main"


def test_installation_token_exchange(monkeypatch):
    """App JWT -> installation id -> installation token, all mocked."""
    import integrations.github as gh
    monkeypatch.setattr(gh.settings, "GITHUB_APP_ID", "123")
    monkeypatch.setattr(gh.settings, "GITHUB_APP_PRIVATE_KEY", "fake-key")
    monkeypatch.setattr(gh, "_app_jwt", lambda: "fake-jwt")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        assert request.headers["Authorization"] == "Bearer fake-jwt"
        if url.endswith("/repos/o/r/installation"):
            return httpx.Response(200, json={"id": 99})
        if url.endswith("/app/installations/99/access_tokens"):
            return httpx.Response(201, json={"token": "ghs_installation_token"})
        return httpx.Response(404, json={})
    token = get_installation_token_for_repo("o/r", transport=httpx.MockTransport(handler))
    assert token == "ghs_installation_token"


def test_installation_token_not_installed(monkeypatch):
    import integrations.github as gh
    monkeypatch.setattr(gh.settings, "GITHUB_APP_ID", "123")
    monkeypatch.setattr(gh.settings, "GITHUB_APP_PRIVATE_KEY", "fake-key")
    monkeypatch.setattr(gh, "_app_jwt", lambda: "fake-jwt")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})
    with pytest.raises(RepoFetchError, match="not installed"):
        get_installation_token_for_repo("o/r", transport=httpx.MockTransport(handler))
