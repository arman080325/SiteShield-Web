from app.reports.pdf_report import generate_domain_report


def test_pdf_report_escapes_markup():
    """Verify that dangerous strings in dynamic scan fields do not break ReportLab XML parsing."""
    dangerous_url = "https://example.com/<script>alert('xss')</script>&foo=1<b"
    scans = [
        {
            "id": 1,
            "created_at": "2026-11-07T12:00:00Z",
            "grade": "B",
            "score": 82,
            "categories": {
                "headers": {
                    "score": 75,
                    "unreachable": False,
                    "checks": [
                        {
                            "header": "Content-Security-Policy",
                            "present": True,
                            "value": "default-src 'self' <script>&bad='1' &amp; \"test\"",
                            "weight": 25,
                            "advice": "Review policy syntax & fix <b unclosed tags &amp; errors",
                        },
                        {
                            "header": "Strict-Transport-Security",
                            "present": False,
                            "value": None,
                            "weight": 20,
                            "advice": "Add HSTS header with max-age >= 31536000 & includeSubDomains <tag>",
                        },
                    ],
                },
                "tls": {
                    "score": 90,
                    "unreachable": False,
                    "protocol": "TLSv1.3",
                    "checks": [
                        {
                            "name": "Certificate Expiry",
                            "passed": False,
                            "partial": True,
                            "detail": "Expires in 12 days <script> & <b>warning</b>",
                            "weight": 30,
                            "advice": "Renew certificate before it expires & check CA <anchor>",
                        },
                        {
                            "name": "Valid Certificate",
                            "passed": True,
                            "partial": False,
                            "detail": "Trusted CA & valid SANs list: *.example.com <script>",
                            "weight": 40,
                            "advice": None,
                        },
                    ],
                },
                "dns": {
                    "score": 80,
                    "unreachable": False,
                    "checks": [
                        {
                            "name": "SPF Record",
                            "passed": True,
                            "detail": "v=spf1 include:_spf.google.com ~all & TXT <evil>",
                            "weight": 10,
                            "advice": None,
                        },
                        {
                            "name": "DMARC Record",
                            "passed": False,
                            "detail": "p=none & rua=mailto:dmarc@example.com?body=<script>",
                            "weight": 10,
                            "advice": "Switch policy from p=none to p=quarantine & monitor reports <b",
                        },
                    ],
                },
                "cookies": {
                    "score": 85,
                    "unreachable": False,
                    "checks": [
                        {
                            "name": "Session Cookie Flags",
                            "passed": False,
                            "detail": "Cookie 'sess_id' missing Secure flag & SameSite=<script>",
                            "weight": 15,
                            "advice": "Set Secure, HttpOnly, and SameSite=Lax on all session cookies & tokens <b",
                        }
                    ],
                },
            },
        }
    ]

    pdf_bytes = generate_domain_report(dangerous_url, scans)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF"), "Generated report must be a valid PDF binary"
    assert len(pdf_bytes) > 1000


def test_pdf_report_empty_scans():
    """Verify that a report can be built for a domain with no scans yet."""
    pdf_bytes = generate_domain_report("https://empty.example.com", [])
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_pdf_report_legacy_scan_null_categories():
    """Verify that a legacy scan with categories=None builds cleanly."""
    legacy_scans = [
        {
            "id": 10,
            "created_at": "2026-06-01T10:00:00Z",
            "grade": "C",
            "score": 65,
            "categories": None,
        }
    ]
    pdf_bytes = generate_domain_report("https://legacy.example.com", legacy_scans)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500
