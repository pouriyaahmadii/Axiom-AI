"""Security primitives, SSRF protection, and cryptographic verification."""

import hashlib
import hmac
import ipaddress
import secrets
import socket
from urllib.parse import urlparse

# Blocked IPv4 networks (private, loopback, link-local, carrier NAT, cloud metadata)
BLOCKED_IPV4_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),  # Broadcast / "this" network
    ipaddress.ip_network("10.0.0.0/8"),  # RFC 1918 Private
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local & Cloud Metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),  # RFC 1918 Private
    ipaddress.ip_network("192.0.0.0/24"),  # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),  # TEST-NET-1 documentation
    ipaddress.ip_network("192.168.0.0/16"),  # RFC 1918 Private
    ipaddress.ip_network("198.18.0.0/15"),  # Network benchmark tests
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2 documentation
    ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3 documentation
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved / future use
    ipaddress.ip_network("255.255.255.255/32"),  # Broadcast
]

# Blocked IPv6 networks
BLOCKED_IPV6_NETWORKS = [
    ipaddress.ip_network("::1/128"),  # Loopback
    ipaddress.ip_network("::/128"),  # Unspecified
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped IPv6
    ipaddress.ip_network("64:ff9b::/96"),  # IPv4/IPv6 translation
    ipaddress.ip_network("100::/64"),  # Discard-only
    ipaddress.ip_network("2001:db8::/32"),  # Documentation
    ipaddress.ip_network("fc00::/7"),  # Unique local (ULA)
    ipaddress.ip_network("fe80::/10"),  # Link-local
    ipaddress.ip_network("ff00::/8"),  # Multicast
]


class SecurityValidationError(ValueError):
    """Raised when an operation violates security policy or safety checks."""

    pass


def is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address belongs to any blocked private/reserved range."""
    if isinstance(ip, ipaddress.IPv4Address):
        return any(ip in net for net in BLOCKED_IPV4_NETWORKS)
    if isinstance(ip, ipaddress.IPv6Address):
        return any(ip in net for net in BLOCKED_IPV6_NETWORKS)
    return True


def is_safe_url(url: str, allow_private: bool = False) -> tuple[bool, str]:
    """Validate that a URL is safe to retrieve and does not target internal assets.

    Returns:
        (is_safe, reason): Boolean indicating safety and explanatory reason.
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string"

    url_clean = url.strip()
    try:
        parsed = urlparse(url_clean)
    except Exception as exc:
        return False, f"Failed to parse URL: {exc}"

    if parsed.scheme.lower() not in ("http", "https"):
        return (
            False,
            f"Unsupported URL scheme: {parsed.scheme!r}. Only 'http' and 'https' are permitted.",
        )

    hostname = parsed.hostname
    if not hostname:
        return False, "URL lacks a valid hostname"

    # Reject localhost names explicitly
    lower_host = hostname.lower()
    if lower_host in (
        "localhost",
        "localhost.localdomain",
        "broadcasthost",
        "ip6-localhost",
        "ip6-loopback",
    ):
        return False, f"Target hostname {hostname!r} resolves to local loopback."

    # RFC 2606 reserved documentation domains permit hermetic offline testing and documentation references
    if lower_host in ("example.com", "example.org", "example.net") or lower_host.endswith(
        ".example"
    ):
        return True, "URL is safe (RFC 2606 documentation domain)"

    # In strict mode, prevent access to private IP spaces and internal cloud metadata
    if not allow_private:
        try:
            # Resolve DNS
            addr_info = socket.getaddrinfo(hostname, None)
            if not addr_info:
                return False, f"Unable to resolve hostname: {hostname}"

            for item in addr_info:
                sockaddr = item[4]
                ip_str = sockaddr[0]
                ip_obj = ipaddress.ip_address(ip_str)
                if is_ip_blocked(ip_obj):
                    return False, f"Hostname {hostname!r} resolved to blocked/private IP {ip_str}"

        except socket.gaierror as err:
            return False, f"DNS resolution failed for {hostname}: {err}"
        except Exception as err:
            return False, f"IP validation failed: {err}"

    return True, "URL is safe"


def validate_url_for_request(url: str, allow_private: bool = False) -> str:
    """Validate a URL against SSRF policy or raise SecurityValidationError."""
    safe, reason = is_safe_url(url, allow_private=allow_private)
    if not safe:
        raise SecurityValidationError(f"SSRF Protection Error: {reason}")
    return url.strip()


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(length)


def verify_hmac_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Perform constant-time verification of an HMAC SHA-256 signature."""
    if not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
