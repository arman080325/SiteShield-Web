import socket
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db

# A dedicated in-memory SQLite DB for tests — never touches siteshield.db.
# StaticPool + a single shared connection keeps the in-memory DB alive
# across the whole test session (in-memory DBs vanish when their connection closes).
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def fresh_db():
    """Create all tables before each test, drop them after — total isolation."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    # Clean any scan cooldown keys in test redis
    from app.core.redis_client import get_redis_client
    r = get_redis_client()
    if r:
        try:
            keys = r.keys("scan:cooldown:*")
            if keys:
                r.delete(*keys)
        except Exception:
            pass


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Reset SlowAPI in-memory storage before and after each test."""
    from app.core.ratelimit import limiter
    try:
        limiter._storage.storage.clear()
    except Exception:
        pass
    yield
    try:
        limiter._storage.storage.clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def fake_getaddrinfo_default(monkeypatch):
    """
    Fake socket.getaddrinfo by default so all tests stay offline.
    Returns 93.184.216.34 (public IP) for normal test hosts.
    Allows loopback addresses through for local database/test connections.
    SSRF tests can override per test case using monkeypatch.
    """
    orig_getaddrinfo = socket.getaddrinfo

    def _fake_getaddrinfo(host, port, *args, **kwargs):
        if host in {"127.0.0.1", "::1"} or (isinstance(host, str) and host.startswith("localhost")):
            return orig_getaddrinfo(host, port, *args, **kwargs)
        try:
            port_int = int(port) if port is not None else 0
        except (ValueError, TypeError):
            port_int = 0
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port_int))
        ]

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    """A TestClient wired to the test DB via dependency override."""
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client(client):
    """A TestClient already signed up + logged in, with the JWT attached.

    Returns (client, email) so tests can create a second user for isolation checks.
    """
    email = "tester@example.com"
    password = "testpass123"
    client.post("/auth/signup", json={"email": email, "password": password})
    resp = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client, email
