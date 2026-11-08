"""Unit tests for the pure scanner functions — no DB, no network mocking needed
for the scoring logic itself."""

from app.scanner.cookies import scan_cookies
from app.scanner.net.http_fetch import FetchResult


def test_cookies_no_cookies_is_full_score():
    """A site that sets no cookies has no cookie-risk surface → 100."""
    fetch_res = FetchResult(
        final_url="https://example.com",
        status_code=200,
        cookies=[],
    )
    result = scan_cookies("https://example.com", fetch_result=fetch_res)
    assert result["score"] == 100
    assert result["unreachable"] is False


def test_cookies_unreachable_flag():
    """A site we can't reach is flagged unreachable, not scored 0 as a finding."""
    fetch_res = FetchResult(
        final_url="https://unreachable.invalid",
        unreachable=True,
        error="Could not reach the site: RequestError",
    )
    result = scan_cookies("https://unreachable.invalid", fetch_result=fetch_res)
    assert result["unreachable"] is True
    assert result["score"] == 0


def test_tls_certificate_expiry_scoring(monkeypatch):
    """
    Assert scoring invariance and partial credit flag for certificate expiry:
    - 20 days left: passed == False, partial == True, weight == 30, score == 85 (40 + 15 + 30).
    - 60 days left: passed == True, partial == False, weight == 30, score == 100.
    """
    from datetime import datetime, timezone, timedelta
    from app.scanner.tls import scan_tls
    import app.scanner.tls as tls_mod

    class FakeSSLSocket:
        def __init__(self, cert, protocol="TLSv1.3"):
            self._cert = cert
            self._protocol = protocol

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def getpeercert(self):
            return self._cert

        def version(self):
            return self._protocol

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class FakeContext:
        def __init__(self, ssock):
            self._ssock = ssock

        def wrap_socket(self, sock, server_hostname=None):
            return self._ssock

    monkeypatch.setattr(tls_mod.socket, "create_connection", lambda *a, **k: FakeSocket())

    # Case 1: Certificate expires in 20 days (partial credit)
    now = datetime.now(timezone.utc)
    future_20 = now + timedelta(days=20, hours=2)
    cert_20 = {"notAfter": future_20.strftime("%b %d %H:%M:%S %Y GMT")}
    monkeypatch.setattr(
        tls_mod.ssl,
        "create_default_context",
        lambda *a, **k: FakeContext(FakeSSLSocket(cert_20, "TLSv1.3")),
    )

    res_20 = scan_tls("https://example.com")
    expiry_20 = next(c for c in res_20["checks"] if c["name"] == "Certificate Expiry")
    assert expiry_20["passed"] is False
    assert expiry_20["partial"] is True
    assert expiry_20["weight"] == 30
    assert res_20["score"] == 85

    # Case 2: Certificate expires in 60 days (full credit)
    future_60 = now + timedelta(days=60, hours=2)
    cert_60 = {"notAfter": future_60.strftime("%b %d %H:%M:%S %Y GMT")}
    monkeypatch.setattr(
        tls_mod.ssl,
        "create_default_context",
        lambda *a, **k: FakeContext(FakeSSLSocket(cert_60, "TLSv1.3")),
    )

    res_60 = scan_tls("https://example.com")
    expiry_60 = next(c for c in res_60["checks"] if c["name"] == "Certificate Expiry")
    assert expiry_60["passed"] is True
    assert expiry_60.get("partial") is False
    assert expiry_60["weight"] == 30
    assert res_60["score"] == 100
