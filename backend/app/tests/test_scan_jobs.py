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


# -----------------------------------------------------------------------------
# Scheduled Scan Sweep Tests
# -----------------------------------------------------------------------------

def test_scheduled_scan_sweep_enqueues_monitored_domains(monkeypatch):
    """Monitored domains get a ScanJob with source='scheduled'; unmonitored are skipped."""
    from app.scanner.tasks import scheduled_scan_sweep
    from app.tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    user = User(email="sched_user1@example.com", hashed_password="pw")
    db.add(user)
    db.commit()

    d_monitored = Domain(url="https://monitored.example.com", owner_id=user.id, monitoring_enabled=True)
    d_unmonitored = Domain(url="https://unmonitored.example.com", owner_id=user.id, monitoring_enabled=False)
    db.add_all([d_monitored, d_unmonitored])
    db.commit()
    monitored_id = d_monitored.id
    unmonitored_id = d_unmonitored.id
    db.close()

    class FakeTask:
        id = "fake-scheduled-task-id"

    enqueued_jobs = []
    monkeypatch.setattr("app.scanner.tasks.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.scanner.tasks.run_scan_job.delay", lambda job_id: enqueued_jobs.append(job_id) or FakeTask())
    monkeypatch.setattr("app.scanner.tasks.get_redis_client", lambda: None)

    res = scheduled_scan_sweep()
    assert res["enqueued"] == 1
    assert len(enqueued_jobs) == 1

    db = TestingSessionLocal()
    job = db.query(ScanJob).filter(ScanJob.id == uuid.UUID(enqueued_jobs[0])).first()
    assert job is not None
    assert job.source == "scheduled"
    assert job.domain_id == monitored_id
    assert job.target_hostname == "monitored.example.com"

    # Verify unmonitored got no job
    unmonitored_job = db.query(ScanJob).filter(ScanJob.domain_id == unmonitored_id).first()
    assert unmonitored_job is None
    db.close()


def test_scheduled_scan_sweep_skips_opted_out_hostname(monkeypatch):
    """An opted-out hostname is skipped during the scheduled scan sweep."""
    from app.scanner.tasks import scheduled_scan_sweep
    from app.tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    user = User(email="sched_optout@example.com", hashed_password="pw")
    db.add(user)
    db.commit()

    d = Domain(url="https://optout-sweep.example.com", owner_id=user.id, monitoring_enabled=True)
    opt = ScanOptOut(hostname="optout-sweep.example.com", reason="Do not scan")
    db.add_all([d, opt])
    db.commit()
    domain_id = d.id
    db.close()

    enqueued_jobs = []
    monkeypatch.setattr("app.scanner.tasks.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.scanner.tasks.run_scan_job.delay", lambda job_id: enqueued_jobs.append(job_id))
    monkeypatch.setattr("app.scanner.tasks.get_redis_client", lambda: None)

    res = scheduled_scan_sweep()
    assert res["enqueued"] == 0
    assert len(enqueued_jobs) == 0

    db = TestingSessionLocal()
    job = db.query(ScanJob).filter(ScanJob.domain_id == domain_id).first()
    assert job is None
    db.close()


def test_scheduled_scan_sweep_skips_queued_or_running_job(monkeypatch):
    """A domain with a queued or running job is not duplicated."""
    from app.scanner.tasks import scheduled_scan_sweep
    from app.tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    user = User(email="sched_dedupe@example.com", hashed_password="pw")
    db.add(user)
    db.commit()

    d1 = Domain(url="https://already-queued.example.com", owner_id=user.id, monitoring_enabled=True)
    d2 = Domain(url="https://already-running.example.com", owner_id=user.id, monitoring_enabled=True)
    db.add_all([d1, d2])
    db.commit()

    j1 = ScanJob(id=uuid.uuid4(), domain_id=d1.id, status="queued", source="manual", target_hostname="already-queued.example.com")
    j2 = ScanJob(id=uuid.uuid4(), domain_id=d2.id, status="running", source="scheduled", target_hostname="already-running.example.com")
    db.add_all([j1, j2])
    db.commit()
    db.close()

    enqueued_jobs = []
    monkeypatch.setattr("app.scanner.tasks.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.scanner.tasks.run_scan_job.delay", lambda job_id: enqueued_jobs.append(job_id))
    monkeypatch.setattr("app.scanner.tasks.get_redis_client", lambda: None)

    res = scheduled_scan_sweep()
    assert res["enqueued"] == 0
    assert len(enqueued_jobs) == 0


def test_scheduled_scan_sweep_skips_cooldown_quietly(monkeypatch):
    """A hostname on cooldown is skipped quietly without error."""
    from app.scanner.tasks import scheduled_scan_sweep
    from app.tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    user = User(email="sched_cooldown@example.com", hashed_password="pw")
    db.add(user)
    db.commit()

    d = Domain(url="https://cooldown-sweep.example.com", owner_id=user.id, monitoring_enabled=True)
    db.add(d)
    db.commit()
    domain_id = d.id
    db.close()

    class FakeRedis:
        def exists(self, key):
            if "cooldown-sweep.example.com" in key:
                return 1
            return 0

        def set(self, key, val, ex=None):
            pass

    enqueued_jobs = []
    monkeypatch.setattr("app.scanner.tasks.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.scanner.tasks.run_scan_job.delay", lambda job_id: enqueued_jobs.append(job_id))
    monkeypatch.setattr("app.scanner.tasks.get_redis_client", lambda: FakeRedis())

    res = scheduled_scan_sweep()
    assert res["enqueued"] == 0
    assert len(enqueued_jobs) == 0

    db = TestingSessionLocal()
    job = db.query(ScanJob).filter(ScanJob.domain_id == domain_id).first()
    assert job is None
    db.close()


def test_scheduled_scan_sweep_unsafe_target_creates_no_scan(monkeypatch):
    """An unsafe target in a scheduled scan fails and creates no Scan row."""
    import socket
    from app.scanner.tasks import run_scan_job, scheduled_scan_sweep
    from app.tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    user = User(email="sched_unsafe@example.com", hashed_password="pw")
    db.add(user)
    db.commit()

    d = Domain(url="https://unsafe-sweep.example.com", owner_id=user.id, monitoring_enabled=True)
    db.add(d)
    db.commit()
    domain_id = d.id
    db.close()

    class FakeTask:
        id = "fake-scheduled-task-id"

    enqueued_jobs = []
    monkeypatch.setattr("app.scanner.tasks.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.scanner.tasks.run_scan_job.delay", lambda job_id: enqueued_jobs.append(job_id) or FakeTask())
    monkeypatch.setattr("app.scanner.tasks.get_redis_client", lambda: None)

    res = scheduled_scan_sweep()
    assert res["enqueued"] == 1
    job_id = enqueued_jobs[0]

    # Monkeypatch DNS resolution to private IP (127.0.0.1) during worker execution
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", int(port)))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    job_res = run_scan_job(job_id)
    assert job_res["status"] == "failed"

    db = TestingSessionLocal()
    job = db.query(ScanJob).filter(ScanJob.id == uuid.UUID(job_id)).first()
    assert job.status == "failed"
    assert job.scan_id is None
    assert (
        "not allowed" in job.error.lower()
        or "private" in job.error.lower()
        or "non-public" in job.error.lower()
        or "loopback" in job.error.lower()
        or "ssrf" in job.error.lower()
    )

    # Crucially assert no Scan row was created
    scans = db.query(Scan).filter(Scan.domain_id == domain_id).all()
    assert len(scans) == 0
    db.close()
