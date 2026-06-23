import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from celery.result import AsyncResult

from app.database import get_db
from app.models import User, Domain, Scan
from app.schemas import ScanOut
from app.auth.dependencies import get_current_user
from app.scanner.tasks import run_domain_scan
from app.celery_app import celery_app

router = APIRouter(prefix="/domains", tags=["scans"])


@router.post("/{domain_id}/scan", status_code=202)
def start_scan(
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

    # Enqueue the job — returns immediately with a task id
    task = run_domain_scan.delay(domain.id, domain.url)
    return {"task_id": task.id, "status": "queued"}


@router.get("/scan-status/{task_id}")
def scan_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    result = AsyncResult(task_id, app=celery_app)

    if result.state == "PENDING":
        return {"status": "pending"}
    if result.state == "STARTED":
        return {"status": "running"}
    if result.state == "SUCCESS":
        return {"status": "done", "result": result.result}
    if result.state == "FAILURE":
        return {"status": "failed", "error": str(result.info)}

    return {"status": result.state.lower()}


@router.get("/{domain_id}/scans", response_model=list[ScanOut])
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

    return (
        db.query(Scan)
        .filter(Scan.domain_id == domain_id)
        .order_by(Scan.created_at.desc())
        .all()
    )