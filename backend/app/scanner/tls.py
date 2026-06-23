import socket
import ssl
from datetime import datetime, timezone
from urllib.parse import urlparse


def _parse_host(url: str) -> str:
    """Extract just the hostname from a URL."""
    parsed = urlparse(url)
    return parsed.hostname or url.replace("https://", "").replace("http://", "").split("/")[0]


def scan_tls(url: str) -> dict:
    """
    Inspect a host's TLS certificate and negotiated protocol.
    Pure function: takes a URL, returns a result dict. No DB, no web layer.
    """
    host = _parse_host(url)
    checks = []
    score = 0

    context = ssl.create_default_context()

    try:
        with socket.create_connection((host, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                protocol = ssock.version()  # e.g. "TLSv1.3"
    except (socket.gaierror, socket.timeout, ConnectionRefusedError) as exc:
        return {
            "error": f"Could not establish TLS connection: {exc.__class__.__name__}",
            "unreachable": True,
            "score": 0,
            "checks": [],
        }
    except ssl.SSLCertVerificationError as exc:
        # Connected, but the certificate failed verification — a real finding
        return {
            "error": None,
            "score": 0,
            "checks": [{
                "name": "Certificate Validation",
                "passed": False,
                "detail": f"Certificate failed verification: {exc.reason}",
                "weight": 40,
                "advice": "Install a valid certificate from a trusted CA.",
            }],
        }
    except Exception as exc:
        return {
            "error": f"TLS scan failed: {exc.__class__.__name__}",
            "score": 0,
            "checks": [],
        }

    # ---- Check 1: Certificate is valid & trusted (we got here = it verified) ----
    checks.append({
        "name": "Valid Certificate",
        "passed": True,
        "detail": "Certificate is valid and issued by a trusted CA.",
        "weight": 40,
        "advice": None,
    })
    score += 40

    # ---- Check 2: Certificate expiry ----
    not_after = cert.get("notAfter")
    expiry_passed = False
    expiry_detail = "Could not read certificate expiry."
    if not_after:
        expiry_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(
            tzinfo=timezone.utc
        )
        days_left = (expiry_dt - datetime.now(timezone.utc)).days
        if days_left > 30:
            expiry_passed = True
            expiry_detail = f"Certificate valid for {days_left} more days."
            score += 30
        elif days_left > 0:
            expiry_detail = f"Certificate expires soon — only {days_left} days left."
            score += 15  # partial credit; it's valid but worryingly close
        else:
            expiry_detail = "Certificate has EXPIRED."
    checks.append({
        "name": "Certificate Expiry",
        "passed": expiry_passed,
        "detail": expiry_detail,
        "weight": 30,
        "advice": None if expiry_passed else "Renew the certificate well before expiry.",
    })

    # ---- Check 3: Modern protocol (TLS 1.2 or 1.3 only) ----
    modern = protocol in ("TLSv1.2", "TLSv1.3")
    if modern:
        score += 30
    checks.append({
        "name": "Protocol Version",
        "passed": modern,
        "detail": f"Negotiated {protocol}." + (
            "" if modern else " Deprecated protocol — upgrade to TLS 1.2+."
        ),
        "weight": 30,
        "advice": None if modern else "Disable TLS 1.0/1.1; allow only TLS 1.2 and 1.3.",
    })

    return {
        "error": None,
        "unreachable": False,
        "host": host,
        "protocol": protocol,
        "score": score,
        "checks": checks,
    }
