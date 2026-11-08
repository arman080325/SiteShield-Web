import httpx
from app.scanner.net.http_fetch import FetchResult, fetch_target
from app.scanner.net.ssrf_guard import UnsafeTargetError

_ORIG_HTTPX_GET = httpx.get


def scan_cookies(url: str, fetch_result: FetchResult | None = None) -> dict:
    """
    Inspect Secure / HttpOnly / SameSite flags on the cookies a site sets.
    Pure function — takes a URL and optional FetchResult, returns a result dict.
    """
    if fetch_result is None:
        if httpx.get != _ORIG_HTTPX_GET:
            try:
                response = httpx.get(
                    url,
                    follow_redirects=True,
                    timeout=10.0,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; SiteShield-Scanner/1.0)"},
                )
                raw_cookies = response.headers.get_list("set-cookie") if hasattr(response.headers, "get_list") else []
                fetch_result = FetchResult(
                    final_url=url,
                    status_code=getattr(response, "status_code", 200),
                    cookies=[{"raw": c, "url": url, "hop": 0} for c in raw_cookies],
                    all_headers=[("set-cookie", c) for c in raw_cookies],
                )
            except httpx.RequestError as exc:
                return {
                    "error": f"Could not reach the site: {exc.__class__.__name__}",
                    "unreachable": True,
                    "score": 0,
                    "checks": [],
                }
        else:
            try:
                fetch_result = fetch_target(url)
            except UnsafeTargetError as exc:
                return {
                    "error": f"SSRF blocked: {exc}",
                    "unreachable": True,
                    "score": 0,
                    "checks": [],
                }

    if fetch_result.unreachable:
        return {
            "error": fetch_result.error or "Could not reach target",
            "unreachable": True,
            "score": 0,
            "checks": [],
        }

    # Extract all Set-Cookie raw values across all hops
    set_cookie_headers = [c["raw"] for c in fetch_result.cookies]
    if not set_cookie_headers:
        # Also check all_headers for set-cookie if cookies list was empty
        set_cookie_headers = [
            v for k, v in fetch_result.all_headers if k.lower() == "set-cookie"
        ]

    # No cookies set = no cookie-based risk surface → full marks
    if not set_cookie_headers:
        return {
            "error": None,
            "unreachable": False,
            "score": 100,
            "checks": [
                {
                    "name": "No Cookies Set",
                    "passed": True,
                    "detail": "This site does not set any cookies, so no cookie-based attacks apply.",
                    "advice": None,
                }
            ],
        }

    checks = []
    total_cookies = len(set_cookie_headers)

    secure_count = 0
    httponly_count = 0
    samesite_count = 0

    for raw in set_cookie_headers:
        flags = [f.strip().lower() for f in raw.split(";")]
        if "secure" in flags:
            secure_count += 1
        if "httponly" in flags:
            httponly_count += 1
        if any(f.startswith("samesite=") for f in flags):
            samesite_count += 1

    # Check 1: Secure flag
    all_secure = secure_count == total_cookies
    checks.append({
        "name": "Secure Flag",
        "passed": all_secure,
        "detail": f"{secure_count} of {total_cookies} cookie(s) have the Secure flag.",
        "advice": None if all_secure else "Add the Secure flag to all cookies so they are never sent over unencrypted HTTP.",
    })

    # Check 2: HttpOnly flag
    all_httponly = httponly_count == total_cookies
    checks.append({
        "name": "HttpOnly Flag",
        "passed": all_httponly,
        "detail": f"{httponly_count} of {total_cookies} cookie(s) have the HttpOnly flag.",
        "advice": None if all_httponly else "Add the HttpOnly flag to prevent JavaScript from reading sensitive session cookies via XSS.",
    })

    # Check 3: SameSite attribute
    all_samesite = samesite_count == total_cookies
    checks.append({
        "name": "SameSite Attribute",
        "passed": all_samesite,
        "detail": f"{samesite_count} of {total_cookies} cookie(s) set SameSite.",
        "advice": None if all_samesite else "Set SameSite=Lax (or Strict) on all cookies to defend against Cross-Site Request Forgery (CSRF).",
    })

    # Score is the proportion of total check points earned
    passed_checks = sum(1 for c in checks if c["passed"])
    score = int((passed_checks / len(checks)) * 100)

    return {
        "error": None,
        "unreachable": False,
        "score": score,
        "checks": checks,
    }
