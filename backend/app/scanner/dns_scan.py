from urllib.parse import urlparse

import dns.resolver


def _parse_host(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or url.replace("https://", "").replace("http://", "").split("/")[0]
    # Strip a leading www. so we query the registrable domain for email records
    return host[4:] if host.startswith("www.") else host


def _domain_resolves(domain: str) -> bool:
    """Check the domain exists at all (has an A or AAAA record)."""
    for record_type in ("A", "AAAA"):
        try:
            answers = dns.resolver.resolve(domain, record_type, lifetime=8)
            if len(answers) > 0:
                return True
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
                dns.resolver.NoNameservers, dns.exception.Timeout):
            continue
    return False


def _query_txt(domain: str) -> list[str]:
    """Return all TXT record strings for a domain (empty list if none/error)."""
    try:
        answers = dns.resolver.resolve(domain, "TXT", lifetime=8)
        records = []
        for rdata in answers:
            # TXT records come as bytes chunks; join + decode
            records.append(b"".join(rdata.strings).decode(errors="ignore"))
        return records
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
            dns.resolver.NoNameservers, dns.exception.Timeout):
        return []


def scan_dns(url: str) -> dict:
    """
    Check DNS-level security records: SPF, DMARC, CAA.
    Pure function — takes a URL, returns a result dict.
    """
    domain = _parse_host(url)

    # If the domain doesn't resolve at all, we have no measurement —
    # flag unreachable so the scoring engine EXCLUDES this category
    # (rather than scoring a real-but-missing-records 0).
    if not _domain_resolves(domain):
        return {
            "error": f"Could not resolve domain: {domain}",
            "unreachable": True,
            "domain": domain,
            "score": 0,
            "checks": [],
        }

    checks = []
    score = 0

    # ---- SPF: a TXT record on the domain starting with "v=spf1" ----
    txt_records = _query_txt(domain)
    spf = next((r for r in txt_records if r.lower().startswith("v=spf1")), None)
    spf_present = spf is not None
    if spf_present:
        score += 35
    checks.append({
        "name": "SPF Record",
        "passed": spf_present,
        "detail": spf if spf_present else "No SPF record found.",
        "weight": 35,
        "advice": None if spf_present
        else "Publish an SPF record to declare authorized mail servers and reduce spoofing.",
    })

    # ---- DMARC: a TXT record at _dmarc.<domain> starting with "v=DMARC1" ----
    dmarc_records = _query_txt(f"_dmarc.{domain}")
    dmarc = next((r for r in dmarc_records if r.lower().startswith("v=dmarc1")), None)
    dmarc_present = dmarc is not None
    if dmarc_present:
        score += 40
    checks.append({
        "name": "DMARC Record",
        "passed": dmarc_present,
        "detail": dmarc if dmarc_present else "No DMARC record found.",
        "weight": 40,
        "advice": None if dmarc_present
        else "Publish a DMARC policy to control handling of mail that fails authentication.",
    })

    # ---- CAA: restricts which CAs may issue certs for the domain ----
    caa_present = False
    try:
        caa_answers = dns.resolver.resolve(domain, "CAA", lifetime=8)
        caa_present = len(caa_answers) > 0
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
            dns.resolver.NoNameservers, dns.exception.Timeout):
        caa_present = False
    if caa_present:
        score += 25
    checks.append({
        "name": "CAA Record",
        "passed": caa_present,
        "detail": "CAA record present — restricts which CAs can issue certificates."
        if caa_present else "No CAA record found.",
        "weight": 25,
        "advice": None if caa_present
        else "Add a CAA record to restrict certificate issuance to specific CAs.",
    })

    return {
        "error": None,
        "unreachable": False,
        "domain": domain,
        "score": score,
        "checks": checks,
    }