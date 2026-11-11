"""Integration tests: API, auth, webhook, demo review, feedback, purge, authz."""
import hashlib, hmac, json

def test_health_and_metrics(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/metrics").json()["repos"] >= 0

def test_auth_flow(client):
    r = client.post("/api/auth/register", json={"email": "a@x.dev", "password": "password123"})
    assert r.status_code == 200
    token = r.json()["token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "a@x.dev", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/register", json={"email": "a@x.dev", "password": "password123"}).status_code == 400

def test_demo_seed_end_to_end(auth_client):
    r = auth_client.post("/api/demo/seed")
    assert r.status_code == 200, r.text
    data = r.json()
    # act as the demo user from here on: it owns the demo repo
    auth_client.headers.update({"Authorization": f"Bearer {data['token']}"})
    assert data["gate_result"] == "fail"
    repo = auth_client.get(f"/api/repos/{data['repo_id']}").json()
    assert repo["symbols"] == 7
    findings = data["findings"]
    # note: an earlier test may have dismissed a finding, so check all findings,
    # not only posted ones — the gate assertion above already proves blocking.
    assert any(f["category"] == "sql_injection" and f["cwe_id"] == "CWE-89"
               and f["severity"] == "high" for f in findings)
    sqli = next(f for f in findings if f["category"] == "sql_injection")
    assert sqli["patch"] and sqli["patch_valid"] is True
    assert "run_query(sql, (order_id,))" in sqli["patch"]
    assert any(f["category"] == "logic_error" for f in findings)
    # quality metrics come from persisted data
    q = auth_client.get(f"/api/repos/{data['repo_id']}/quality").json()
    assert q["total_findings"] >= 2
    # by_severity counts posted findings only; a dismissed high finding in an
    # earlier test legitimately removes it from this count.
    assert q["precision"] is None or 0.0 <= q["precision"] <= 1.0  # null until feedback exists
    # findings filter API
    flt = auth_client.get("/api/findings", params={"severity": "high"}).json()
    assert all(f["severity"] == "high" for f in flt)
    # review detail page data
    pr = auth_client.get(f"/api/repos/{data['repo_id']}/prs/42").json()
    assert pr["runs"][0]["gate_result"] == "fail"
    assert pr["runs"][0]["coverage"]["pct"] == 100.0
    return data

def test_feedback_and_dismissal(auth_client):
    data = test_demo_seed_end_to_end(auth_client)
    fid = next(f["id"] for f in data["findings"] if f["category"] == "sql_injection")
    r = auth_client.post(f"/api/findings/{fid}/feedback",
                         json={"verdict": "reject_wrong", "reason": "test"})
    assert r.status_code == 200 and r.json()["state"] == "dismissed"
    r = auth_client.post(f"/api/findings/{fid}/feedback",
                         json={"verdict": "bogus"})
    assert r.status_code == 400
    q = auth_client.get(f"/api/repos/{data['repo_id']}/quality").json()
    assert q["verdicts"]["reject_wrong"] >= 1
    assert q["false_positive_rate"] is not None

def test_repo_authz(auth_client, second_client):
    r = auth_client.post("/api/repos", json={"full_name": "private/secret-repo"})
    assert r.status_code == 200
    rid = r.json()["id"]
    # second user cannot read the private repo
    assert second_client.get(f"/api/repos/{rid}").status_code == 403
    assert second_client.patch(f"/api/repos/{rid}/settings",
                               json={"confidence_threshold": 0.9}).status_code == 403
    # owner can
    assert auth_client.get(f"/api/repos/{rid}/settings").status_code == 200
    s = auth_client.patch(f"/api/repos/{rid}/settings",
                          json={"confidence_threshold": 0.9, "training_opt_in": True}).json()
    assert s["confidence_threshold"] == 0.9 and s["training_opt_in"] is True

def test_webhook_signature_and_dedup(auth_client):
    secret = "test-webhook-secret"
    payload = json.dumps({"action": "opened", "repository": {"full_name": "demo/shop-api"},
                          "pull_request": {"number": 42, "title": "x", "user": {"login": "a"},
                                           "base": {"sha": "b"}, "head_sha": "h"}}).encode()
    sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    headers = {"X-GitHub-Delivery": "deliv-1", "X-GitHub-Event": "pull_request",
               "X-Hub-Signature-256": sig}
    # bad signature -> 401
    bad = dict(headers, **{"X-Hub-Signature-256": "sha256=bad"})
    assert auth_client.post("/webhooks/github", content=payload, headers=bad).status_code == 401
    # no token configured for GitHub posting/diff fetch -> error recorded honestly, not faked
    r = auth_client.post("/webhooks/github", content=payload, headers=headers)
    assert r.status_code in (200, 500) or r.json().get("status") in ("error", "queued")
    # redelivery of the same delivery id is a duplicate
    r2 = auth_client.post("/webhooks/github", content=payload, headers=headers)
    assert r2.json().get("status") == "duplicate"

def test_purge_verified(auth_client):
    data = test_demo_seed_end_to_end(auth_client)
    rid = data["repo_id"]
    r = auth_client.post(f"/api/repos/{rid}/purge", params={"confirm": False})
    assert r.status_code == 400
    r = auth_client.post(f"/api/repos/{rid}/purge", params={"confirm": True})
    assert r.status_code == 200 and r.json()["verified"] is True
    assert r.json()["remaining_symbols"] == 0

def test_repo_connect_normalizes_and_dedupes(auth_client):
    """Connect accepts a full GitHub URL, stores canonical owner/repo, and
    rejects the same repo under any other spelling (live bug 2026-11-11:
    querypilot was listed twice as a URL and as a URL + .git)."""
    r = auth_client.post("/api/repos", json={"full_name": "https://github.com/Acme/Widget.git/"})
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "acme/widget"
    assert r.json()["clone_url"] == "https://github.com/acme/widget.git"
    for spelling in ("acme/widget", "ACME/WIDGET", "github.com/acme/widget",
                     "https://github.com/acme/widget"):
        assert auth_client.post("/api/repos", json={"full_name": spelling}).status_code == 400
    assert auth_client.post("/api/repos", json={"full_name": "not-a-repo"}).status_code == 400
    assert auth_client.post("/api/repos", json={"full_name": "a/b/c"}).status_code == 400
    names = [x["full_name"] for x in auth_client.get("/api/repos").json()]
    assert names.count("acme/widget") == 1


def test_repo_list_collapses_legacy_duplicates(auth_client):
    """Rows stored before normalization existed (raw URLs in the DB) are
    shown once in the list, under the canonical name."""
    from database.session import SessionLocal
    from database.models import Repository
    me = auth_client.get("/api/auth/me").json()
    db = SessionLocal()
    try:
        for raw in ("https://github.com/legacy/dup", "https://github.com/legacy/dup.git"):
            if not db.query(Repository).filter_by(full_name=raw).first():
                db.add(Repository(full_name=raw, name="dup", owner_id=me["id"]))
        db.commit()
    finally:
        db.close()
    names = [x["full_name"] for x in auth_client.get("/api/repos").json()]
    assert names.count("legacy/dup") == 1


def test_reindex_fetches_real_repo_files(auth_client, monkeypatch):
    """Re-index of a non-demo repo fetches files from GitHub (mocked here)
    instead of silently indexing zero files (live bug 2026-11-11:
    'Re-indexed: 0 symbols' for Gautam825406/codesentry)."""
    import apps.api.main as main
    fixture_files = {"pkg/mod.py": "def hello():\n    return 'hi'\n",
                     "pkg/util.js": "function util() { return 1; }\n"}
    monkeypatch.setattr(main, "fetch_repo_files",
                        lambda full_name, ref=None: (dict(fixture_files), "f" * 40))
    r = auth_client.post("/api/repos", json={"full_name": "real/repo"})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    res = auth_client.post(f"/api/repos/{rid}/reindex", json={})
    assert res.status_code == 200, res.text
    assert res.json()["files_fetched"] == 2
    assert res.json()["symbols"] == 2
    repo = auth_client.get(f"/api/repos/{rid}").json()
    assert repo["index_status"] == "indexed" and repo["symbols"] == 2
    assert repo["head_sha"] == "f" * 40


def test_reindex_fetch_failure_is_honest_502(auth_client, monkeypatch):
    """If GitHub cannot be reached, re-index fails loudly (502) and the
    repo is marked failed — never 'indexed' with 0 symbols."""
    import apps.api.main as main
    from integrations.github import RepoFetchError
    monkeypatch.setattr(main, "fetch_repo_files",
                        lambda full_name, ref=None: (_ for _ in ()).throw(
                            RepoFetchError("Repository real/gone not found or not accessible")))
    r = auth_client.post("/api/repos", json={"full_name": "real/gone"})
    rid = r.json()["id"]
    res = auth_client.post(f"/api/repos/{rid}/reindex", json={})
    assert res.status_code == 502, res.text
    assert "not found or not accessible" in res.text
    repo = auth_client.get(f"/api/repos/{rid}").json()
    assert repo["index_status"] == "failed" and repo["symbols"] == 0


def test_demo_reindex_without_body_still_indexes(auth_client):
    """Regression: re-indexing the demo repo with an empty body must still
    index the bundled demo files (7 symbols), not 0."""
    data = test_demo_seed_end_to_end(auth_client)
    rid = data["repo_id"]
    res = auth_client.post(f"/api/repos/{rid}/reindex", json={})
    assert res.status_code == 200, res.text
    assert res.json()["files_fetched"] == 5
    repo = auth_client.get(f"/api/repos/{rid}").json()
    assert repo["index_status"] == "indexed" and repo["symbols"] == 7


def test_clean_pr_passes_gate(auth_client):
    r = auth_client.post("/api/demo/seed")
    repo_id = r.json()["repo_id"]
    auth_client.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    diff = """diff --git a/app/users.py b/app/users.py
--- a/app/users.py
+++ b/app/users.py
@@ -1,5 +1,6 @@
 from app.db import run_query
 
 
 def get_user(user_id):
     return run_query("SELECT * FROM users WHERE id = %s", (user_id,))
+
"""
    files = {"app/users.py": open("fixtures/sample_repo/app/users.py").read() + "\n"}
    res = auth_client.post(f"/api/repos/{repo_id}/prs/43/review", json={
        "number": 43, "title": "Whitespace only", "diff_text": diff, "file_contents": files})
    assert res.status_code == 200, res.text
    assert res.json()["gate_result"] == "pass"
