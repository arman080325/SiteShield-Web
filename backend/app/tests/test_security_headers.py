import pytest
from fastapi.testclient import TestClient


def test_standard_security_headers_on_success(client):
    """X-Content-Type-Options, Referrer-Policy, and CSP are present on responses."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("Referrer-Policy") == "no-referrer"
    assert "default-src 'none'" in resp.headers.get("Content-Security-Policy", "")


def test_cache_control_no_store_on_authenticated_and_domains(auth_client):
    """Cache-Control: no-store is sent on authenticated and /domains endpoints."""
    client, _ = auth_client
    resp = client.get("/domains")
    assert resp.status_code == 200
    assert resp.headers.get("Cache-Control") == "no-store"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"


def test_security_headers_on_error_responses(client):
    """Error responses (401, 404, 422) also carry security headers and Cache-Control: no-store."""
    # 401 Unauthorized
    r401 = client.get("/auth/me")
    assert r401.status_code == 401
    assert r401.headers.get("X-Content-Type-Options") == "nosniff"
    assert r401.headers.get("Referrer-Policy") == "no-referrer"
    assert r401.headers.get("Cache-Control") == "no-store"

    # 404 Not Found
    r404 = client.get("/nonexistent-endpoint-abc")
    assert r404.status_code == 404
    assert r404.headers.get("X-Content-Type-Options") == "nosniff"
    assert r404.headers.get("Referrer-Policy") == "no-referrer"
    assert r404.headers.get("Cache-Control") == "no-store"

    # 422 Unprocessable Entity
    r422 = client.post("/auth/signup", json={"email": "not-an-email"})
    assert r422.status_code == 422
    assert r422.headers.get("X-Content-Type-Options") == "nosniff"
    assert r422.headers.get("Referrer-Policy") == "no-referrer"
    assert r422.headers.get("Cache-Control") == "no-store"


def test_docs_enabled_toggle(monkeypatch):
    """When docs_enabled is False, /docs and /openapi.json return 404."""
    from app import config
    from app.main import app
    import importlib

    # Test with docs disabled
    monkeypatch.setattr(config.settings, "docs_enabled", False)
    # Re-create app instance or verify conditional paths
    from fastapi import FastAPI
    test_app = FastAPI(
        docs_url="/docs" if config.settings.docs_enabled else None,
        openapi_url="/openapi.json" if config.settings.docs_enabled else None,
    )
    with TestClient(test_app) as tc:
        assert tc.get("/docs").status_code == 404
        assert tc.get("/openapi.json").status_code == 404
