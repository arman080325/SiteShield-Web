import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from celery.result import AsyncResult

from app.database import get_db
from app.models import User, Domain, Scan
from app.schemas import ScanOut,ScanDetail
from app.auth.dependencies import get_current_user
from app.scanner.tasks import run_domain_scan
from app.celery_app import celery_app
from fastapi import Response
from app.reports.pdf_report import generate_domain_report


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

    # Parse the stored JSON breakdown into structured categories
    result = []
    for scan in scans:
        categories = None
        try:
            if scan.results_json:
                parsed = json.loads(scan.results_json)
                # Only accept the NEW multi-category shape (a dict with our keys).
                # Old scans stored a flat list of checks — skip those gracefully.
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

    # Shape scans for the report generator
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