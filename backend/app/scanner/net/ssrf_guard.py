import ipaddress
import socket
from urllib.parse import urlsplit

ALLOWED_PORTS = {80, 443}
BLOCKED_HOSTNAMES = {"localhost", "redis", "postgres"}
BLOCKED_SUFFIXES = (".local", ".internal", ".localhost", ".home.arpa")


class UnsafeTargetError(Exception):
    """Target resolves to a non-public address or uses a disallowed port/scheme."""


def is_public_ip(ip_val: str | ipaddress._BaseAddress) -> bool:
    """Return True only if the address is a publicly routable global IP."""
    if isinstance(ip_val, str):
        try:
            ip = ipaddress.ip_address(ip_val)
        except ValueError:
            return False
    else:
        ip = ip_val

    # Unwrap IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1 -> 127.0.0.1)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped

    if ip.is_loopback or ip.is_private or ip.is_link_local:
        return False
    if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return False
    # Explicit cloud metadata check
    if str(ip) == "169.254.169.254":
        return False

    return getattr(ip, "is_global", True)


def validate_url_syntax(url: str) -> tuple[str, str, int]:
    """
    Validate URL scheme, port, and hostname format without performing network DNS lookups.
    Returns (scheme, hostname, port).
    Raises UnsafeTargetError or ValueError on invalid/disallowed syntax.
    """
    url = url.strip()
    if not url:
        raise ValueError("URL cannot be empty")

    # If scheme omitted, caller usually prepends https://, but if raw input has scheme:
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise UnsafeTargetError(f"Scheme '{scheme}' is not allowed (only http and https)")

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise ValueError("URL does not contain a valid hostname")

    port = parsed.port
    if port is None:
        port = 80 if scheme == "http" else 443

    if port not in ALLOWED_PORTS:
        raise UnsafeTargetError(f"Port {port} is not allowed (only ports 80 and 443 are allowed)")

    # Reject known blocked hostnames and suffixes
    if hostname in BLOCKED_HOSTNAMES:
        raise UnsafeTargetError(f"Host '{hostname}' is not a permitted public target")

    if any(hostname.endswith(suffix) for suffix in BLOCKED_SUFFIXES):
        raise UnsafeTargetError(f"Host '{hostname}' ends with a private/internal domain suffix")

    # Single label hostnames without a dot (e.g. 'redis', 'postgres', 'metadata')
    if "." not in hostname:
        raise UnsafeTargetError(f"Host '{hostname}' is not a valid fully qualified domain name")

    # If hostname is a bare IP literal
    try:
        ip = ipaddress.ip_address(hostname)
        if not is_public_ip(ip):
            raise UnsafeTargetError(f"Target IP address '{hostname}' is not a public address")
    except ValueError:
        # Not an IP literal, it is a domain name
        pass

    return scheme, hostname, port


def resolve_public(host: str, port: int = 443) -> list[str]:
    """
    Resolve a hostname or IP address, enforcing that ALL resolved IP addresses are public.
    Raises UnsafeTargetError if port is disallowed or any resolved IP is non-public.
    Re-raises socket.gaierror if name cannot be resolved.
    """
    if port not in ALLOWED_PORTS:
        raise UnsafeTargetError(f"Port {port} is not allowed")

    host_clean = host.strip().lower()
    # Strip brackets if IPv6 literal like [::1]
    if host_clean.startswith("[") and host_clean.endswith("]"):
        host_clean = host_clean[1:-1]

    if host_clean in BLOCKED_HOSTNAMES:
        raise UnsafeTargetError(f"Host '{host}' is a disallowed internal hostname")

    if any(host_clean.endswith(suffix) for suffix in BLOCKED_SUFFIXES):
        raise UnsafeTargetError(f"Host '{host}' ends with a private/internal domain suffix")

    if "." not in host_clean:
        try:
            # Check if it's an IPv6 address without dots
            ipaddress.IPv6Address(host_clean)
        except ValueError:
            raise UnsafeTargetError(f"Host '{host}' is not a valid fully qualified domain name")

    # If it is an IP literal
    try:
        ip = ipaddress.ip_address(host_clean)
        if not is_public_ip(ip):
            raise UnsafeTargetError(f"Target '{host}' resolves to a non-public address")
        return [str(ip)]
    except ValueError:
        pass

    # Resolve via socket.getaddrinfo
    try:
        infos = socket.getaddrinfo(host_clean, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise

    addrs = sorted({info[4][0] for info in infos})
    if not addrs:
        raise UnsafeTargetError(f"No addresses resolved for '{host}'")

    for addr in addrs:
        if not is_public_ip(addr):
            raise UnsafeTargetError(f"Host '{host}' resolves to a non-public address ({addr})")

    return addrs
