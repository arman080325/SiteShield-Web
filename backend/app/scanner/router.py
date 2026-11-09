import json
import uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.ratelimit import get_user_or_ip, limiter
from app.core.redis_client import get_redis_client
from app.database import get_db
from app.models import Domain, Scan, ScanJob, ScanOptOut, User
from app.reports.pdf_report import generate_domain_report
from app.scanner.tasks import run_scan_job
from app.schemas import ScanDetail

router = APIRouter(prefix="/domains", tags=["scans"])


@router.post("/{domain_id}/scan", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("30/hour", key_func=get_user_or_ip)
def start_scan(
    request: Request,
    response: Response,
    domain_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Ownership-scoped lookup — same IDOR protection as the CRUD endpoints
    domain = (
        db.query(Domain)
        .filter(Domain.id == domain_id, Domain.owner_id == current_user.id)
        .first()
    )
    if domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")

    parsed = urlsplit(domain.url)
    hostname = (parsed.hostname or "").strip().lower()

    # 1. Opt-out check
    opt_out = (
        db.query(ScanOptOut)
        .filter(ScanOptOut.hostname == hostname)
        .first()
    )
    if opt_out:
        raise HTTPException(
            status_code=400,
            detail="This domain has opted out of SiteShield scans.",
        )

    # 2. User deduplication: If user already has a queued or running job for this domain, return it
    existing_job = (
        db.query(ScanJob)
        .filter(
            ScanJob.domain_id == domain.id,
            ScanJob.requested_by_user_id == current_user.id,
            ScanJob.status.in_(["queued", "running"]),
        )
        .order_by(ScanJob.created_at.desc())
        .first()
    )
    if existing_job:
        return Response(
            content=json.dumps({
                "job_id": str(existing_job.id),
                "status": existing_job.status,
                "progress": existing_job.progress,
                "message": "Scan already in progress",
            }),
            media_type="application/json",
            status_code=status.HTTP_200_OK,
        )

    # 3. Domain cache: If THIS domain was scanned < 5 min ago, return latest scan with cached: true
    five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
    recent_scan = (
        db.query(Scan)
        .filter(Scan.domain_id == domain.id, Scan.created_at >= five_min_ago)
        .order_by(Scan.created_at.desc())
        .first()
    )
    if recent_scan:
        recent_job = (
            db.query(ScanJob)
            .filter(ScanJob.scan_id == recent_scan.id)
            .order_by(ScanJob.created_at.desc())
            .first()
        )
        job_id_val = str(recent_job.id) if recent_job else str(uuid.uuid4())
        return Response(
            content=json.dumps({
                "job_id": job_id_val,
                "status": "succeeded",
                "scan_id": recent_scan.id,
                "cached": True,
            }),
            media_type="application/json",
            status_code=status.HTTP_200_OK,
        )

    # 4. Cross-tenant cooldown: Check Redis cooldown key
    redis_client = get_redis_client()
    cooldown_key = f"scan:cooldown:{hostname}"
    if redis_client:
        try:
            ttl = redis_client.ttl(cooldown_key)
            if ttl and ttl > 0:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"This target was recently scanned. Please retry in {ttl} seconds.",
                    headers={"Retry-After": str(ttl)},
                )
        except HTTPException:
            raise
        except Exception:
            pass  # if redis is down or errored, proceed

    # 5. Create ScanJob and enqueue Celery task
    new_job = ScanJob(
        id=uuid.uuid4(),
        domain_id=domain.id,
        requested_by_user_id=current_user.id,
        source="manual",
        target_hostname=hostname,
        status="queued",
        progress={"headers": "pending", "tls": "pending", "dns": "pending", "cookies": "pending"},
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    # Set initial cooldown in Redis
    if redis_client:
        try:
            redis_client.set(cooldown_key, "1", ex=300)
        except Exception:
            pass

    # Enqueue Celery task
    task = run_scan_job.delay(str(new_job.id))
    new_job.celery_task_id = task.id
    db.commit()

    return Response(
        content=json.dumps({
            "job_id": str(new_job.id),
            "status": "queued",
        }),
        media_type="application/json",
        status_code=status.HTTP_202_ACCEPTED,
    )


@router.get("/scan-jobs/{job_id}")
def get_scan_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Scan job not found")

    job = (
        db.query(ScanJob)
        .join(Domain, ScanJob.domain_id == Domain.id)
        .filter(ScanJob.id == job_uuid, Domain.owner_id == current_user.id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Scan job not found")

    return {
        "job_id": str(job.id),
        "status": job.status,
        "progress": job.progress,
        "error": job.error,
        "scan_id": job.scan_id,
    }


@router.get("/{domain_id}/scans", response_model=list[ScanDetail])
def list_scans(
    domain_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    domain = (
        db.query(Domain)
        .filter(Domain.id == domain_id, Domain.owner_id == current_user.id)
        .first()
    )
    if domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")

    scans = (
        db.query(Scan)
        .filter(Scan.domain_id == domain_id)
        .order_by(Scan.created_at.desc())
        .all()
    )

    # Parse stored JSON breakdown into structured categories
    result = []
    for scan in scans:
        categories = None
        try:
            if scan.results_json:
                parsed = json.loads(scan.results_json)
                if isinstance(parsed, dict) and (
                    "headers" in parsed or "tls" in parsed or "dns" in parsed
                ):
                    categories = parsed
        except (json.JSONDecodeError, TypeError):
            categories = None
        result.append(ScanDetail(
            id=scan.id,
            domain_id=scan.domain_id,
            grade=scan.grade,
            score=scan.score,
            created_at=scan.created_at,
            categories=categories,
        ))
    return result


@router.get("/{domain_id}/report")
def download_report(
    domain_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    domain = (
        db.query(Domain)
        .filter(Domain.id == domain_id, Domain.owner_id == current_user.id)
        .first()
    )
    if domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")

    scans = (
        db.query(Scan)
        .filter(Scan.domain_id == domain_id)
        .order_by(Scan.created_at.desc())
        .all()
    )

    scan_dicts = []
    for scan in scans:
        categories = None
        try:
            if scan.results_json:
                parsed = json.loads(scan.results_json)
                if isinstance(parsed, dict) and (
                    "headers" in parsed or "tls" in parsed or "dns" in parsed
                ):
                    categories = parsed
        except (json.JSONDecodeError, TypeError):
            categories = None
        scan_dicts.append({
            "grade": scan.grade,
            "score": scan.score,
            "created_at": scan.created_at.isoformat() if scan.created_at else None,
            "categories": categories,
        })

    pdf_bytes = generate_domain_report(domain.url, scan_dicts)

    safe_name = domain.url.replace("https://", "").replace("http://", "").replace("/", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="siteshield_{safe_name}.pdf"'
        },
    )
