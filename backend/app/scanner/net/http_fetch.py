import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit
import httpx

from app.config import settings
from app.scanner.net.ssrf_guard import UnsafeTargetError, is_public_ip, resolve_public, validate_url_syntax

MAX_REDIRECTS = 5
MAX_BODY_BYTES = 1024 * 1024  # 1 MB


@dataclass
class FetchResult:
    final_url: str
    status_code: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    all_headers: list[tuple[str, str]] = field(default_factory=list)
    cookies: list[dict] = field(default_factory=list)
    redirect_chain: list[dict] = field(default_factory=list)
    peer_ip: str | None = None
    elapsed_ms: float = 0.0
    body_truncated: bytes = b""
    unreachable: bool = False
    error: str | None = None


def fetch_target(url: str, timeout: float = 10.0) -> FetchResult:
    """
    Perform an SSRF-safe HTTP GET request, manually following redirects up to 5 hops.
    Validates host, port, scheme, resolved IP, and peer IP at each hop.
    Caps total timeout at `timeout` seconds and response body at 1 MB.
    """
    start_time = time.perf_counter()
    deadline = start_time + timeout

    current_url = url.strip()
    redirect_chain: list[dict] = []
    all_cookies: list[dict] = []

    # Initial syntax & SSRF check
    scheme, hostname, port = validate_url_syntax(current_url)
    try:
        resolve_public(hostname, port)
    except socket_gaierror_types() as exc:
        return FetchResult(
            final_url=current_url,
            unreachable=True,
            error=f"DNS resolution failed: {exc}",
        )

    headers = {
        "User-Agent": settings.scanner_user_agent,
        "Accept": "*/*",
    }

    try:
        with httpx.Client(
            verify=True,
            follow_redirects=False,
            headers=headers,
        ) as client:
            for hop in range(MAX_REDIRECTS + 1):
                remaining_timeout = max(0.5, deadline - time.perf_counter())

                try:
                    response = client.get(current_url, timeout=remaining_timeout)
                except httpx.RequestError as exc:
                    return FetchResult(
                        final_url=current_url,
                        unreachable=True,
                        error=f"HTTP request error: {exc.__class__.__name__}",
                        redirect_chain=redirect_chain,
                    )

                # Post-connect verification on peer IP (fail-closed anti-rebinding check)
                peer_ip = _extract_peer_ip(response)
                if not peer_ip or not is_public_ip(peer_ip):
                    raise UnsafeTargetError(
                        f"Peer address ({peer_ip}) is missing or not a public address"
                    )

                # Collect cookies across hops
                for name, value in response.headers.multi_items():
                    if name.lower() == "set-cookie":
                        all_cookies.append({
                            "raw": value,
                            "url": current_url,
                            "hop": hop,
                        })

                # Check redirect
                if response.is_redirect or response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location:
                        break  # Redirect status but no Location header

                    next_url = urljoin(current_url, location)
                    redirect_chain.append({
                        "from_url": current_url,
                        "to_url": next_url,
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "peer_ip": peer_ip,
                    })

                    # Validate next hop URL and IP
                    next_scheme, next_host, next_port = validate_url_syntax(next_url)
                    resolve_public(next_host, next_port)

                    current_url = next_url
                    continue

                # Final response reached
                content = response.content[:MAX_BODY_BYTES]
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0

                return FetchResult(
                    final_url=str(response.url),
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    all_headers=list(response.headers.multi_items()),
                    cookies=all_cookies,
                    redirect_chain=redirect_chain,
                    peer_ip=peer_ip,
                    elapsed_ms=elapsed_ms,
                    body_truncated=content,
                    unreachable=False,
                    error=None,
                )

            # Reached max redirects without terminal response
            return FetchResult(
                final_url=current_url,
                unreachable=True,
                error="Too many redirects (exceeded 5 hops)",
                redirect_chain=redirect_chain,
            )

    except UnsafeTargetError:
        raise
    except Exception as exc:
        return FetchResult(
            final_url=current_url,
            unreachable=True,
            error=f"Fetch failed: {exc.__class__.__name__}",
            redirect_chain=redirect_chain,
        )


def _extract_peer_ip(response: httpx.Response) -> str | None:
    """Extract peer IP from response extensions network_stream."""
    stream = response.extensions.get("network_stream")
    if not stream:
        return None
    try:
        server_addr = stream.get_extra_info("server_addr")
    except Exception:
        return None

    if not server_addr:
        return None

    if isinstance(server_addr, (tuple, list)) and len(server_addr) > 0:
        return str(server_addr[0])
    if isinstance(server_addr, str):
        return server_addr
    return None


def socket_gaierror_types():
    import socket
    return (socket.gaierror, socket.timeout)
