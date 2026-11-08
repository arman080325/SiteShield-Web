import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

from app.celery_app import celery_app
from app.core.redis_client import get_redis_client
from app.database import SessionLocal
from app.models import Domain, Scan, ScanJob, ScanOptOut
from app.scanner.cookies import scan_cookies
from app.scanner.dns_scan import scan_dns
from app.scanner.headers import scan_headers
from app.scanner.net.http_fetch import fetch_target
from app.scanner.net.ssrf_guard import UnsafeTargetError, resolve_public
from app.scanner.tls import scan_tls

# Category weights — must sum to 1.0
HEADERS_WEIGHT = 0.35
TLS_WEIGHT = 0.30
DNS_WEIGHT = 0.20
COOKIES_WEIGHT = 0.15


def _combined_grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    if score >= 20:
        return "E"
    return "F"


@celery_app.task(name="run_scan_job")
def run_scan_job(job_id_str: str) -> dict:
    """Execute a scan job by its UUID, updating progress and saving Scan row on success."""
    db = SessionLocal()
    try:
        try:
            job_uuid = uuid.UUID(job_id_str)
        except ValueError:
            return {"error": "Invalid job UUID"}

        job = db.query(ScanJob).filter(ScanJob.id == job_uuid).first()
        if not job:
            return {"error": "Job not found"}

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.progress = {
            "headers": "pending",
            "tls": "pending",
            "dns": "pending",
            "cookies": "pending",
        }
        db.commit()

        domain = db.query(Domain).filter(Domain.id == job.domain_id).first() if job.domain_id else None
        url = domain.url if domain else f"https://{job.target_hostname}"

        parsed = urlsplit(url)
        hostname = (parsed.hostname or job.target_hostname or "").strip().lower()
        port = parsed.port or (80 if parsed.scheme == "http" else 443)

        # Scan-time SSRF check (User Addition 4): call resolve_public once.
        # If UnsafeTargetError, mark job failed with clear error and save NO Scan row.
        try:
            resolve_public(hostname, port)
        except UnsafeTargetError as exc:
            job.status = "failed"
            job.error = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return {"job_id": job_id_str, "status": "failed", "error": str(exc)}
        except Exception as exc:
            job.status = "failed"
            job.error = f"Target resolution failed: {exc}"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return {"job_id": job_id_str, "status": "failed", "error": job.error}

        # Shared HTTP fetch
        try:
            fetch_res = fetch_target(url)
        except UnsafeTargetError as exc:
            job.status = "failed"
            job.error = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return {"job_id": job_id_str, "status": "failed", "error": str(exc)}
        except Exception as exc:
            fetch_res = None

        # Execute categories
        headers_result = scan_headers(url, fetch_result=fetch_res)
        job.progress = {"headers": "done", "tls": "pending", "dns": "pending", "cookies": "pending"}
        db.commit()

        cookies_result = scan_cookies(url, fetch_result=fetch_res)
        job.progress = {"headers": "done", "tls": "pending", "dns": "pending", "cookies": "done"}
        db.commit()

        tls_result = scan_tls(url)
        job.progress = {"headers": "done", "tls": "done", "dns": "pending", "cookies": "done"}
        db.commit()

        dns_result = scan_dns(url)
        job.progress = {"headers": "done", "tls": "done", "dns": "done", "cookies": "done"}
        db.commit()

        # Combine categories
        categories_meta = [
            ("headers", headers_result, HEADERS_WEIGHT),
            ("tls", tls_result, TLS_WEIGHT),
            ("dns", dns_result, DNS_WEIGHT),
            ("cookies", cookies_result, COOKIES_WEIGHT),
        ]

        weighted_sum = 0.0
        active_weight = 0.0
        for _name, result, weight in categories_meta:
            if result.get("unreachable"):
                continue
            weighted_sum += result.get("score", 0) * weight
            active_weight += weight

        if active_weight > 0:
            overall_score = round(weighted_sum / active_weight)
            overall_grade = _combined_grade(overall_score)
        else:
            overall_score = 0
            overall_grade = "N/A"

        full_results = {
            "headers": {
                "score": headers_result.get("score", 0),
                "checks": headers_result.get("checks", []),
                "error": headers_result.get("error"),
                "unreachable": headers_result.get("unreachable", False),
            },
            "tls": {
                "score": tls_result.get("score", 0),
                "checks": tls_result.get("checks", []),
                "protocol": tls_result.get("protocol"),
                "error": tls_result.get("error"),
                "unreachable": tls_result.get("unreachable", False),
            },
            "dns": {
                "score": dns_result.get("score", 0),
                "checks": dns_result.get("checks", []),
                "error": dns_result.get("error"),
                "unreachable": dns_result.get("unreachable", False),
            },
            "cookies": {
                "score": cookies_result.get("score", 0),
                "checks": cookies_result.get("checks", []),
                "error": cookies_result.get("error"),
                "unreachable": cookies_result.get("unreachable", False),
            },
        }

        # Persist Scan row
        scan = Scan(
            domain_id=job.domain_id,
            grade=overall_grade,
            score=overall_score,
            results_json=json.dumps(full_results),
        )
        db.add(scan)
        db.flush()

        job.scan_id = scan.id
        job.status = "succeeded"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()

        # Set Redis cooldown (300 seconds)
        r = get_redis_client()
        if r:
            try:
                r.set(f"scan:cooldown:{hostname}", "1", ex=300)
            except Exception:
                pass

        return {
            "job_id": job_id_str,
            "scan_id": scan.id,
            "status": "succeeded",
            "grade": overall_grade,
            "score": overall_score,
        }
    except Exception as exc:
        db.rollback()
        try:
            job = db.query(ScanJob).filter(ScanJob.id == uuid.UUID(job_id_str)).first()
            if job:
                job.status = "failed"
                job.error = str(exc)
                job.finished_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass
        return {"job_id": job_id_str, "status": "failed", "error": str(exc)}
    finally:
        db.close()


@celery_app.task(name="run_domain_scan")
def run_domain_scan(domain_id: int, url: str) -> dict:
    """Legacy helper: create a ScanJob and run it synchronously or return its task."""
    db = SessionLocal()
    try:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").strip().lower()
        job = ScanJob(
            id=uuid.uuid4(),
            domain_id=domain_id,
            source="manual",
            target_hostname=hostname,
            status="queued",
        )
        db.add(job)
        db.commit()
        job_id_str = str(job.id)
    finally:
        db.close()

    return run_scan_job(job_id_str)


@celery_app.task(name="scheduled_scan_sweep")
def scheduled_scan_sweep():
    """Periodic task: enqueue a scan for every domain with monitoring enabled, respecting opt-outs, dedupe, and cooldown."""
    db = SessionLocal()
    r = get_redis_client()
    enqueued_count = 0

    try:
        domains = db.query(Domain).filter(Domain.monitoring_enabled == True).all()
        for domain in domains:
            parsed = urlsplit(domain.url)
            hostname = (parsed.hostname or "").strip().lower()

            # 1. Opt-out check
            if db.query(ScanOptOut).filter(ScanOptOut.hostname == hostname).first():
                continue

            # 2. Dedupe: already queued or running
            if db.query(ScanJob).filter(
                ScanJob.domain_id == domain.id,
                ScanJob.status.in_(["queued", "running"]),
            ).first():
                continue

            # 3. Cooldown check
            if r:
                try:
                    if r.exists(f"scan:cooldown:{hostname}"):
                        continue
                except Exception:
                    pass

            # Create scheduled job
            job = ScanJob(
                id=uuid.uuid4(),
                domain_id=domain.id,
                requested_by_user_id=domain.owner_id,
                source="scheduled",
                target_hostname=hostname,
                status="queued",
                progress={"headers": "pending", "tls": "pending", "dns": "pending", "cookies": "pending"},
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            task = run_scan_job.delay(str(job.id))
            job.celery_task_id = task.id
            db.commit()

            if r:
                try:
                    r.set(f"scan:cooldown:{hostname}", "1", ex=300)
                except Exception:
                    pass

            enqueued_count += 1
    finally:
        db.close()

    return {"enqueued": enqueued_count}
