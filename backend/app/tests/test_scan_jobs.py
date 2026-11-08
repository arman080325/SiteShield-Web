import json
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from app.models import Domain, Scan, ScanJob, ScanOptOut, User
from app.scanner.tasks import run_scan_job


def test_start_scan_and_get_job(auth_client, monkeypatch):
    client, _ = auth_client
    class FakeTask:
        id = "celery-fake-task-id"
    monkeypatch.setattr("app.scanner.tasks.run_scan_job.delay", lambda *a, **k: FakeTask())

    # Add domain
    d_resp = client.post("/domains", json={"url": "https://start-job.example.com"})
    assert d_resp.status_code == 201
    domain_id = d_resp.json()["id"]

    # Start scan
    resp = client.post(f"/domains/{domain_id}/scan")
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    job_id = data["job_id"]

    # Check job status
    status_resp = client.get(f"/domains/scan-jobs/{job_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["job_id"] == job_id
    assert status_data["status"] == "queued"


def test_scan_job_idor_isolation(auth_client, client, monkeypatch):
    """User B must get 404 when querying User A's job_id."""
    client_a, _ = auth_client
    class FakeTask:
        id = "celery-fake-task-id"
    monkeypatch.setattr("app.scanner.tasks.run_scan_job.delay", lambda *a, **k: FakeTask())

    d_resp = client_a.post("/domains", json={"url": "https://idor-job.example.com"})
    assert d_resp.status_code == 201
    domain_id = d_resp.json()["id"]

    s_resp = client_a.post(f"/domains/{domain_id}/scan")
    assert s_resp.status_code == 202
    job_id = s_resp.json()["job_id"]

    # User B signs up and logs in
    client.post("/auth/signup", json={"email": "user_b@example.com", "password": "password123"})
    login = client.post("/auth/login", data={"username": "user_b@example.com", "password": "password123"})
    client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})

    # User B tries to fetch User A's scan job
    resp = client.get(f"/domains/scan-jobs/{job_id}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Scan job not found"


def test_user_deduplication_returns_same_job(auth_client, monkeypatch):
    client, _ = auth_client
    class FakeTask:
        id = "celery-fake-task-id"
    monkeypatch.setattr("app.scanner.tasks.run_scan_job.delay", lambda *a, **k: FakeTask())

    d_resp = client.post("/domains", json={"url": "https://dedupe.example.com"})
    assert d_resp.status_code == 201
    domain_id = d_resp.json()["id"]

    # First request enqueues
    r1 = client.post(f"/domains/{domain_id}/scan")
    assert r1.status_code == 202
    job_id_1 = r1.json()["job_id"]

    # Second request while queued returns 200 and same job_id
    r2 = client.post(f"/domains/{domain_id}/scan")
    assert r2.status_code == 200
    assert r2.json()["job_id"] == job_id_1
    assert "Scan already in progress" in r2.json()["message"]


def test_opt_out_domain_rejected(auth_client, monkeypatch):
    client, _ = auth_client
    from app.tests.conftest import TestingSessionLocal

    # Seed opt-out table
    db = TestingSessionLocal()
    opt = ScanOptOut(hostname="optout.example.com", reason="Requested exclusion")
    db.add(opt)
    db.commit()
    db.close()

    d_resp = client.post("/domains", json={"url": "https://optout.example.com"})
    assert d_resp.status_code == 201
    domain_id = d_resp.json()["id"]

    r = client.post(f"/domains/{domain_id}/scan")
    assert r.status_code == 400
    assert "opted out" in r.json()["detail"]


def test_recent_scan_cache_hit(auth_client, monkeypatch):
    client, _ = auth_client
    from app.tests.conftest import TestingSessionLocal

    d_resp = client.post("/domains", json={"url": "https://cached.example.com"})
    assert d_resp.status_code == 201
    domain_id = d_resp.json()["id"]

    # Seed a scan finished 1 minute ago
    db = TestingSessionLocal()
    scan = Scan(
        domain_id=domain_id,
        grade="A",
        score=95,
        results_json="{}",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db.add(scan)
    db.commit()
    saved_scan_id = scan.id
    db.close()

    r = client.post(f"/domains/{domain_id}/scan")
    assert r.status_code == 200
    assert r.json()["cached"] is True
    assert r.json()["scan_id"] == saved_scan_id


def test_cross_tenant_cooldown(auth_client, monkeypatch):
    client, _ = auth_client

    class FakeRedis:
        def ttl(self, key):
            if "cooldown:cooldown.example.com" in key:
                return 240
            return 0
        def set(self, key, val, ex=None):
            pass

    monkeypatch.setattr("app.scanner.router.get_redis_client", lambda: FakeRedis())

    d_resp = client.post("/domains", json={"url": "https://cooldown.example.com"})
    assert d_resp.status_code == 201
    domain_id = d_resp.json()["id"]

    r = client.post(f"/domains/{domain_id}/scan")
    assert r.status_code == 429
    assert r.headers.get("Retry-After") == "240"
    assert "Please retry in 240 seconds" in r.json()["detail"]


def test_worker_run_scan_job_unsafe_target_saves_no_scan(monkeypatch):
    from app.tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    user = User(email="worker_ssrf@example.com", hashed_password="pw")
    db.add(user)
    db.commit()
    domain = Domain(url="https://127.0.0.1", owner_id=user.id)
    db.add(domain)
    db.commit()
    domain_id = domain.id

    job = ScanJob(
        id=uuid.uuid4(),
        domain_id=domain_id,
        requested_by_user_id=user.id,
        source="manual",
        target_hostname="127.0.0.1",
        status="queued",
    )
    db.add(job)
    db.commit()
    job_id = str(job.id)
    db.close()

    monkeypatch.setattr("app.scanner.tasks.SessionLocal", TestingSessionLocal)

    result = run_scan_job(job_id)
    assert result["status"] == "failed"

    # Verify job state in DB and assert NO Scan row created
    db = TestingSessionLocal()
    updated_job = db.query(ScanJob).filter(ScanJob.id == uuid.UUID(job_id)).first()
    assert updated_job.status == "failed"
    assert updated_job.scan_id is None
    scan_count = db.query(Scan).filter(Scan.domain_id == domain_id).count()
    assert scan_count == 0
    db.close()
