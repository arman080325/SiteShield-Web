import httpx

# Each header: weight (points) and a short explanation shown in results.
SECURITY_HEADERS = {
    "strict-transport-security": {
        "weight": 20,
        "label": "Strict-Transport-Security (HSTS)",
        "advice": "Add HSTS to force HTTPS and prevent protocol downgrade attacks.",
    },
    "content-security-policy": {
        "weight": 25,
        "label": "Content-Security-Policy (CSP)",
        "advice": "Add a CSP to mitigate XSS and data-injection attacks.",
    },
    "x-frame-options": {
        "weight": 15,
        "label": "X-Frame-Options",
        "advice": "Set X-Frame-Options to DENY or SAMEORIGIN to prevent clickjacking.",
    },
    "x-content-type-options": {
        "weight": 15,
        "label": "X-Content-Type-Options",
        "advice": "Set to 'nosniff' to stop MIME-type sniffing.",
    },
    "referrer-policy": {
        "weight": 15,
        "label": "Referrer-Policy",
        "advice": "Set a Referrer-Policy to limit referrer information leakage.",
    },
    "permissions-policy": {
        "weight": 10,
        "label": "Permissions-Policy",
        "advice": "Add a Permissions-Policy to restrict access to browser features.",
    },
}


def score_to_grade(score: int) -> str:
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


def scan_headers(url: str) -> dict:
    """Fetch a URL and grade its HTTP security headers. Returns a result dict."""
    response = None
    last_error = None
    for attempt in range(2):  # one initial try + one retry for transient blips
        try:
            response = httpx.get(
                url,
                follow_redirects=True,
                timeout=10.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; SiteShield-Scanner/1.0)"
                },
            )
            break
        except httpx.RequestError as exc:
            last_error = exc
            continue

    if response is None:
        # Couldn't reach the site — flag as unreachable so the scoring
        # engine EXCLUDES this category instead of scoring it 0.
        return {
            "error": f"Could not reach the site: {last_error.__class__.__name__}",
            "unreachable": True,
            "score": 0,
            "grade": "F",
            "checks": [],
        }

    # httpx header lookups are case-insensitive
    present_headers = response.headers

    checks = []
    score = 0
    for key, meta in SECURITY_HEADERS.items():
        value = present_headers.get(key)
        is_present = value is not None
        if is_present:
            score += meta["weight"]
        checks.append({
            "header": meta["label"],
            "present": is_present,
            "value": value if is_present else None,
            "weight": meta["weight"],
            "advice": None if is_present else meta["advice"],
        })

    return {
        "error": None,
        "unreachable": False,
        "final_url": str(response.url),
        "status_code": response.status_code,
        "score": score,
        "grade": score_to_grade(score),
        "checks": checks,
    }