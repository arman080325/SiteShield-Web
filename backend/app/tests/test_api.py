"""Integration tests for the API — auth flow, domain CRUD, and the
multi-tenant isolation (IDOR) protection."""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_signup_and_login(client):
    r = client.post("/auth/signup",
                    json={"email": "a@example.com", "password": "pw12345"})
    assert r.status_code == 201

    r = client.post("/auth/login",
                    data={"username": "a@example.com", "password": "pw12345"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_duplicate_signup_rejected(client):
    client.post("/auth/signup",
                json={"email": "dup@example.com", "password": "pw12345"})
    r = client.post("/auth/signup",
                    json={"email": "dup@example.com", "password": "pw12345"})
    assert r.status_code == 400


def test_protected_route_requires_auth(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_add_and_list_domain(auth_client):
    client, _ = auth_client
    r = client.post("/domains", json={"url": "https://example.com"})
    assert r.status_code == 201
    assert r.json()["url"] == "https://example.com"

    r = client.get("/domains")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_idor_protection(auth_client, client):
    """The security test: user B must NOT see or access user A's domain."""
    # User A (from auth_client) adds a domain
    client_a, _ = auth_client
    created = client_a.post("/domains", json={"url": "https://secret.com"})
    domain_id = created.json()["id"]

    # User B signs up fresh on a separate client
    from fastapi.testclient import TestClient
    from app.main import app
    client_b = TestClient(app)
    client_b.post("/auth/signup",
                  json={"email": "b@example.com", "password": "pw12345"})
    login = client_b.post("/auth/login",
                          data={"username": "b@example.com", "password": "pw12345"})
    client_b.headers.update(
        {"Authorization": f"Bearer {login.json()['access_token']}"})

    # User B's list is empty, and B cannot fetch A's domain by id
    assert client_b.get("/domains").json() == []
    assert client_b.get(f"/domains/{domain_id}").status_code == 404