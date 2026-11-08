import socket
import pytest
import respx
import httpx
from app.scanner.net.ssrf_guard import UnsafeTargetError, is_public_ip, resolve_public, validate_url_syntax
from app.scanner.net.http_fetch import fetch_target
from app.scanner.tls import scan_tls


# -----------------------------------------------------------------------------
# 12 Target SSRF Cases
# -----------------------------------------------------------------------------

def test_ssrf_case_1_localhost():
    with pytest.raises(UnsafeTargetError):
        validate_url_syntax("http://localhost")
    with pytest.raises(UnsafeTargetError):
        resolve_public("localhost", 80)


def test_ssrf_case_2_127_0_0_1():
    with pytest.raises(UnsafeTargetError):
        validate_url_syntax("http://127.0.0.1")
    with pytest.raises(UnsafeTargetError):
        resolve_public("127.0.0.1", 80)


def test_ssrf_case_3_ipv6_loopback():
    with pytest.raises(UnsafeTargetError):
        validate_url_syntax("http://[::1]")
    with pytest.raises(UnsafeTargetError):
        resolve_public("[::1]", 80)


def test_ssrf_case_4_private_class_a():
    with pytest.raises(UnsafeTargetError):
        validate_url_syntax("http://10.0.0.5")
    with pytest.raises(UnsafeTargetError):
        resolve_public("10.0.0.5", 80)


def test_ssrf_case_5_cloud_metadata():
    with pytest.raises(UnsafeTargetError):
        validate_url_syntax("http://169.254.169.254")
    with pytest.raises(UnsafeTargetError):
        resolve_public("169.254.169.254", 80)


def test_ssrf_case_6_single_label_redis():
    with pytest.raises(UnsafeTargetError):
        validate_url_syntax("http://redis")
    with pytest.raises(UnsafeTargetError):
        resolve_public("redis", 80)


def test_ssrf_case_7_cloud_internal_domain():
    with pytest.raises(UnsafeTargetError):
        validate_url_syntax("http://metadata.google.internal")
    with pytest.raises(UnsafeTargetError):
        resolve_public("metadata.google.internal", 80)


def test_ssrf_case_8_dns_resolving_to_private_ip(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.50", int(port)))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(UnsafeTargetError):
        resolve_public("evil.example.com", 443)


@respx.mock
def test_ssrf_case_9_redirect_to_private_ip(monkeypatch):
    """Public target returning 302 redirecting to http://127.0.0.1 must be blocked."""
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", int(port)))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    # Fake network_stream with public peer
    class FakeStream:
        def get_extra_info(self, info):
            if info == "server_addr":
                return ("93.184.216.34", 443)
            return None

    route = respx.get("https://public.example.com").mock(
        return_value=httpx.Response(
            302,
            headers={"Location": "http://127.0.0.1/admin"},
            extensions={"network_stream": FakeStream()},
        )
    )

    with pytest.raises(UnsafeTargetError):
        fetch_target("https://public.example.com")


def test_ssrf_case_10_disallowed_port():
    with pytest.raises(UnsafeTargetError):
        validate_url_syntax("http://example.com:6379")
    with pytest.raises(UnsafeTargetError):
        resolve_public("example.com", 6379)


def test_ssrf_case_11_file_scheme():
    with pytest.raises(UnsafeTargetError):
        validate_url_syntax("file:///etc/passwd")


def test_ssrf_case_12_gopher_scheme():
    with pytest.raises(UnsafeTargetError):
        validate_url_syntax("gopher://127.0.0.1:6379/_flushall")


# -----------------------------------------------------------------------------
# Anti-DNS Rebinding (Peer IP Checks)
# -----------------------------------------------------------------------------

@respx.mock
def test_peer_ip_allowed_when_public(monkeypatch):
    """When peer address is public, fetch_target proceeds."""
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", int(port)))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    class FakeStream:
        def get_extra_info(self, info):
            if info == "server_addr":
                return ("93.184.216.34", 443)
            return None

    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200,
            text="Hello world",
            extensions={"network_stream": FakeStream()},
        )
    )

    res = fetch_target("https://example.com")
    assert res.unreachable is False
    assert res.status_code == 200
    assert res.peer_ip == "93.184.216.34"


@respx.mock
def test_peer_ip_rejected_when_missing(monkeypatch):
    """Fail-closed: If network_stream is missing, fetch_target raises UnsafeTargetError."""
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", int(port)))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, text="No stream")
    )

    with pytest.raises(UnsafeTargetError):
        fetch_target("https://example.com")


@respx.mock
def test_peer_ip_rejected_when_private(monkeypatch):
    """Fail-closed: If peer IP resolves public initially but connects to private IP, reject."""
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", int(port)))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    class FakeStream:
        def get_extra_info(self, info):
            if info == "server_addr":
                return ("127.0.0.1", 443)
            return None

    respx.get("https://example.com").mock(
        return_value=httpx.Response(
            200,
            text="Rebound!",
            extensions={"network_stream": FakeStream()},
        )
    )

    with pytest.raises(UnsafeTargetError):
        fetch_target("https://example.com")


# -----------------------------------------------------------------------------
# TLS, Headers, and Cookies Scanner SSRF Protection
# -----------------------------------------------------------------------------

def test_scan_tls_blocks_ssrf_target():
    res = scan_tls("http://127.0.0.1")
    assert res["unreachable"] is True
    assert "SSRF blocked" in res["error"]
    assert res["score"] == 0


@respx.mock
def test_headers_scanner_ssrf_guarded(monkeypatch):
    """When target resolves to 127.0.0.1, scan_headers blocks before network request."""
    from app.scanner.headers import scan_headers

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", int(port)))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    route = respx.get("http://evil-headers.example.com").mock(
        return_value=httpx.Response(200, text="Should never be reached")
    )

    res = scan_headers("http://evil-headers.example.com")
    assert res["unreachable"] is True
    assert res["score"] == 0
    assert "SSRF blocked" in res["error"]
    assert len(res["checks"]) == 0
    # Prove no request was sent
    assert route.call_count == 0


@respx.mock
def test_cookies_scanner_ssrf_guarded(monkeypatch):
    """When target resolves to 127.0.0.1, scan_cookies blocks before network request."""
    from app.scanner.cookies import scan_cookies

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", int(port)))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    route = respx.get("http://evil-cookies.example.com").mock(
        return_value=httpx.Response(200, text="Should never be reached")
    )

    res = scan_cookies("http://evil-cookies.example.com")
    assert res["unreachable"] is True
    assert res["score"] == 0
    assert "SSRF blocked" in res["error"]
    assert len(res["checks"]) == 0
    # Prove no request was sent
    assert route.call_count == 0


# -----------------------------------------------------------------------------
# Domain Creation Endpoint 422 Checks
# -----------------------------------------------------------------------------

def test_create_domain_unresolvable_gives_422(auth_client, monkeypatch):
    client, _ = auth_client

    def unresolvable(host, port, *args, **kwargs):
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", unresolvable)

    resp = client.post("/domains", json={"url": "https://nonexistent-bad-domain-999.xyz"})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "We couldn't find this domain. Check the spelling."


def test_create_domain_private_resolution_gives_422(auth_client, monkeypatch):
    client, _ = auth_client

    def private_dns(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.20.30.40", int(port)))]

    monkeypatch.setattr(socket, "getaddrinfo", private_dns)

    resp = client.post("/domains", json={"url": "https://internal-portal.corp.com"})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "This address isn't publicly reachable, so it can't be scanned."


def test_create_domain_disallowed_syntax_gives_422(auth_client):
    client, _ = auth_client
    # Disallowed scheme
    resp1 = client.post("/domains", json={"url": "ftp://ftp.example.com"})
    assert resp1.status_code == 422

    # Disallowed port
    resp2 = client.post("/domains", json={"url": "https://example.com:8443"})
    assert resp2.status_code == 422
