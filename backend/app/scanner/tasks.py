import json

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Scan
from app.scanner.headers import scan_headers
from app.scanner.tls import scan_tls


# Category weights — how much each contributes to the overall score
HEADERS_WEIGHT = 0.6
TLS_WEIGHT = 0.4


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


@celery_app.task(name="run_domain_scan")
def run_domain_scan(domain_id: int, url: str) -> dict:
    """Background task: run all scan categories, combine, and persist."""
    headers_result = scan_headers(url)
    tls_result = scan_tls(url)

    # Weighted overall score (each category is already 0–100)
    headers_score = headers_result.get("score", 0)
    tls_score = tls_result.get("score", 0)
    overall_score = round(headers_score * HEADERS_WEIGHT + tls_score * TLS_WEIGHT)
    overall_grade = _combined_grade(overall_score)

    # Bundle the full breakdown for storage + frontend
    full_results = {
        "headers": {
            "score": headers_score,
            "checks": headers_result.get("checks", []),
            "error": headers_result.get("error"),
        },
        "tls": {
            "score": tls_score,
            "checks": tls_result.get("checks", []),
            "protocol": tls_result.get("protocol"),
            "error": tls_result.get("error"),
        },
    }

    db = SessionLocal()
    try:
        scan = Scan(
            domain_id=domain_id,
            grade=overall_grade,
            score=overall_score,
            results_json=json.dumps(full_results),
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)
        scan_id = scan.id
    finally:
        db.close()

    return {
        "scan_id": scan_id,
        "grade": overall_grade,
        "score": overall_score,
        "final_url": headers_result.get("final_url"),
        "status_code": headers_result.get("status_code"),
        "categories": full_results,  # headers + tls, each with their checks
        "error": headers_result.get("error"),
    }