import json

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Scan
from app.scanner.headers import scan_headers


@celery_app.task(name="run_domain_scan")
def run_domain_scan(domain_id: int, url: str) -> dict:
    """Background task: scan a domain's headers and persist the result."""
    result = scan_headers(url)

    # Workers get their own DB session (separate process)
    db = SessionLocal()
    try:
        scan = Scan(
            domain_id=domain_id,
            grade=result["grade"],
            score=result["score"],
            results_json=json.dumps(result["checks"]),
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)
        scan_id = scan.id
    finally:
        db.close()

    return {
        "scan_id": scan_id,
        "grade": result["grade"],
        "score": result["score"],
        "final_url": result.get("final_url"),
        "status_code": result.get("status_code"),
        "checks": result["checks"],
        "error": result.get("error"),
    }