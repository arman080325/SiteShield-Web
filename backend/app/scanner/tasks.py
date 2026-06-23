import json

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Scan, Domain
from app.scanner.headers import scan_headers
from app.scanner.tls import scan_tls
from app.scanner.dns_scan import scan_dns
from app.scanner.cookies import scan_cookies


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


@celery_app.task(name="run_domain_scan")
def run_domain_scan(domain_id: int, url: str) -> dict:
    """Background task: run all scan categories, combine, and persist."""
    headers_result = scan_headers(url)
    tls_result = scan_tls(url)
    dns_result = scan_dns(url)
    cookies_result = scan_cookies(url)

    # Each category: (score, base_weight, is_reachable)
    categories_meta = [
        ("headers", headers_result, HEADERS_WEIGHT),
        ("tls", tls_result, TLS_WEIGHT),
        ("dns", dns_result, DNS_WEIGHT),
        ("cookies", cookies_result, COOKIES_WEIGHT),
    ]

    # Only include categories that actually reached/measured the target.
    # A category is "unreachable" if it explicitly flags it.
    weighted_sum = 0.0
    active_weight = 0.0
    for _name, result, weight in categories_meta:
        if result.get("unreachable"):
            continue  # exclude from scoring — we have no measurement
        weighted_sum += result.get("score", 0) * weight
        active_weight += weight

    # Re-normalize across only the categories we could measure
    # if active_weight > 0:
    #     overall_score = round(weighted_sum / active_weight)
    # else:
    #     overall_score = 0  # nothing was reachable at all
    # overall_grade = _combined_grade(overall_score)
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
        "categories": full_results,
        "error": None,
    }


@celery_app.task(name="scheduled_scan_sweep")
def scheduled_scan_sweep():
    """Periodic task: enqueue a scan for every domain with monitoring enabled."""
    db = SessionLocal()
    try:
        domains = db.query(Domain).filter(Domain.monitoring_enabled == True).all()
        count = 0
        for domain in domains:
            run_domain_scan.delay(domain.id, domain.url)
            count += 1
    finally:
        db.close()
    return {"enqueued": count}