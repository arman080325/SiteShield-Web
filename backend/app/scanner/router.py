import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Domain, Scan
from app.schemas import ScanResult, ScanOut, HeaderCheck
from app.auth.dependencies import get_current_user
from app.scanner.headers import scan_headers

router = APIRouter(prefix="/domains", tags=["scans"])


@router.post("/{domain_id}/scan", response_model=ScanResult, status_code=201)
def run_scan(
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

    result = scan_headers(domain.url)

    # Persist the scan summary; store the full checks payload as JSON
    scan = Scan(
        domain_id=domain.id,
        grade=result["grade"],
        score=result["score"],
        results_json=json.dumps(result["checks"]),
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    return ScanResult(
        scan=ScanOut.model_validate(scan),
        final_url=result.get("final_url"),
        status_code=result.get("status_code"),
        checks=[HeaderCheck(**c) for c in result["checks"]],
        error=result.get("error"),
    )


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