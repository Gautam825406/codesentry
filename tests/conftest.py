import os, sys, tempfile
import pytest

# Isolated temp DB for the whole test session — a unique path per run,
# set BEFORE importing the app. (Deleting the file after import breaks
# SQLite's pooled connection to the old inode.)
_TMPDB = os.path.join(tempfile.mkdtemp(prefix="codesentry-test-"), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMPDB}"
os.environ["GITHUB_WEBHOOK_SECRET"] = "test-webhook-secret"
os.environ["CODESENTRY_JWT_SECRET"] = "test-secret"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from database.session import init_db  # noqa: E402
from apps.api.main import app  # noqa: E402

@pytest.fixture(scope="session", autouse=True)
def _fresh_db():
    init_db()
    yield
    if os.path.exists(_TMPDB):
        os.remove(_TMPDB)

@pytest.fixture()
def client():
    return TestClient(app)

@pytest.fixture()
def auth_client(client):
    import uuid
    email = f"tester-{uuid.uuid4().hex[:8]}@x.dev"
    r = client.post("/api/auth/register", json={"email": email,
                                                "password": "password123", "name": "Tester"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client

@pytest.fixture()
def second_client(client):
    import uuid
    email = f"other-{uuid.uuid4().hex[:8]}@x.dev"
    r = client.post("/api/auth/register", json={"email": email,
                                                "password": "password123", "name": "Other"})
    assert r.status_code == 200
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return c
