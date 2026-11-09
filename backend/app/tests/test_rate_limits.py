import pytest
from app.core.ratelimit import limiter


@pytest.fixture(autouse=True)
def reset_limiter_storage():
    """Reset limiter in-memory storage before each test."""
    try:
        limiter._storage.storage.clear()
    except Exception:
        pass
    yield
    try:
        limiter._storage.storage.clear()
    except Exception:
        pass


def test_login_rate_limit(client):
    """POST /auth/login is limited to 5/min per IP."""
    # 5 allowed attempts
    for i in range(5):
        resp = client.post(
            "/auth/login",
            data={"username": f"user{i}@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code in {400, 401}

    # 6th attempt hits 429
    r6 = client.post(
        "/auth/login",
        data={"username": "user6@example.com", "password": "wrongpassword"},
    )
    assert r6.status_code == 429
    assert "Retry-After" in r6.headers
    assert "Rate limit exceeded" in r6.json()["detail"]


def test_signup_rate_limit(client):
    """POST /auth/signup is limited to 5/hour per IP."""
    for i in range(5):
        resp = client.post(
            "/auth/signup",
            json={"email": f"signup{i}@example.com", "password": "password123"},
        )
        assert resp.status_code == 201

    # 6th attempt hits 429
    r6 = client.post(
        "/auth/signup",
        json={"email": "signup6@example.com", "password": "password123"},
    )
    assert r6.status_code == 429
    assert "Retry-After" in r6.headers
    assert "Rate limit exceeded" in r6.json()["detail"]


def test_scan_rate_limit_per_user(auth_client, monkeypatch):
    """POST /domains/{domain_id}/scan is limited to 30/hour per user."""
    client, _ = auth_client
    class FakeTask:
        id = "fake-task"
    monkeypatch.setattr("app.scanner.tasks.run_scan_job.delay", lambda *a, **k: FakeTask())

    # Add domain
    d_resp = client.post("/domains", json={"url": "https://rate-limit-user.example.com"})
    assert d_resp.status_code == 201
    domain_id = d_resp.json()["id"]

    # 30 allowed scan requests (some may return 200 due to dedupe, but hit the endpoint)
    for _ in range(30):
        resp = client.post(f"/domains/{domain_id}/scan")
        assert resp.status_code in {200, 202}

    # 31st request hits 429
    r31 = client.post(f"/domains/{domain_id}/scan")
    assert r31.status_code == 429
    assert "Retry-After" in r31.headers
