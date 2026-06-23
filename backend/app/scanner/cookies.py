import httpx


def scan_cookies(url: str) -> dict:
    """
    Inspect Secure / HttpOnly / SameSite flags on the cookies a site sets.
    Pure function — takes a URL, returns a result dict.
    """
    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=10.0,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SiteShield-Scanner/1.0)"},
        )
    except httpx.RequestError as exc:
        return {
            "error": f"Could not reach the site: {exc.__class__.__name__}",
            "unreachable": True,
            "score": 0,
            "checks": [],
        }

    set_cookie_headers = response.headers.get_list("set-cookie")

    # No cookies set = no cookie-based risk surface → full marks
    if not set_cookie_headers:
        return {
            "error": None,
            "unreachable": False,
            "score": 100,
            "checks": [{
                "name": "Cookie Security",
                "passed": True,
                "detail": "Site sets no cookies — no cookie-based risk surface.",
                "weight": 100,
                "advice": None,
            }],
        }

    total = len(set_cookie_headers)
    secure_count = sum(1 for c in set_cookie_headers if "secure" in c.lower())
    httponly_count = sum(1 for c in set_cookie_headers if "httponly" in c.lower())
    samesite_count = sum(1 for c in set_cookie_headers if "samesite" in c.lower())

    secure_ok = secure_count == total
    httponly_ok = httponly_count == total
    samesite_ok = samesite_count == total

    score = 0
    if secure_ok:
        score += 40
    if httponly_ok:
        score += 35
    if samesite_ok:
        score += 25

    checks = [
        {
            "name": "Secure flag",
            "passed": secure_ok,
            "detail": f"{secure_count}/{total} cookies set Secure."
            + ("" if secure_ok else " Cookies without Secure can leak over HTTP."),
            "weight": 40,
            "advice": None if secure_ok
            else "Set the Secure flag on all cookies so they're only sent over HTTPS.",
        },
        {
            "name": "HttpOnly flag",
            "passed": httponly_ok,
            "detail": f"{httponly_count}/{total} cookies set HttpOnly."
            + ("" if httponly_ok else " Cookies without HttpOnly are readable by JavaScript (XSS risk)."),
            "weight": 35,
            "advice": None if httponly_ok
            else "Set HttpOnly on all cookies to block JavaScript access and mitigate XSS theft.",
        },
        {
            "name": "SameSite attribute",
            "passed": samesite_ok,
            "detail": f"{samesite_count}/{total} cookies set SameSite."
            + ("" if samesite_ok else " Cookies without SameSite are more exposed to CSRF."),
            "weight": 25,
            "advice": None if samesite_ok
            else "Set SameSite (Lax or Strict) on all cookies to reduce CSRF risk.",
        },
    ]

    return {
        "error": None,
        "unreachable": False,
        "score": score,
        "checks": checks,
    }